"""
Vocabulary Extraction Script

Extracts vocabulary items from textbook page images using Azure AI Content Understanding.
Outputs structured JSON with English words, German translations, example phrases, page numbers, and lesson units.
"""

import os
import json
import base64
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

from azure.identity import DefaultAzureCredential

load_dotenv()

# Configuration
ENDPOINT = os.environ["CONTENTUNDERSTANDING_ENDPOINT"].rstrip("/")
API_VERSION = "2025-11-01"
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"


class ContentUnderstandingClient:
    """Simple client for Azure AI Content Understanding REST API."""
    
    def __init__(self, endpoint: str, credential):
        self.endpoint = endpoint
        self.credential = credential
        self._token = None
    
    def _get_headers(self):
        """Get authentication headers."""
        if self._token is None or self._is_token_expired():
            self._token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
        return {
            "Authorization": f"Bearer {self._token.token}",
            "Content-Type": "application/json",
        }
    
    def _is_token_expired(self):
        """Check if token is expired."""
        if self._token is None:
            return True
        return self._token.expires_on < time.time() + 60
    
    def get_analyzer(self, analyzer_id: str) -> dict:
        """Get an analyzer by ID."""
        url = f"{self.endpoint}/contentunderstanding/analyzers/{analyzer_id}?api-version={API_VERSION}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_analyzer(self, analyzer_id: str, analyzer_template: dict) -> dict:
        """Create a new analyzer."""
        url = f"{self.endpoint}/contentunderstanding/analyzers/{analyzer_id}?api-version={API_VERSION}"
        response = requests.put(url, headers=self._get_headers(), json=analyzer_template)
        if not response.ok:
            print(f"Error creating analyzer: {response.status_code}")
            print(f"Response: {response.text}")
        response.raise_for_status()
        
        # Poll for completion
        operation_location = response.headers.get("Operation-Location")
        if operation_location:
            return self._poll_operation(operation_location)
        return response.json()
    
    def _poll_operation(self, operation_url: str, timeout: int = 300) -> dict:
        """Poll an operation until completion."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(operation_url, headers=self._get_headers())
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status", "").lower()
            if status in ("succeeded", "completed", "ready"):
                return result
            elif status in ("failed", "error"):
                raise Exception(f"Operation failed: {result}")
            
            time.sleep(2)
        raise TimeoutError("Operation timed out")
    
    def analyze(self, analyzer_id: str, data_uri: str) -> dict:
        """Analyze content using an analyzer with binary data."""
        # Use analyzeBinary endpoint for base64 data
        url = f"{self.endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyzeBinary?api-version={API_VERSION}"
        
        # Parse the data URI and send as binary
        # data_uri format: data:image/jpeg;base64,<base64_data>
        if data_uri.startswith("data:"):
            parts = data_uri.split(",", 1)
            if len(parts) == 2:
                mime_info = parts[0]  # data:image/jpeg;base64
                base64_data = parts[1]
                # Get mime type from data URI
                mime_type = mime_info.split(":")[1].split(";")[0] if ":" in mime_info else "application/octet-stream"
                
                # Decode base64 and send as binary
                import base64
                binary_data = base64.b64decode(base64_data)
                
                headers = self._get_headers()
                headers["Content-Type"] = mime_type
                
                response = requests.post(url, headers=headers, data=binary_data)
                if not response.ok:
                    print(f"Error analyzing: {response.status_code}")
                    print(f"Response: {response.text}")
                response.raise_for_status()
                
                # Poll for completion
                operation_location = response.headers.get("Operation-Location")
                if operation_location:
                    return self._poll_operation(operation_location)
                return response.json()
        
        raise ValueError("Invalid data URI format")


def create_vocabulary_analyzer_template() -> dict:
    """
    Create the analyzer template for vocabulary extraction.
    Uses the fieldSchema format from the API docs (2025-11-01).
    prebuilt-document has OCR capabilities and supports extract method.
    """
    return {
        "description": "Extracts English-German vocabulary pairs from textbook pages including words, translations, examples, page numbers and lesson units",
        "baseAnalyzerId": "prebuilt-document",
        "models": {
            "completion": "gpt-4.1"
        },
        "config": {
            "returnDetails": True,
            "disableContentFiltering": False
        },
        "fieldSchema": {
            "fields": {
                "vocabularyItems": {
                    "type": "array",
                    "method": "extract",
                    "description": "List of vocabulary entries found on the page. Each entry contains an English word with its German translation.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "englishWord": {
                                "type": "string",
                                "method": "extract",
                                "description": "The English vocabulary word or phrase"
                            },
                            "germanTranslation": {
                                "type": "string",
                                "method": "extract", 
                                "description": "The German translation of the English word"
                            },
                            "exampleSentence": {
                                "type": "string",
                                "method": "generate",
                                "description": "An example sentence using the vocabulary word if provided on the page"
                            },
                            "wordType": {
                                "type": "string",
                                "method": "classify",
                                "description": "The grammatical type of the word",
                                "enum": ["noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun", "other"]
                            }
                        }
                    }
                },
                "pageNumber": {
                    "type": "number",
                    "method": "extract",
                    "description": "The page number shown on the textbook page, if visible"
                },
                "lessonUnit": {
                    "type": "string",
                    "method": "extract",
                    "description": "The lesson number, unit number, or chapter title if visible on the page (e.g., 'Unit 3', 'Lesson 5')"
                },
                "textbookTitle": {
                    "type": "string",
                    "method": "extract",
                    "description": "The textbook title or series name if visible on the page"
                }
            }
        }
    }


def create_vocabulary_analyzer(client: ContentUnderstandingClient) -> str:
    """
    Create a custom analyzer for extracting vocabulary from textbook images.
    Returns the analyzer ID.
    """
    analyzer_id = "vocabularyExtractor"
    
    try:
        # Check if analyzer already exists
        existing = client.get_analyzer(analyzer_id)
        print(f"Analyzer '{analyzer_id}' already exists. Using existing analyzer.")
        return analyzer_id
    except requests.exceptions.HTTPError as e:
        if e.response.status_code != 404:
            raise
    
    print(f"Creating analyzer '{analyzer_id}'...")
    
    template = create_vocabulary_analyzer_template()
    client.create_analyzer(analyzer_id, template)
    
    print(f"Analyzer '{analyzer_id}' created successfully.")
    return analyzer_id


def encode_image_to_base64(image_path: Path) -> str:
    """Read an image file and encode it as base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: Path) -> str:
    """Determine MIME type from file extension."""
    ext = image_path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return mime_types.get(ext, "image/jpeg")


