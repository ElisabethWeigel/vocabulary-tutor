"""
Exercise Data Models

Defines the data structures for different exercise types:
- Fill-in-the-Blank: Complete sentences with missing vocabulary words
- Matching: Match English words with German translations
- Spelling: Unscramble letters to spell the word correctly
- Hangman: Guess the word letter by letter
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class Difficulty(Enum):
    """Exercise difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExerciseType(Enum):
    """Types of vocabulary exercises."""
    FILL_IN_BLANK = "fill_in_blank"
    MATCHING = "matching"
    SPELLING = "spelling"
    HANGMAN = "hangman"


@dataclass
class Exercise:
    """Base class for all exercises."""
    id: str
    type: ExerciseType
    difficulty: Difficulty
    vocabulary_ids: list[str]
    instructions: str
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
    
    def to_dict(self) -> dict:
        """Convert exercise to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "difficulty": self.difficulty.value,
            "vocabularyIds": self.vocabulary_ids,
            "instructions": self.instructions,
        }


@dataclass
class FillInBlankExercise(Exercise):
    """
    Fill-in-the-blank exercise.
    
    Shows a sentence with a blank where the vocabulary word should go.
    Student must type the correct word to complete the sentence.
    
    Example:
        Sentence: "In summer you wear shirts with short ___."
        Answer: "sleeves"
        Hint: "Ärmel" (German translation)
    """
    sentence: str = ""
    blank_position: int = 0  # Index where blank appears
    correct_answer: str = ""
    hint: Optional[str] = None  # German translation as hint
    word_type: Optional[str] = None  # noun, verb, etc.
    
    def __post_init__(self):
        self.type = ExerciseType.FILL_IN_BLANK
        super().__post_init__()
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "sentence": self.sentence,
            "blankPosition": self.blank_position,
            "correctAnswer": self.correct_answer,
            "hint": self.hint,
            "wordType": self.word_type,
        })
        return base


@dataclass
class MatchingPair:
    """A single pair in a matching exercise."""
    id: str
    left: str  # English word
    right: str  # German translation
    vocabulary_id: str


@dataclass
class MatchingExercise(Exercise):
    """
    Matching exercise.
    
    Shows two columns of words that need to be matched.
    Left column: English words
    Right column: German translations (shuffled)
    
    Example:
        Left: [sleeve, insect, safe]
        Right: [Insekt, sicher, Ärmel]  (shuffled)
    """
    pairs: list[MatchingPair] = field(default_factory=list)
    shuffled_right: list[str] = field(default_factory=list)  # Pre-shuffled for frontend
    
    def __post_init__(self):
        self.type = ExerciseType.MATCHING
        super().__post_init__()
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "pairs": [
                {"id": p.id, "left": p.left, "right": p.right, "vocabularyId": p.vocabulary_id}
                for p in self.pairs
            ],
            "shuffledRight": self.shuffled_right,
            "pairCount": len(self.pairs),
        })
        return base


@dataclass
class SpellingExercise(Exercise):
    """
    Spelling exercise.
    
    Shows the German word and scrambled letters of the English word.
    Student must arrange letters to spell the English word correctly.
    
    Example:
        German: "Ärmel"
        Scrambled: "e l s e v e"
        Answer: "sleeve"
    """
    german_word: str = ""
    english_word: str = ""
    scrambled_letters: list[str] = field(default_factory=list)
    hint: Optional[str] = None  # First letter or word length
    
    def __post_init__(self):
        self.type = ExerciseType.SPELLING
        super().__post_init__()
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "germanWord": self.german_word,
            "englishWord": self.english_word,
            "scrambledLetters": self.scrambled_letters,
            "hint": self.hint,
            "letterCount": len(self.english_word),
        })
        return base


@dataclass
class HangmanExercise(Exercise):
    """
    Hangman exercise.
    
    Classic hangman game where student guesses letters.
    Shows the German translation as a hint.
    
    Example:
        Word: "sleeve" (hidden as "_ _ _ _ _ _")
        Hint: "Ärmel"
        Category: "noun"
        Max attempts: 6
    """
    word: str = ""
    hint: str = ""  # German translation
    category: str = ""  # Word type (noun, verb, etc.)
    max_attempts: int = 6
    revealed_letters: list[int] = field(default_factory=list)  # Indices of pre-revealed letters (for easy mode)
    
    def __post_init__(self):
        self.type = ExerciseType.HANGMAN
        super().__post_init__()
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "word": self.word,
            "wordLength": len(self.word),
            "hint": self.hint,
            "category": self.category,
            "maxAttempts": self.max_attempts,
            "revealedLetters": self.revealed_letters,
        })
        return base


@dataclass
class ExerciseSet:
    """A collection of exercises grouped by type and difficulty."""
    id: str
    name: str
    exercise_type: ExerciseType
    difficulty: Difficulty
    exercises: list[Exercise] = field(default_factory=list)
    created_at: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "exerciseType": self.exercise_type.value,
            "difficulty": self.difficulty.value,
            "exerciseCount": len(self.exercises),
            "exercises": [e.to_dict() for e in self.exercises],
            "createdAt": self.created_at,
        }
