"""
Exercise Generator

Generates vocabulary exercises from the vocabulary database.
Supports Fill-in-the-Blank, Matching, Spelling, and Hangman exercises.
"""

import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    Difficulty,
    ExerciseType,
    FillInBlankExercise,
    MatchingExercise,
    MatchingPair,
    SpellingExercise,
    HangmanExercise,
    ExerciseSet,
)


class ExerciseGenerator:
    """
    Generates vocabulary exercises from a list of vocabulary items.
    
    Supports different difficulty levels:
    - EASY: Shorter words (<=6 chars), more hints, fewer items
    - MEDIUM: Medium words (<=10 chars), some hints
    - HARD: All words, minimal hints, more items
    """
    
    # Difficulty settings
    DIFFICULTY_CONFIG = {
        Difficulty.EASY: {
            "max_word_length": 6,
            "show_hints": True,
            "matching_pairs": 4,
            "hangman_attempts": 8,
            "reveal_first_letter": True,
        },
        Difficulty.MEDIUM: {
            "max_word_length": 10,
            "show_hints": True,
            "matching_pairs": 6,
            "hangman_attempts": 6,
            "reveal_first_letter": False,
        },
        Difficulty.HARD: {
            "max_word_length": 100,  # No limit
            "show_hints": False,
            "matching_pairs": 8,
            "hangman_attempts": 5,
            "reveal_first_letter": False,
        },
    }
    
    def __init__(self, vocabulary_items: list[dict]):
        """
        Initialize with vocabulary items.
        
        Args:
            vocabulary_items: List of vocabulary dictionaries with structure:
                {
                    "id": "vocab_0001",
                    "sourceForm": {"text": "sleeve"},
                    "targetForm": {"text": "Ärmel"},
                    "wordType": "noun",
                    "exampleSentences": [{"source": "...", "target": "..."}]
                }
        """
        self.vocabulary = vocabulary_items
        self._build_indices()
    
    def _build_indices(self):
        """Build indices for efficient vocabulary lookup."""
        self.by_word_type = {}
        self.by_length = {}
        
        for item in self.vocabulary:
            # Index by word type
            word_type = item.get("wordType", "unknown")
            if word_type not in self.by_word_type:
                self.by_word_type[word_type] = []
            self.by_word_type[word_type].append(item)
            
            # Index by word length
            english = self._get_english(item)
            length = len(english)
            if length not in self.by_length:
                self.by_length[length] = []
            self.by_length[length].append(item)
    
    def _get_english(self, item: dict) -> str:
        """Extract English word from vocabulary item."""
        return item.get("sourceForm", {}).get("text", "")
    
    def _get_german(self, item: dict) -> str:
        """Extract German word from vocabulary item."""
        text = item.get("targetForm", {}).get("text", "")
        # If multiple translations (separated by ;), take the first
        if ";" in text:
            text = text.split(";")[0].strip()
        return text
    
    def _get_example_sentence(self, item: dict) -> Optional[str]:
        """Extract example sentence from vocabulary item."""
        sentences = item.get("exampleSentences", [])
        if sentences and len(sentences) > 0:
            return sentences[0].get("source")
        return None
    
    def _filter_by_difficulty(self, difficulty: Difficulty) -> list[dict]:
        """Filter vocabulary by difficulty settings."""
        config = self.DIFFICULTY_CONFIG[difficulty]
        max_length = config["max_word_length"]
        
        filtered = []
        for item in self.vocabulary:
            english = self._get_english(item)
            if len(english) <= max_length and english:
                filtered.append(item)
        
        return filtered
    
    def _select_random(self, items: list[dict], count: int) -> list[dict]:
        """Select random items without replacement."""
        if len(items) <= count:
            return items.copy()
        return random.sample(items, count)
    
    # =========================================================================
    # Fill-in-the-Blank Exercises
    # =========================================================================
    
    def generate_fill_in_blank(
        self,
        difficulty: Difficulty,
        count: int = 10,
    ) -> list[FillInBlankExercise]:
        """
        Generate fill-in-the-blank exercises.
        
        Uses example sentences and replaces the vocabulary word with a blank.
        Falls back to a simple template if no example sentence exists.
        """
        config = self.DIFFICULTY_CONFIG[difficulty]
        vocabulary = self._filter_by_difficulty(difficulty)
        
        # Filter to items with example sentences preferably
        with_examples = [v for v in vocabulary if self._get_example_sentence(v)]
        without_examples = [v for v in vocabulary if not self._get_example_sentence(v)]
        
        # Prefer items with examples
        selected = self._select_random(with_examples, count)
        if len(selected) < count:
            remaining = count - len(selected)
            selected.extend(self._select_random(without_examples, remaining))
        
        exercises = []
        for item in selected:
            english = self._get_english(item)
            german = self._get_german(item)
            word_type = item.get("wordType", "unknown")
            example = self._get_example_sentence(item)
            
            if example:
                # Replace the word in the sentence with ___
                # Use case-insensitive replacement
                pattern = re.compile(re.escape(english), re.IGNORECASE)
                sentence = pattern.sub("___", example)
                # Find blank position (word index)
                words = sentence.split()
                blank_pos = next(
                    (i for i, w in enumerate(words) if "___" in w), 0
                )
            else:
                # Create a simple template sentence
                templates = {
                    "noun": f"The ___ is important.",
                    "verb": f"I ___ every day.",
                    "adjective": f"It is very ___.",
                    "adverb": f"She did it ___.",
                }
                sentence = templates.get(word_type, f"The word is ___.")
                blank_pos = sentence.split().index("___") if "___" in sentence.split() else 0
            
            exercise = FillInBlankExercise(
                id=f"fib_{uuid.uuid4().hex[:8]}",
                type=ExerciseType.FILL_IN_BLANK,
                difficulty=difficulty,
                vocabulary_ids=[item["id"]],
                instructions="Fill in the blank with the correct English word.",
                sentence=sentence,
                blank_position=blank_pos,
                correct_answer=english,
                hint=german if config["show_hints"] else None,
                word_type=word_type,
            )
            exercises.append(exercise)
        
        return exercises
    
    # =========================================================================
    # Matching Exercises
    # =========================================================================
    
    def generate_matching(
        self,
        difficulty: Difficulty,
        count: int = 5,
    ) -> list[MatchingExercise]:
        """
        Generate matching exercises.
        
        Each exercise contains N pairs of English-German words to match.
        """
        config = self.DIFFICULTY_CONFIG[difficulty]
        vocabulary = self._filter_by_difficulty(difficulty)
        pairs_per_exercise = config["matching_pairs"]
        
        exercises = []
        remaining = vocabulary.copy()
        random.shuffle(remaining)
        
        for _ in range(count):
            if len(remaining) < pairs_per_exercise:
                # Refill if needed
                remaining = vocabulary.copy()
                random.shuffle(remaining)
            
            selected = remaining[:pairs_per_exercise]
            remaining = remaining[pairs_per_exercise:]
            
            pairs = []
            for item in selected:
                pair = MatchingPair(
                    id=f"pair_{uuid.uuid4().hex[:8]}",
                    left=self._get_english(item),
                    right=self._get_german(item),
                    vocabulary_id=item["id"],
                )
                pairs.append(pair)
            
            # Shuffle the right side
            shuffled = [p.right for p in pairs]
            random.shuffle(shuffled)
            
            exercise = MatchingExercise(
                id=f"match_{uuid.uuid4().hex[:8]}",
                type=ExerciseType.MATCHING,
                difficulty=difficulty,
                vocabulary_ids=[p.vocabulary_id for p in pairs],
                instructions="Match the English words with their German translations.",
                pairs=pairs,
                shuffled_right=shuffled,
            )
            exercises.append(exercise)
        
        return exercises
    
    # =========================================================================
    # Spelling Exercises
    # =========================================================================
    
    def generate_spelling(
        self,
        difficulty: Difficulty,
        count: int = 10,
    ) -> list[SpellingExercise]:
        """
        Generate spelling exercises.
        
        Shows the German word and scrambled letters of the English word.
        Student must unscramble to spell correctly.
        """
        config = self.DIFFICULTY_CONFIG[difficulty]
        vocabulary = self._filter_by_difficulty(difficulty)
        selected = self._select_random(vocabulary, count)
        
        exercises = []
        for item in selected:
            english = self._get_english(item)
            german = self._get_german(item)
            
            # Scramble the letters
            letters = list(english.lower())
            random.shuffle(letters)
            
            # Make sure it's actually scrambled
            attempts = 0
            while "".join(letters) == english.lower() and attempts < 10:
                random.shuffle(letters)
                attempts += 1
            
            # Build hint based on difficulty
            hint = None
            if config["show_hints"]:
                if config["reveal_first_letter"]:
                    hint = f"Starts with '{english[0].upper()}', {len(english)} letters"
                else:
                    hint = f"{len(english)} letters"
            
            exercise = SpellingExercise(
                id=f"spell_{uuid.uuid4().hex[:8]}",
                type=ExerciseType.SPELLING,
                difficulty=difficulty,
                vocabulary_ids=[item["id"]],
                instructions="Arrange the letters to spell the English word.",
                german_word=german,
                english_word=english,
                scrambled_letters=letters,
                hint=hint,
            )
            exercises.append(exercise)
        
        return exercises
    
    # =========================================================================
    # Hangman Exercises
    # =========================================================================
    
    def generate_hangman(
        self,
        difficulty: Difficulty,
        count: int = 10,
    ) -> list[HangmanExercise]:
        """
        Generate hangman exercises.
        
        Classic word guessing game with the German translation as hint.
        """
        config = self.DIFFICULTY_CONFIG[difficulty]
        vocabulary = self._filter_by_difficulty(difficulty)
        selected = self._select_random(vocabulary, count)
        
        exercises = []
        for item in selected:
            english = self._get_english(item)
            german = self._get_german(item)
            word_type = item.get("wordType", "unknown")
            
            # Determine which letters to reveal (for easy mode)
            revealed = []
            if config["reveal_first_letter"] and len(english) > 0:
                revealed = [0]  # Reveal first letter
            
            exercise = HangmanExercise(
                id=f"hang_{uuid.uuid4().hex[:8]}",
                type=ExerciseType.HANGMAN,
                difficulty=difficulty,
                vocabulary_ids=[item["id"]],
                instructions="Guess the English word letter by letter.",
                word=english,
                hint=german,
                category=word_type,
                max_attempts=config["hangman_attempts"],
                revealed_letters=revealed,
            )
            exercises.append(exercise)
        
        return exercises
    
    # =========================================================================
    # Exercise Set Generation
    # =========================================================================
    
    def generate_exercise_set(
        self,
        exercise_type: ExerciseType,
        difficulty: Difficulty,
        count: int = 10,
        name: Optional[str] = None,
    ) -> ExerciseSet:
        """
        Generate a complete exercise set of a specific type and difficulty.
        """
        generators = {
            ExerciseType.FILL_IN_BLANK: self.generate_fill_in_blank,
            ExerciseType.MATCHING: self.generate_matching,
            ExerciseType.SPELLING: self.generate_spelling,
            ExerciseType.HANGMAN: self.generate_hangman,
        }
        
        generator = generators.get(exercise_type)
        if not generator:
            raise ValueError(f"Unknown exercise type: {exercise_type}")
        
        exercises = generator(difficulty, count)
        
        if not name:
            name = f"{exercise_type.value.replace('_', ' ').title()} - {difficulty.value.title()}"
        
        return ExerciseSet(
            id=f"set_{uuid.uuid4().hex[:8]}",
            name=name,
            exercise_type=exercise_type,
            difficulty=difficulty,
            exercises=exercises,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    
    def generate_all_sets(
        self,
        count_per_set: int = 10,
    ) -> dict[str, ExerciseSet]:
        """
        Generate exercise sets for all types and difficulties.
        
        Returns a dictionary keyed by "{difficulty}_{type}".
        """
        sets = {}
        
        for difficulty in Difficulty:
            for exercise_type in ExerciseType:
                key = f"{difficulty.value}_{exercise_type.value}"
                sets[key] = self.generate_exercise_set(
                    exercise_type=exercise_type,
                    difficulty=difficulty,
                    count=count_per_set,
                )
        
        return sets
