"""
streamlit_final_fixed_parser.py

Final corrected app:
- Router LLM call returns JSON (decision + subqueries). Parser strips code fences and extracts JSON.
- If JSON invalid or missing subqueries for a 'complex' decision, system FALLS BACK to SIMPLE (no heuristics).
- At most 4 subqueries, and uses exactly the number LLM returned (no padding).
- All LLM prompts/responses saved untruncated into a single human-readable .txt log.
- Streamlit shows only the final answer and a tiny low-opacity filename at the bottom.
"""

import os
import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
import requests
import streamlit as st
import chromadb

# New imports for uploader
import subprocess
import shutil
import time

# --- session state initialization (put near the top, after imports) ---
if "is_searching" not in st.session_state:
    st.session_state["is_searching"] = False

if "final_answer" not in st.session_state:
    st.session_state["final_answer"] = None

if "last_log_path" not in st.session_state:
    st.session_state["last_log_path"] = None

if "upload_chroma_dir" not in st.session_state:
    st.session_state["upload_chroma_dir"] = None

if "upload_collection" not in st.session_state:
    st.session_state["upload_collection"] = None

# optional: current_upload metadata used by sidebar uploader
if "current_upload" not in st.session_state:
    st.session_state["current_upload"] = None



# ===========================
# CONFIG 
# ===========================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "xiaomi/mimo-v2-flash:free")

# ChromaDB persistent folder 
GLOBAL_CHROMA_DIR = Path(
    r"C:\Users\GANNOJU SHAHSANK\Downloads\MAANG_PYTHON\GenAI\Financial_rag_bot\rag_json_approach\chromadb_vectors\global"
)
GLOBAL_COLLECTION = "global_chunks"

# Retrieval sizes
TOP_K_SIMPLE = 50      # for SIMPLE path retrieval
TOP_K_PER_SUB = 50     # per-subquery retrieval

# Logging directory (single .txt per query)
LOGS_BASE_DIR = Path(
    r"C:\Users\GANNOJU SHAHSANK\Downloads\MAANG_PYTHON\GenAI\Financial_rag_bot\rag_json_approach\logs"
)
LOGS_BASE_DIR.mkdir(parents=True, exist_ok=True)

# ===========================
# UTILITIES
# ===========================
def now_ts():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def short_slug(text: str, max_len: int = 40):
    s = " ".join(text.split())
    s = s[:max_len]
    s = "".join(c if c.isalnum() else "_" for c in s).strip("_")
    return s if s else "q"

def make_log_paths(query: str):
    qid = f"{now_ts()}_{hashlib.sha1(query.encode('utf-8')).hexdigest()[:8]}"
    slug = short_slug(query, max_len=30)
    txt_name = f"{qid}_{slug}.txt"
    return qid, LOGS_BASE_DIR / txt_name

def safe_write_text(path: Path, text: str):
    path.write_text(text, encoding="utf-8")

