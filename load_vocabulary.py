"""
Load Vocabulary into Cosmos DB

Loads extracted vocabulary items from JSON into Azure Cosmos DB.
Uses Azure Identity (DefaultAzureCredential) for authentication.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential

load_dotenv()

# Configuration
COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "https://vocab-tutor-db.documents.azure.com:443/")
DATABASE_NAME = "VocabularyTutorDB"
VOCABULARY_CONTAINER = "vocabulary"

VOCABULARY_FILE = Path(__file__).parent / "output" / "vocabulary.json"


def load_vocabulary_data() -> dict:
    """Load vocabulary data from JSON file."""
    with open(VOCABULARY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def create_cosmos_client() -> CosmosClient:
    """Create Cosmos DB client with Azure Identity authentication."""
    credential = DefaultAzureCredential()
    return CosmosClient(COSMOS_ENDPOINT, credential=credential)


def prepare_document(vocab_item: dict) -> dict:
    """
    Prepare a vocabulary item for Cosmos DB insertion.
    Ensures it has required fields and proper format.
    """
    # Use the vocab ID as the document ID
    doc = vocab_item.copy()
    
    # Ensure we have required Cosmos DB fields
    if "id" not in doc:
        doc["id"] = f"vocab_{datetime.now(timezone.utc).timestamp()}"
    
    # Clean up the ID to be Cosmos DB compliant (no special chars)
    doc["id"] = doc["id"].replace(" ", "_")
    
    # Add metadata
    doc["_loadedAt"] = datetime.now(timezone.utc).isoformat()
    doc["_type"] = "vocabulary"
    
    return doc


def load_to_cosmos(vocabulary_items: list[dict]) -> tuple[int, int]:
    """
    Load vocabulary items into Cosmos DB.
    Returns (success_count, error_count).
    """
    client = create_cosmos_client()
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(VOCABULARY_CONTAINER)
    
    success_count = 0
    error_count = 0
    
    for item in vocabulary_items:
        try:
            doc = prepare_document(item)
            container.upsert_item(doc)
            success_count += 1
            
            # Progress indicator
            if success_count % 10 == 0:
                print(f"  Loaded {success_count} items...")
                
        except Exception as e:
            error_count += 1
            print(f"  Error loading item {item.get('id', 'unknown')}: {e}")
    
    return success_count, error_count


def main():
    """Main loading workflow."""
    print("=" * 60)
    print("Loading Vocabulary into Cosmos DB")
    print("=" * 60)
    
    print(f"\nCosmos DB: {COSMOS_ENDPOINT}")
    print(f"Database: {DATABASE_NAME}")
    print(f"Container: {VOCABULARY_CONTAINER}")
    print(f"Source file: {VOCABULARY_FILE}")
    
    # Check if vocabulary file exists
    if not VOCABULARY_FILE.exists():
        print(f"\nError: Vocabulary file not found: {VOCABULARY_FILE}")
        print("Please run extract_vocabulary.py first.")
        return
    
    # Load vocabulary data
    print("\n" + "-" * 40)
    print("Loading vocabulary from JSON...")
    
    data = load_vocabulary_data()
    vocabulary_items = data.get("vocabularyItems", [])
    
    print(f"Found {len(vocabulary_items)} vocabulary items")
    
    if not vocabulary_items:
        print("No vocabulary items to load.")
        return
    
    # Load into Cosmos DB
    print("\n" + "-" * 40)
    print("Uploading to Cosmos DB...")
    
    success_count, error_count = load_to_cosmos(vocabulary_items)
    
    # Summary
    print("\n" + "=" * 60)
    print("LOADING COMPLETE")
    print(f"  Successfully loaded: {success_count}")
    print(f"  Errors: {error_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
