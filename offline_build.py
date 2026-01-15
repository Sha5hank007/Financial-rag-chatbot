# offline_build.py
import os
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# === portable paths & config ===
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR    = Path(os.getenv("DATA_DIR", BASE_DIR / "Data"))
CHUNKS_DIR  = Path(os.getenv("CHUNKS_DIR", BASE_DIR / "chunks" / "previous_chunks"))
CHROMA_DIR  = Path(os.getenv("CHROMA_DIR", BASE_DIR / "chromadb_vectors" / "global"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", BASE_DIR / "uploads"))
LOGS_DIR    = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))

for d in (DATA_DIR, CHUNKS_DIR, CHROMA_DIR, UPLOADS_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# === CONFIG ===
CHUNKS_DIR = CHUNKS_DIR
CHROMA_DIR = CHROMA_DIR
COLLECTION_NAME = "global_chunks"

# Batch size recommendation for 2026 for performance and stability
BATCH_SIZE = 100 
PROGRESS_EVERY = 500

# === embedding function ===
# This uses the all-MiniLM-L12-v2 model which produces 384-dimensional vectors
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L12-v2"
)

# === chunk -> markdown (compact) ===
def chunk_to_markdown(chunk: dict) -> str:
    lines = []
    
    # 1. Safely retrieve the global header or use a placeholder
    global_headers = chunk.get('global_header', [])
    # Check if list is not empty before accessing [0]
    section_name = global_headers[0] if global_headers else "General"
    
    source = chunk.get("source_file", "Unknown Source")
    lines.append(f"Context: {source} | Section: {section_name}")

    # 2. Extract and join subheaders safely
    subheaders = chunk.get("subheaders", [])
    title = " | ".join(subheaders) if subheaders else "Data Row"
    lines.append(f"### {title}")

    # 3. Filter data: Skip noise like 0, NA, or empty strings
    data_dict = chunk.get("data", {})
    for k, v in data_dict.items():
        # Using a set of 'noise' values for faster lookup in 2026
        if v not in {0, "0", "NA", "N.A.", "", None}:
            lines.append(f"- **{k}**: {v}")

    return "\n".join(lines)



# === load chunks ===
def load_chunks(chunks_dir):
    docs, metas, ids = [], [], []
    for fp in Path(chunks_dir).rglob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                c = json.load(f)
        except Exception as e:
            print(f"Error loading {fp}: {e}")
            continue
            
        text = chunk_to_markdown(c)
        if not text:
            continue
            
        # Ensure ID is unique across different folders or versions
        chunk_id = f"{c.get('source_file')}__{c.get('sheet_name')}__row_{c.get('excel_row_number')}"
        docs.append(text)
        ids.append(chunk_id)
        metas.append({
            "source_file": c.get("source_file"),
            "sheet_name": c.get("sheet_name"),
            "excel_row_number": c.get("excel_row_number"),
            "path": str(fp)
        })
    return docs, metas, ids

# === main build with batching ===
def main():
    os.makedirs(CHROMA_DIR, exist_ok=True)
    print("Loading chunks...")
    docs, metas, ids = load_chunks(CHUNKS_DIR)
    total = len(docs)
    print(f"Loaded {total} chunks")
    if total == 0:
        print("No chunks found. Exiting.")
        return

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Recreate collection cleanly
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
        
    collection = client.create_collection(
        name=COLLECTION_NAME, 
        embedding_function=embedding_fn
    )

    # Adding documents in batches
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        
        # FIX: Chroma handles the embedding internally. 
        # Just pass documents, and the collection will use embedding_fn automatically
        collection.add(
            documents=docs[start:end],
            metadatas=metas[start:end],
            ids=ids[start:end]
        )
        
        if end % PROGRESS_EVERY == 0 or end == total:
            print(f"Processed {end}/{total} chunks")

    print("DONE. Total vectors:", collection.count())
    print("Chroma directory:", CHROMA_DIR)

if __name__ == "__main__":
    main()


