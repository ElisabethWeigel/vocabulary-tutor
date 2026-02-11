"""
Generate Exercises CLI

Command-line tool for generating vocabulary exercises from extracted vocabulary.

Usage:
    python generate_exercises.py --type all --difficulty all --count 10
    python generate_exercises.py --type hangman --difficulty easy --count 5
    python generate_exercises.py --type fill_in_blank,matching --difficulty medium
"""

import argparse
import sys
from pathlib import Path

from exercises import (
    ExerciseGenerator,
    ExerciseExporter,
    ExerciseType,
    Difficulty,
)

# Paths
PROJECT_DIR = Path(__file__).parent
VOCABULARY_PATH = PROJECT_DIR / "output" / "vocabulary.json"
OUTPUT_DIR = PROJECT_DIR / "output" / "exercises"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate vocabulary exercises from extracted vocabulary.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    Generate all exercise types at all difficulties:
        python generate_exercises.py --type all --difficulty all --count 10
    
    Generate only hangman exercises at easy difficulty:
        python generate_exercises.py --type hangman --difficulty easy --count 5
    
    Generate fill-in-blank and matching at medium difficulty:
        python generate_exercises.py --type fill_in_blank,matching --difficulty medium
        """,
    )
    
    parser.add_argument(
        "--type", "-t",
        type=str,
        default="all",
        help="Exercise type(s): fill_in_blank, matching, spelling, hangman, or 'all'. "
             "Comma-separated for multiple types.",
    )
    
    parser.add_argument(
        "--difficulty", "-d",
        type=str,
        default="all",
        help="Difficulty level(s): easy, medium, hard, or 'all'. "
             "Comma-separated for multiple levels.",
    )
    
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=10,
        help="Number of exercises per set (default: 10).",
    )
    
    parser.add_argument(
        "--vocabulary", "-v",
        type=str,
        default=str(VOCABULARY_PATH),
        help=f"Path to vocabulary JSON file (default: {VOCABULARY_PATH}).",
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=str(OUTPUT_DIR),
        help=f"Output directory for exercises (default: {OUTPUT_DIR}).",
    )
    
    parser.add_argument(
        "--with-answers",
        action="store_true",
        help="Export a separate answers.json file for server-side validation.",
    )
    
    return parser.parse_args()


def parse_types(type_str: str) -> list[ExerciseType]:
    """Parse exercise types from string."""
    if type_str.lower() == "all":
        return list(ExerciseType)
    
    types = []
    for t in type_str.split(","):
        t = t.strip().lower()
        try:
            types.append(ExerciseType(t))
        except ValueError:
            print(f"Warning: Unknown exercise type '{t}', skipping.")
    
    return types


def parse_difficulties(diff_str: str) -> list[Difficulty]:
    """Parse difficulty levels from string."""
    if diff_str.lower() == "all":
        return list(Difficulty)
    
    difficulties = []
    for d in diff_str.split(","):
        d = d.strip().lower()
        try:
            difficulties.append(Difficulty(d))
        except ValueError:
            print(f"Warning: Unknown difficulty '{d}', skipping.")
    
    return difficulties


def main():
    """Main entry point."""
    args = parse_args()
    
    print("=" * 60)
    print("Vocabulary Exercise Generator")
    print("=" * 60)
    
    # Parse arguments
    exercise_types = parse_types(args.type)
    difficulties = parse_difficulties(args.difficulty)
    vocabulary_path = Path(args.vocabulary)
    output_dir = Path(args.output)
    count = args.count
    
    print(f"\nVocabulary file: {vocabulary_path}")
    print(f"Output directory: {output_dir}")
    print(f"Exercise types: {[t.value for t in exercise_types]}")
    print(f"Difficulties: {[d.value for d in difficulties]}")
    print(f"Exercises per set: {count}")
    
    # Check vocabulary file exists
    if not vocabulary_path.exists():
        print(f"\nError: Vocabulary file not found: {vocabulary_path}")
        print("Please run extract_vocabulary.py first.")
        sys.exit(1)
    
    # Load vocabulary
    print("\n" + "-" * 40)
    print("Loading vocabulary...")
    
    exporter = ExerciseExporter(output_dir)
    vocabulary = exporter.load_vocabulary(vocabulary_path)
    
    print(f"Loaded {len(vocabulary)} vocabulary items")
    
    if not vocabulary:
        print("Error: No vocabulary items found.")
        sys.exit(1)
    
    # Create generator
    generator = ExerciseGenerator(vocabulary)
    
    # Generate exercise sets
    print("\n" + "-" * 40)
    print("Generating exercises...")
    
    exercise_sets = {}
    for difficulty in difficulties:
        for exercise_type in exercise_types:
            key = f"{difficulty.value}_{exercise_type.value}"
            print(f"  Generating: {key}...")
            
            exercise_set = generator.generate_exercise_set(
                exercise_type=exercise_type,
                difficulty=difficulty,
                count=count,
            )
            exercise_sets[key] = exercise_set
            
            print(f"    Created {len(exercise_set.exercises)} exercises")
    
    # Export to JSON
    print("\n" + "-" * 40)
    print("Exporting to JSON...")
    
    exported = exporter.export_all(exercise_sets)
    
    for key, path in exported.items():
        print(f"  {key}: {path}")
    
    # Export answers if requested
    if args.with_answers:
        print("\nExporting answer keys...")
        answers_path = exporter.export_answers(exercise_sets)
        print(f"  Answers: {answers_path}")
    
    # Summary
    total_exercises = sum(len(s.exercises) for s in exercise_sets.values())
    
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print(f"  Exercise sets created: {len(exercise_sets)}")
    print(f"  Total exercises: {total_exercises}")
    print(f"  Output directory: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
