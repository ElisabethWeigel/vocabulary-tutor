"""
Exercise Exporter

Exports generated exercises to JSON files organized by difficulty and type.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from .models import ExerciseSet, Difficulty, ExerciseType


class ExerciseExporter:
    """
    Exports exercise sets to JSON files.
    
    Directory structure:
        output/exercises/
            easy/
                fill_in_blank.json
                matching.json
                spelling.json
                hangman.json
            medium/
                ...
            hard/
                ...
            manifest.json
    """
    
    def __init__(self, output_dir: Path):
        """
        Initialize exporter with output directory.
        
        Args:
            output_dir: Base directory for exercise output (e.g., output/exercises)
        """
        self.output_dir = Path(output_dir)
    
    def _ensure_directories(self):
        """Create output directory structure."""
        for difficulty in Difficulty:
            dir_path = self.output_dir / difficulty.value
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def export_set(self, exercise_set: ExerciseSet) -> Path:
        """
        Export a single exercise set to JSON.
        
        Args:
            exercise_set: The exercise set to export
            
        Returns:
            Path to the exported JSON file
        """
        self._ensure_directories()
        
        # Determine output path
        difficulty_dir = self.output_dir / exercise_set.difficulty.value
        filename = f"{exercise_set.exercise_type.value}.json"
        output_path = difficulty_dir / filename
        
        # Convert to dict and save
        data = exercise_set.to_dict()
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def export_all(self, exercise_sets: dict[str, ExerciseSet]) -> dict[str, Path]:
        """
        Export all exercise sets and create a manifest.
        
        Args:
            exercise_sets: Dictionary of exercise sets keyed by "{difficulty}_{type}"
            
        Returns:
            Dictionary mapping set keys to their exported file paths
        """
        self._ensure_directories()
        
        exported = {}
        manifest_entries = []
        
        for key, exercise_set in exercise_sets.items():
            path = self.export_set(exercise_set)
            exported[key] = path
            
            # Build manifest entry
            manifest_entries.append({
                "key": key,
                "path": str(path.relative_to(self.output_dir)),
                "type": exercise_set.exercise_type.value,
                "difficulty": exercise_set.difficulty.value,
                "exerciseCount": len(exercise_set.exercises),
                "name": exercise_set.name,
            })
        
        # Write manifest
        manifest = {
            "version": "1.0",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "totalSets": len(exercise_sets),
            "sets": manifest_entries,
        }
        
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return exported
    
    def export_answers(self, exercise_sets: dict[str, ExerciseSet]) -> Path:
        """
        Export answer keys separately for frontend validation.
        
        This creates a separate answers.json file that can be loaded
        server-side for validation without exposing answers to the client.
        
        Args:
            exercise_sets: Dictionary of exercise sets
            
        Returns:
            Path to the answers.json file
        """
        self._ensure_directories()
        
        answers = {}
        
        for key, exercise_set in exercise_sets.items():
            set_answers = {}
            
            for exercise in exercise_set.exercises:
                exercise_dict = exercise.to_dict()
                
                # Extract the answer based on exercise type
                if exercise_set.exercise_type == ExerciseType.FILL_IN_BLANK:
                    set_answers[exercise.id] = {
                        "answer": exercise_dict.get("correctAnswer"),
                    }
                elif exercise_set.exercise_type == ExerciseType.MATCHING:
                    # Answer is the correct pairing
                    pairs = exercise_dict.get("pairs", [])
                    set_answers[exercise.id] = {
                        "pairs": {p["left"]: p["right"] for p in pairs},
                    }
                elif exercise_set.exercise_type == ExerciseType.SPELLING:
                    set_answers[exercise.id] = {
                        "answer": exercise_dict.get("englishWord"),
                    }
                elif exercise_set.exercise_type == ExerciseType.HANGMAN:
                    set_answers[exercise.id] = {
                        "answer": exercise_dict.get("word"),
                    }
            
            answers[key] = set_answers
        
        answers_path = self.output_dir / "answers.json"
        with open(answers_path, "w", encoding="utf-8") as f:
            json.dump(answers, f, indent=2, ensure_ascii=False)
        
        return answers_path
    
    def load_vocabulary(self, vocabulary_path: Path) -> list[dict]:
        """
        Load vocabulary from a JSON file.
        
        Args:
            vocabulary_path: Path to vocabulary.json
            
        Returns:
            List of vocabulary items
        """
        with open(vocabulary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return data.get("vocabularyItems", [])
