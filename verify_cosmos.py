"""Quick script to verify vocabulary loaded in Cosmos DB."""
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

client = CosmosClient('https://vocab-tutor-db.documents.azure.com:443/', credential=DefaultAzureCredential())
container = client.get_database_client('VocabularyTutorDB').get_container_client('vocabulary')

# Query sample items
items = list(container.query_items('SELECT c.id, c.sourceForm, c.targetForm, c.wordType FROM c', enable_cross_partition_query=True, max_item_count=10))

print("Sample vocabulary from Cosmos DB:")
print("-" * 50)
for item in items[:5]:
    english = item['sourceForm']['text']
    german = item['targetForm']['text']
    word_type = item['wordType']
    print(f"  {english} -> {german} ({word_type})")

# Count total
total = len(list(container.query_items('SELECT c.id FROM c', enable_cross_partition_query=True)))
print("-" * 50)
print(f"Total vocabulary items in Cosmos DB: {total}")
