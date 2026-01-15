import os
import json
import tempfile
import requests
import chromadb
from pathlib import Path
import streamlit as st
from chromadb.utils import embedding_functions

# === portable paths & config ===
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR    = Path(os.getenv("DATA_DIR", BASE_DIR / "Data"))
CHUNKS_DIR  = Path(os.getenv("CHUNKS_DIR", BASE_DIR / "chunks" / "previous_chunks"))
CHROMA_DIR  = Path(os.getenv("CHROMA_DIR", BASE_DIR / "chromadb_vectors" / "global"))
UPLOADS_CHUNKS = Path(os.getenv("CHUNKS_DIR", BASE_DIR / "chunks" / "uploaded_chunks"))
LOGS_DIR    = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
UPLOADED_VECTOR_DB  =Path(os.getenv("CHROMA_DIR", BASE_DIR / "chromadb_vectors" / "uploaded"))

for d in (DATA_DIR, CHUNKS_DIR, CHROMA_DIR, UPLOADS_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# ===============================
# CONFIG & PATHS
# ===============================
GLOBAL_CHROMA_DIR = CHROMA_DIR 
GLOBAL_COLLECTION = "global_chunks"
UPLOADED_CHUNKS_ROOT = UPLOADS_CHUNKS
UPLOADED_CHROMA_ROOT = UPLOADED_VECTOR_DB

TOP_K = 50
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "xiaomi/mimo-v2-flash:free"


# =======================================================================================================================================
# DEBUG CONFIG (REMOVE AFTER DEBUGGING)
# =====================================================================================================================================
DEBUG_MODE = True
# Replace with your actual directory path
DEBUG_DIR = LOGS_DIR 

def save_prompt_to_file(prompt_content):
    """Saves the current prompt to a text file in the specified directory."""
    if not DEBUG_MODE:
        return
    
    # Ensure directory exists
    log_path = Path(DEBUG_DIR)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Save as a fixed filename or use timestamps for history
    file_path = log_path / "last_llm_prompt.txt"
    file_path.write_text(prompt_content, encoding="utf-8")

#========================================================================================================================================


# ===============================
# UI STYLE (SMALL FONTS)
# ===============================
st.markdown("""
    <style>
    .answer-font {
        font-size: 18px !important;
        color: #333333;
        line-height: 1.5;
    }
    .chunk-font {
        font-size: 12px !important;
        color: #666666;
    }
    </style>
    """, unsafe_allow_html=True)


embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L12-v2")

def chunk_to_markdown(chunk: dict) -> str:
    lines = []
    title_parts = []
    if chunk.get("global_header"): title_parts.append(chunk["global_header"][-1])
    if chunk.get("subheaders"):
        sh = chunk["subheaders"]
        title_parts.append(sh[0] if isinstance(sh, list) else sh)
    if title_parts:
        t = " | ".join(title_parts)
        lines.append(f"### {t if len(t) <= 120 else t[:117] + '...'}")
    for k, v in list(chunk.get("data", {}).items())[:12]:
        lines.append(f"- **{k}**: {v}")
    return "\n".join(lines)

def index_uploaded_chunks(chunks_dir, chroma_dir, collection_name):
    docs, metas, ids = [], [], []
    for fp in Path(chunks_dir).rglob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                c = json.load(f)
            md = chunk_to_markdown(c)
            if not md: continue
            docs.append(md)
            ids.append(f"{c.get('source_file')}__{c.get('sheet_name')}__row_{c.get('excel_row_number')}")
            metas.append({"source_file": str(c.get("source_file")), "sheet_name": str(c.get("sheet_name")), "excel_row_number": str(c.get("excel_row_number"))})
        except: continue
    if not docs: return None
    os.makedirs(chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    try: client.delete_collection(collection_name)
    except: pass
    collection = client.create_collection(name=collection_name, embedding_function=embedding_fn)
    collection.add(documents=docs, metadatas=metas, ids=ids)
    return collection

# ===============================
# LLM CALL (ADJUSTED PROMPT FOR 2026)
# ===============================
def call_llm(query, retrieved_docs):
    # Send slightly more context for a "bigger" answer
    context = "\n\n---\n\n".join(retrieved_docs[:12])
    
    # Prompt adjusted to ask for a descriptive paragraph + key stats
    prompt = f"""
Using the financial context below, provide a detailed answer based on question.

Context:
{context}

Question:
{query}
"""
    # --- DEBUG CALL ---===================================================================================================
    save_prompt_to_file(prompt)
    # ------------------================================================================================================
    
    try:
        r = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e: return f"Error calling LLM: {str(e)}"

# ===============================
# STREAMLIT UI
# ===============================
st.set_page_config(layout="wide", page_title="Financial RAG",  page_icon="📊")
st.title("📊 Financial RAG")

with st.sidebar:
    st.header("Upload Data")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])

uploaded_collection = None
if uploaded_file:
    file_stem = Path(uploaded_file.name).stem
    up_chunks_dir = os.path.join(UPLOADED_CHUNKS_ROOT, file_stem)
    up_chroma_dir = os.path.join(UPLOADED_CHROMA_ROOT, file_stem)
    os.makedirs(up_chunks_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    with st.spinner("Processing file..."):
        import chunker
        old_out = chunker.OUTPUT_CHUNKS_DIR
        chunker.OUTPUT_CHUNKS_DIR = up_chunks_dir
        chunker.process_excel_file(tmp_path)
        chunker.OUTPUT_CHUNKS_DIR = old_out
        uploaded_collection = index_uploaded_chunks(up_chunks_dir, up_chroma_dir, f"uploaded_{file_stem}")
    st.sidebar.success("Index Ready")

query = st.text_input("Ask a question about the financial data:")

if st.button("Search") and query:
    # 1. Searching Loader Symbol
    with st.spinner("Analyzing data and generating answer..."):
        if uploaded_collection:
            collection = uploaded_collection
            label = f"Uploaded: {uploaded_file.name}"
        else:
            client = chromadb.PersistentClient(path=GLOBAL_CHROMA_DIR)
            collection = client.get_collection(GLOBAL_COLLECTION)
            label = "Global"

        results = collection.query(query_texts=[query], n_results=TOP_K, include=["documents", "metadatas"])
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        answer = call_llm(query, docs)

    # 2. Small Answer Display
    st.markdown(f"##### 🧠 Answer ({label})")
    st.markdown(f'<div class="answer-font">{answer}</div>', unsafe_allow_html=True)

    # 3. Small Scrollable Chunks
    st.divider()
    with st.expander(f"📚 View All {len(docs)} Retrieved Chunks", expanded=False):
        full_md = ""
        for i, (text, meta) in enumerate(zip(docs, metas)):
            full_md += f"**[{i+1}] Source: {meta.get('source_file')}**\n\n{text}\n\n---\n\n"
        
        st.markdown(f'<div class="chunk-font">{full_md}</div>', unsafe_allow_html=True)













# compare nav per unit for Motilal Oswal Balanced Advantage Fund and Motilal Oswal Midcap Fund for last 5 years

# compare top allocations for Motilal Oswal BSE 1000 Index Fund and Motilal Oswal Ultra Short Term Fund 