def analyze_image(
    client: ContentUnderstandingClient,
    analyzer_id: str,
    image_path: Path,
) -> dict | None:
    """
    Analyze a single textbook image and extract vocabulary.
    Returns extracted data as a dictionary.
    """
    print(f"Analyzing: {image_path.name}...")
    
    # Encode image as base64 data URI
    base64_data = encode_image_to_base64(image_path)
    mime_type = get_image_mime_type(image_path)
    data_uri = f"data:{mime_type};base64,{base64_data}"
    
    try:
        # Submit analysis request
        result = client.analyze(analyzer_id, data_uri)
        
        # Extract fields from result
        contents = result.get("result", {}).get("contents", [])
        if contents and len(contents) > 0:
            content = contents[0]
            
            # Build result dictionary
            extracted = {
                "sourceFile": image_path.name,
                "extractedAt": datetime.utcnow().isoformat() + "Z",
                "markdown": content.get("markdown"),
                "fields": {},
            }
            
            # Extract custom fields
            fields = content.get("fields", {})
            for field_name, field_value in fields.items():
                if field_value:
                    # Handle different field value formats
                    if isinstance(field_value, dict):
                        if "valueArray" in field_value:
                            extracted["fields"][field_name] = field_value["valueArray"]
                        elif "valueString" in field_value:
                            extracted["fields"][field_name] = field_value["valueString"]
                        elif "valueNumber" in field_value:
                            extracted["fields"][field_name] = field_value["valueNumber"]
                        elif "value" in field_value:
                            extracted["fields"][field_name] = field_value["value"]
                        else:
                            extracted["fields"][field_name] = field_value
                    else:
                        extracted["fields"][field_name] = field_value
            
            vocab_items = extracted.get("fields", {}).get("vocabularyItems", [])
            count = len(vocab_items) if isinstance(vocab_items, list) else 0
            print(f"  [OK] Extracted {count} vocabulary items")
            return extracted
        else:
            print(f"  [X] No content extracted")
            return None
            
    except requests.exceptions.HTTPError as e:
        print(f"  [X] Error analyzing {image_path.name}: {e}")
        return None
    except Exception as e:
        print(f"  [X] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_field_value(field):
    """Extract the actual value from a Content Understanding field object."""
    if field is None:
        return None
    if isinstance(field, dict):
        # Handle nested valueString, valueNumber, valueObject etc.
        if "valueString" in field:
            return field["valueString"]
        elif "valueNumber" in field:
            return field["valueNumber"]
        elif "valueObject" in field:
            return field["valueObject"]
        elif "value" in field:
            return field["value"]
        # If it looks like a raw field with just type/confidence, return None
        if set(field.keys()) <= {"type", "confidence", "spans", "source"}:
            return None
        # Already a plain value or unrecognized structure
        return field
    return field


def transform_to_vocabulary_format(raw_results: list[dict]) -> list[dict]:
    """
    Transform raw extraction results into the final vocabulary JSON format
    matching the data model from the plan.
    """
    vocabulary_items = []
    
    for result in raw_results:
        if not result or "fields" not in result:
            continue
            
        fields = result["fields"]
        page_number = get_field_value(fields.get("pageNumber"))
        lesson_unit = get_field_value(fields.get("lessonUnit"))
        textbook_title = get_field_value(fields.get("textbookTitle"))
        source_file = result.get("sourceFile", "unknown")
        
        items = fields.get("vocabularyItems", [])
        if not isinstance(items, list):
            items = [items] if items else []
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            # Handle the nested valueObject structure
            vocab_obj = item.get("valueObject", item)
            
            # Extract values from nested structure
            english_word = get_field_value(vocab_obj.get("englishWord", ""))
            german_translation = get_field_value(vocab_obj.get("germanTranslation", ""))
            word_type = get_field_value(vocab_obj.get("wordType", "unknown"))
            example = get_field_value(vocab_obj.get("exampleSentence"))
            
            if not english_word and not german_translation:
                continue  # Skip empty entries
                
            vocab_entry = {
                "id": f"vocab_{len(vocabulary_items) + 1:04d}",
                "sourceLanguage": "en",
                "targetLanguage": "de",
                "sourceForm": {
                    "text": english_word or "",
                },
                "targetForm": {
                    "text": german_translation or "",
                    "languageSpecificData": {},
                },
                "wordType": word_type or "unknown",
                "regularity": "unknown",  # To be classified by agent later
                "exampleSentences": [],
                "textbookMemberships": [
                    {
                        "textbookId": textbook_title or "unknown",
                        "unitId": lesson_unit,
                        "lessonId": None,
                        "page": page_number,
                        "sourceFile": source_file,
                    }
                ],
                "extractedAt": result.get("extractedAt"),
            }
            
            # Add example sentence if present
            if example:
                vocab_entry["exampleSentences"].append({
                    "source": example,
                    "target": None,  # May need separate extraction
                })
            
            vocabulary_items.append(vocab_entry)
    
    return vocabulary_items


def main():
    """Main extraction workflow."""
    print("=" * 60)
    print("Vocabulary Extraction from Textbook Images")
    print("=" * 60)
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Initialize client with Azure Identity
    credential = DefaultAzureCredential()
    client = ContentUnderstandingClient(endpoint=ENDPOINT, credential=credential)
    
    print(f"\nEndpoint: {ENDPOINT}")
    print(f"Data directory: {DATA_DIR}")
    
    # Find all image files
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif"}
    image_files = [
        f for f in DATA_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if not image_files:
        print(f"\nNo image files found in {DATA_DIR}")
        return
    
    print(f"\nFound {len(image_files)} image(s) to process:")
    for img in image_files:
        print(f"  - {img.name}")
    
    # Create or get analyzer
    print("\n" + "-" * 40)
    analyzer_id = create_vocabulary_analyzer(client)
    
    # Analyze each image
    print("\n" + "-" * 40)
    print("Analyzing images...")
    
    raw_results = []
    for image_path in image_files:
        result = analyze_image(client, analyzer_id, image_path)
        if result:
            raw_results.append(result)
    
    # Transform to final format
    print("\n" + "-" * 40)
    print("Transforming results...")
    
    vocabulary_items = transform_to_vocabulary_format(raw_results)
    
    # Save raw results
    raw_output_path = OUTPUT_DIR / "extraction_raw.json"
    with open(raw_output_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, indent=2, ensure_ascii=False)
    print(f"\nRaw results saved to: {raw_output_path}")
    
    # Save transformed vocabulary
    vocab_output_path = OUTPUT_DIR / "vocabulary.json"
    with open(vocab_output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "extractedAt": datetime.utcnow().isoformat() + "Z",
                "sourceFiles": [f.name for f in image_files],
                "totalItems": len(vocabulary_items),
                "vocabularyItems": vocabulary_items,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Vocabulary JSON saved to: {vocab_output_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print(f"  Images processed: {len(image_files)}")
    print(f"  Vocabulary items extracted: {len(vocabulary_items)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
