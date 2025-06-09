import os
import chromadb
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from werkzeug.utils import secure_filename # Still needed for clear_db temp folder in case, but not upload
import shutil

# Import the ingestion function - it will be called separately now
from data_ingestion import ingest_document

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
# Get API key from environment variable
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please create a .env file.")

# Configure Google Generative AI
genai.configure(api_key=GOOGLE_API_KEY)

# Define paths and model names
CHROMA_DB_PATH = "./chroma_db_data"
# UPLOAD_FOLDER is no longer strictly needed for frontend uploads,
# but can be kept for backend ingestion if you choose to temporarily save files there.
# os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Ensure upload folder exists if you keep it

EMBEDDER_MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'
GENERATIVE_MODEL_NAME = "models/gemini-1.5-flash-latest"

RAG_COLLECTION_NAME = "collection4"

# --- Global Initialization (Loaded once when the app starts) ---
chroma_client = None
collection = None
embedder = None

try:
    print(f"Loading ChromaDB from: {CHROMA_DB_PATH}")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma_client.get_or_create_collection(name=RAG_COLLECTION_NAME)
    print(f"ChromaDB collection '{RAG_COLLECTION_NAME}' loaded with {collection.count()} documents.")
except Exception as e:
    print(f"Error loading ChromaDB: {e}")
    collection = None

try:
    print(f"Loading SentenceTransformer model: {EMBEDDER_MODEL_NAME}")
    embedder = SentenceTransformer(EMBEDDER_MODEL_NAME)
    print("SentenceTransformer model loaded.")
except Exception as e:
    print(f"Error loading SentenceTransformer: {e}")
    embedder = None

gemini_model = genai.GenerativeModel(GENERATIVE_MODEL_NAME)


# --- RAG Logic Function (Remains the same) ---
def generate_rag_answer(query_text: str, n_results: int = 2) -> str:
    if not collection or not embedder:
        return "Backend services (ChromaDB or Embedder) are not initialized. Cannot generate answer."

    try:
        if collection.count() == 0:
            return "የመረጃ ቋቱ ባዶ ነው። እባክዎ ከመጠየቅዎ በፊት ሰነዶችን ይስቀሉ።"

        query_embedding = embedder.encode(query_text).tolist()

        # --- START CRITICAL DEBUGGING ---
        print(f"\nDEBUG INFO (RAG Query):")
        print(f"  - Requested n_results: {n_results}") # What n_results is being used in this call
        print(f"  - Total documents in collection: {collection.count()}") # How many total documents are there

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            # include=['documents', 'distances', 'metadatas', 'ids'] # Ensure all are included for debugging
        )
        
        if "documents" not in results or not results["documents"] or not results["documents"][0]:
            print("  - WARNING: 'documents' key missing or empty in query results. No chunks retrieved.")
            return "No matching context found in the database."

        retrieved_chunks = results["documents"][0]
        retrieved_ids = results.get("ids", [[]])[0]
        retrieved_distances = results.get("distances", [[]])[0]

        print(f"  - Actual number of chunks retrieved by ChromaDB: {len(retrieved_chunks)}") # How many chunks ChromaDB returned

        # Print details for the first few retrieved chunks
        for i in range(min(len(retrieved_chunks), 5)): # Print details for up to 5 chunks
            print(f"    Chunk {i+1} (ID: {retrieved_ids[i]}, Distance: {retrieved_distances[i]:.4f}):")
            print(f"      Text Length: {len(retrieved_chunks[i])} characters")
            print(f"      Text Start: '{retrieved_chunks[i][:150]}...'") # Print start of text
            print(f"      Metadata: {results.get('metadatas', [{}])[0][i]}")

        print("--- END CRITICAL DEBUGGING ---\n")

        context = "\n\n".join(retrieved_chunks)
        
        # This print will now show the combined context, but after you've seen the debug info
        print("--- COMBINED CONTEXT SENT TO LLM (first 1000 chars) ---")
        print(context[:1000] + "..." if len(context) > 1000 else context)
        print("------------------------------------------------------\n")
        if not context.strip():
            return "ከመረጃ ቋቱ ጋር የሚዛመድ መረጃ አልተገኘም። እባክዎ ጥያቄዎን በሌላ መንገድ ይሞክሩ።"

        # first_prompt = f"""
        # እርስዎ አጋዥ የ AI ረዳት ነዎት። ከቀረበው የአማርኛ ጽሑፍ ውስጥ ዋና ዋና ነጥቦችን እና ዝርዝሮችን ሳይለቁ ጠቅለል ያለ ማጠቃለያ ይፍጠሩ።

        # ጽሑፍ:
        # {context}
        # """
        # res_summary_obj = gemini_model.generate_content(first_prompt)
        # summarized_context = res_summary_obj.text if res_summary_obj and hasattr(res_summary_obj, 'text') else "No summary could be generated from the provided context."

        final_prompt = f"""
        እርስዎ አጋዥ የ AI ረዳት ነዎት። ጥያቄውን ለመመለስ የቀረበውን ጽሑፍ ብቻ ይጠቀሙ።

        ጽሑፍ:
        {context}

        ጥያቄ:
        {query_text}

        መልሱን ግልጽ እና አጭር በሆነ መንገድ በጽሑፉ ላይ ብቻ በመመስረት ይመልሱ።
        """
        response_obj = gemini_model.generate_content(final_prompt)
        final_answer = response_obj.text if response_obj and hasattr(response_obj, 'text') else "መልስ ማመንጨት አልተቻለም።"

        return final_answer

    except Exception as e:
        print(f"An error occurred during RAG generation: {e}")
        if "dimension" in str(e).lower() and "expecting embedding with dimension" in str(e).lower():
            return "የመረጃ ቋቱ እና የማመንጫ ሞዴሉ እኩል ያልሆኑ ልኬቶች አላቸው። እባክዎ ፋይል ከሰቀሉ በኋላ መተግበሪያውን እንደገና ያስጀምሩት።"
        return f"ጥያቄዎን ሲያስተናግድ ስህተት ተፈጥሯል። እባክዎ እንደገና ይሞክሩ። ስህተት: {e}"


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"response": "No message provided."}), 400

    bot_response = generate_rag_answer(user_message)
    return jsonify({"response": bot_response})

# Removed the @app.route('/upload', methods=['POST']) function entirely

@app.route('/clear_db', methods=['POST'])
def clear_database():
    try:
        if os.path.exists(CHROMA_DB_PATH):
            shutil.rmtree(CHROMA_DB_PATH)
            os.makedirs(CHROMA_DB_PATH, exist_ok=True)
            
            global collection
            global chroma_client
            chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            collection = chroma_client.get_or_create_collection(name=RAG_COLLECTION_NAME)
            print(f"ChromaDB at {CHROMA_DB_PATH} cleared. Collection '{RAG_COLLECTION_NAME}' re-created.")
            return jsonify({"status": "success", "message": "ChromaDB has been cleared and re-initialized. Please restart the application."})
        else:
            return jsonify({"status": "warning", "message": "ChromaDB directory does not exist, nothing to clear."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error clearing database: {e}"}), 500


# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)