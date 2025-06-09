# ingest_script.py
import os
from data_ingestion import ingest_document

# Define the path to your document
# IMPORTANT: Make sure this path is correct on your system where you run this script.
# Example: If your PDF is in the same directory as this script:
DOCUMENT_TO_INGEST = "constitution-amh.pdf" # Change this to your actual file name
# Or if it's a text file:
# DOCUMENT_TO_INGEST = "your_amharic_text.txt"

# Define the collection name (must match RAG_COLLECTION_NAME in app.py)
COLLECTION_NAME = "collection4"

print(f"Attempting to ingest data from: {DOCUMENT_TO_INGEST}")
print(f"Into ChromaDB collection: {COLLECTION_NAME}")

if not os.path.exists(DOCUMENT_TO_INGEST):
    print(f"Error: Document '{DOCUMENT_TO_INGEST}' not found. Please place it in the same directory or update the path.")
else:
    # Call the ingestion function
    # You can adjust chunk_by, group_size, max_characters, language_type as needed
    result = ingest_document(
        file_path=DOCUMENT_TO_INGEST,
        collection_name=COLLECTION_NAME,
    )
    print("\nIngestion Result:")
    print(result)

    if result["status"] == "success":
        print("\n--- IMPORTANT ---")
        print("Data ingestion completed. To use the new data in your chatbot,")
        print("PLEASE RESTART YOUR FLASK APPLICATION (`python app.py`).")
        print("-----------------")