# ===========================
# LLM CALL (OpenRouter)
# ===========================
def call_llm_openrouter(prompt: str, timeout: int = 40) -> str:
    if not OPENROUTER_API_KEY:
        return "ERROR: OPENROUTER_API_KEY not set in environment."
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        resp.raise_for_status()
        j = resp.json()
        return j["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR_CALLING_LLM: {str(e)}"

# ===========================
# Robust router JSON extraction
# ===========================
def extract_json_from_text(text: str):
    """
    Attempts to extract a JSON object from the LLM text.
    Strategy (in order):
    1) Trim and try json.loads(text) directly.
    2) Strip common fenced codeblocks (```json ... ``` or ``` ... ```) and try again.
    3) Find the first '{' and last '}' and try to parse that substring.
    If none succeed, raise ValueError.
    """
    if not isinstance(text, str):
        raise ValueError("router response not a string")

    txt = text.strip()

    # direct try
    try:
        return json.loads(txt)
    except Exception:
        pass

    # strip common fences like ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(r"^```(?:json)?\s*(.*)\s*```$", re.DOTALL | re.IGNORECASE)
    m = fence_pattern.search(txt)
    if m:
        inner = m.group(1).strip()
        try:
            return json.loads(inner)
        except Exception:
            pass

    # fallback: extract first {...} block (best-effort)
    first = txt.find("{")
    last = txt.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = txt[first:last + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError("No valid JSON found in router response")

# ===========================
# LOG BUILDING (NO TRUNCATION)
# ===========================
def build_full_text_log(qid: str, query: str, decision: str, llm_calls: list) -> str:
    lines = []
    lines.append("=" * 100)
    lines.append("QUERY")
    lines.append("=" * 100)
    lines.append(query)
    lines.append("")
    lines.append(f"Time (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"QID: {qid}")
    lines.append(f"Decision (router): {decision}")
    lines.append("=" * 100)
    lines.append("LLM CALLS (in order)")
    lines.append("=" * 100)
    for idx, call in enumerate(llm_calls, start=1):
        lines.append(f"LLM CALL {idx}: {call.get('type','unknown')}")
        lines.append("-" * 80)
        lines.append("PROMPT:")
        lines.append(call.get("prompt",""))
        lines.append("")
        lines.append("RESPONSE:")
        lines.append(call.get("response",""))
        lines.append("")
        lines.append("=" * 100)
    lines.append("END OF LOG")
    lines.append("=" * 100)
    return "\n".join(lines)

# ===========================
# CORE ORCHESTRATOR (single router+planner call)
# ===========================
def process_query_and_log(query: str, collection) -> tuple:
    qid, txt_path = make_log_paths(query)
    llm_calls = []

    # Router+planner: decide and produce minimal subqueries (<=4)
    router_prompt = (
        "You are a router and planner.\n\n"
        "Task:\n"
        "1) Decide whether the user's query is SIMPLE or COMPLEX.\n"
        "   - SIMPLE: can be answered with a single retrieval + answer.\n"
        "   - COMPLEX: needs multiple independent sub-questions.\n"
        "2) If COMPLEX, produce the MINIMUM number of independent sub-questions required (no more than 4). "
        "Do NOT pad; prefer fewer sub-questions. Each sub-question must be necessary and self-contained.\n\n"
        "Return STRICT JSON only with these keys: {\"decision\": \"simple\" | \"complex\", \"subqueries\": [ ... ]}\n"
        "- If decision is \"simple\", set \"subqueries\": []\n"
        "- If decision is \"complex\", include only the needed subqueries (1..4)\n\n"
        "User query:\n"
        f"{query}\n"
    )

    router_response = call_llm_openrouter(router_prompt)
    llm_calls.append({"type": "router_planner", "prompt": router_prompt, "response": router_response})

    # Parse router response strictly. If parsing fails, fallback to SIMPLE.
    decision = "simple"
    subqueries = []

    try:
        parsed = extract_json_from_text(router_response)
        # extract decision
        raw_decision = parsed.get("decision", "simple")
        if not isinstance(raw_decision, str):
            raise ValueError("decision not a string")
        decision = raw_decision.strip().lower()

        # extract subqueries only if complex
        if decision == "complex":
            raw_subs = parsed.get("subqueries", [])
            if not isinstance(raw_subs, list) or not raw_subs:
                # missing or invalid → downgrade to SIMPLE (strict fail-safe)
                decision = "simple"
                subqueries = []
            else:
                # sanitize and cap
                subqueries = [s.strip() for s in raw_subs if isinstance(s, str) and s.strip()]
                subqueries = subqueries[:4]
                if not subqueries:
                    decision = "simple"

    except Exception:
        # Strict fail-safe: treat as SIMPLE whenever router output isn't valid JSON per contract
        decision = "simple"
        subqueries = []

    # SIMPLE path
    if decision == "simple":
        try:
            res = collection.query(query_texts=[query], n_results=TOP_K_SIMPLE, include=["documents"])
            docs = res["documents"][0]
        except Exception:
            docs = []

        answer_prompt = (
            "Answer the user's question using the context below. Be concise but complete.\n\n"
            "CONTEXT:\n" + ("\n\n".join(docs) if docs else "") + "\n\n"
            "QUESTION:\n" + query + "\n"
        )
        answer_response = call_llm_openrouter(answer_prompt)
        llm_calls.append({"type": "simple_answer", "prompt": answer_prompt, "response": answer_response})

        # Save full text log
        full_text = build_full_text_log(qid, query, decision, llm_calls)
        safe_write_text(txt_path, full_text)
        return answer_response, txt_path

    # COMPLEX path (subqueries guaranteed non-empty and <=4)
    sub_answers = []
    for i, sq in enumerate(subqueries, start=1):
        try:
            r = collection.query(query_texts=[sq], n_results=TOP_K_PER_SUB, include=["documents"])
            docs = r["documents"][0]
        except Exception:
            docs = []

        sq_prompt = (
            f"Answer this sub-question using the context below. Keep the answer focused and explicit.\n\n"
            "CONTEXT:\n" + ("\n\n".join(docs) if docs else "") + "\n\n"
            f"SUB-QUESTION:\n{sq}\n"
        )
        sq_response = call_llm_openrouter(sq_prompt)
        llm_calls.append({"type": f"subquery_answer_{i}", "prompt": sq_prompt, "response": sq_response})
        sub_answers.append({"subquery": sq, "answer": sq_response})

    # Final synthesis: NO retrieval, only combine sub-answers
    synth_parts = [
        "You are given answers to sub-questions. Combine them into ONE coherent final answer.",
        "Be explicit about assumptions.",
        "",
        "Original question:",
        query,
        "",
        "Sub-answers:"
    ]
    for idx, s in enumerate(sub_answers, start=1):
        synth_parts.append(f"Sub-question {idx}: {s['subquery']}")
        synth_parts.append("Answer:")
        synth_parts.append(s["answer"])
        synth_parts.append("")

    synth_prompt = "\n".join(synth_parts)
    synth_response = call_llm_openrouter(synth_prompt)
    llm_calls.append({"type": "final_synthesis", "prompt": synth_prompt, "response": synth_response})

    # Save full text log
    full_text = build_full_text_log(qid, query, decision, llm_calls)
    safe_write_text(txt_path, full_text)
    return synth_response, txt_path

# ===========================
# STREAMLIT UI
# ===========================
st.set_page_config(page_title="RAG Router (final parser)", layout="wide",page_icon="📊")
st.title("📊 Financial RAG — Robust parser")

#===========================================================================================================================
#     file uploader change (Modified code)
#==========================================================================================================================
# -----------------------------
# Compact uploader in the sidebar (replace the top-of-page uploader with this)
# -----------------------------
# ensure session keys exist
if "upload_chroma_dir" not in st.session_state:
    st.session_state["upload_chroma_dir"] = None
if "upload_collection" not in st.session_state:
    st.session_state["upload_collection"] = None
if "last_upload_path" not in st.session_state:
    st.session_state["last_upload_path"] = None

# Sidebar header (small, compact)
st.sidebar.markdown("<div style='font-size:13px;font-weight:600;margin-bottom:6px'>Upload (isolated index)</div>", unsafe_allow_html=True)

# Put uploader UI inside a collapsed expander to reduce clutter
with st.sidebar.expander("Upload Excel (click to open)", expanded=False):
    # explicit absolute path input for uploads root
    default_uploads_root = str(Path.home() / "rag_uploads")
    uploads_root_input = st.text_input("Uploads root (absolute)", value=default_uploads_root, key="uploads_root_input")
    uploads_root = Path(uploads_root_input).expanduser()
    uploads_root.mkdir(parents=True, exist_ok=True)

    uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"], key="sidebar_uploader")
    show_logs = st.checkbox("Show live logs", value=True, key="sidebar_show_logs")

    st.markdown("<small style='color:gray'>Files saved under the uploads root. Each upload is isolated and will not mix with the global DB.</small>", unsafe_allow_html=True)

    # If file selected, show a small action button to start indexing (avoids accidental runs)
    if uploaded_file:
        if st.button("Start indexing this upload", key="sidebar_index_btn"):
            # Create explicit per-upload directories (same logic as before)
            h = hashlib.sha1(uploaded_file.name.encode("utf-8")).hexdigest()[:8]
            upload_id = f"{uploaded_file.name.rsplit('.',1)[0]}_{h}"
            upload_dir = uploads_root / upload_id

            excel_dir = upload_dir / "excel"
            chunks_dir = upload_dir / "chunks"
            chroma_dir = upload_dir / "chroma"
            scripts_dir = upload_dir / "scripts"

            for d in (excel_dir, chunks_dir, chroma_dir, scripts_dir):
                d.mkdir(parents=True, exist_ok=True)

            excel_path = excel_dir / uploaded_file.name
            with open(excel_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            st.sidebar.success(f"Saved to: {str(excel_path)}")
            st.sidebar.info("Indexing started. Open this expander to view logs.")

            # Save minimal upload metadata to session so other parts of app can use it
            st.session_state["current_upload"] = {
                "upload_id": upload_id,
                "upload_dir": str(upload_dir),
                "excel_dir": str(excel_dir),
                "chunks_dir": str(chunks_dir),
                "chroma_dir": str(chroma_dir),
                "scripts_dir": str(scripts_dir),
                "uploaded_filename": uploaded_file.name,
                "show_logs": show_logs
            }

            # The actual indexing run (copy+patch scripts + subprocess streaming) should be
            # triggered here exactly the same as your previous logic. To keep this block compact,
            # call a helper function you already have (e.g. run_index_for_upload(upload_meta)).
            # Example:
            try:
                run_index_for_upload(st.session_state["current_upload"])
            except Exception as e:
                st.sidebar.error(f"Indexing failed: {e}")
            else:
                st.sidebar.success("Indexing finished.")
                # save chroma path & collection name for queries
                st.session_state["upload_chroma_dir"] = str(chroma_dir)
                st.session_state["upload_collection"] = f"upload_{upload_id}"
                st.session_state["last_upload_path"] = str(upload_dir)


# ============================================================================================================
# Query UI + handling
query = st.text_area("Enter your query", height=140, key="query_input")

# Show Search button ONLY if not already searching
if not st.session_state["is_searching"]:
    if st.button("Search", type="primary") and query.strip():
        st.session_state["is_searching"] = True
        st.rerun()

else:
    st.info("Processing your query...")

if st.session_state["is_searching"] and query.strip():
    with st.spinner("Processing..."):
        # choose collection (uploaded or global)
        if st.session_state.get("upload_chroma_dir") and st.session_state.get("upload_collection"):
            client = chromadb.PersistentClient(path=str(st.session_state["upload_chroma_dir"]))
            collection = client.get_collection(st.session_state["upload_collection"])
        else:
            client = chromadb.PersistentClient(path=str(GLOBAL_CHROMA_DIR))
            collection = client.get_collection(GLOBAL_COLLECTION)

        try:
            final_answer, txt_log_path = process_query_and_log(query.strip(), collection)
        except Exception as e:
            st.error(f"Error while processing query: {e}")
            final_answer, txt_log_path = None, None

        # persist results
        st.session_state["final_answer"] = final_answer
        st.session_state["last_log_path"] = str(txt_log_path) if txt_log_path else None

        # IMPORTANT: reset searching flag
        st.session_state["is_searching"] = False
        st.rerun()


# Display final answer only when available in session_state
if st.session_state.get("final_answer"):
    st.subheader("Final Answer")
    st.markdown(st.session_state["final_answer"])

    # Tiny low-opacity filename (if available)
    if st.session_state.get("last_log_path"):
        try:
            logfile_name = Path(st.session_state["last_log_path"]).name
        except Exception:
            logfile_name = st.session_state["last_log_path"]
        st.markdown(
            f"<div style='font-size:10px;opacity:0.35'>Log file: {logfile_name}</div>",
            unsafe_allow_html=True,
        )






    
    
# streamlit run "C:\Users\GANNOJU SHAHSANK\Downloads\MAANG_PYTHON\GenAI\Financial_rag_bot\rag_json_approach\new_streamlit_wth_node.py"    

# compare nav per unit for Motilal Oswal Balanced Advantage Fund and Motilal Oswal Midcap Fund for last 5 years

# compare top allocations for Motilal Oswal BSE 1000 Index Fund and Motilal Oswal Ultra Short Term Fund 