# Financial RAG Chatbot (Excel → ChromaDB → LLM)

This project is a Retrieval-Augmented Generation (RAG) system that allows users to query financial Excel files using natural language.

The system chunks Excel data, stores embeddings in ChromaDB, retrieves relevant rows, and generates answers using an LLM.

---

## What this project does

- Parses multi-sheet financial Excel files
- Chunks rows with structural context (headers, subheaders)
- Builds vector embeddings using SentenceTransformers
- Stores vectors in ChromaDB (local, persistent)
- Answers user queries using retrieval + LLM synthesis
- Supports both simple and complex (multi-step) queries

---

## Tech stack

- **Python 3.12.7**
- **Streamlit** (UI)
- **ChromaDB** (vector database)
- **SentenceTransformers** (`all-MiniLM-L12-v2`)
- **OpenRouter** (LLM API)
- **openpyxl / numpy / pandas**

-----------------------------------------------------------------------------------------------------------------

## Streamlit applications

This repository contains two Streamlit entry points.

### 1. streamlit_app.py — Single-step retrieval

Use this app for simple, direct questions.

How it works:

- The user query is embedded once
- A single similarity search is performed on ChromaDB
- Top-K relevant chunks are retrieved
- The LLM generates an answer using only those chunks

Characteristics:

- Faster
- Fewer LLM calls
- Lower cost
- No query routing or decomposition

### 2. new_streamlit_wth_node.py — Multi-step (router-based) retrieval

Use this app for complex or analytical questions involving funds, portfolios, or comparisons.

How it works:

- A router LLM first classifies the query as simple or complex
- Complex queries are decomposed into focused sub-questions (e.g., fund exposure, asset allocation, maturity profile)
- Each sub-question performs its own vector retrieval from ChromaDB
- Each sub-question is answered independently using retrieved financial rows
- A final synthesis step combines all sub-answers into one coherent response
- All prompts and responses are logged for traceability

Typical use cases:

- Comparing multiple mutual funds
- Analyzing portfolio composition or risk exposure
- Cross-sheet or cross-period financial reasoning

Characteristics:

- Higher accuracy for multi-factor financial queries
- Multiple retrieval and LLM calls
- Higher latency and cost than single-step retrieval.

---

## How to run locally 

1. Clone the repository
   ```bash
   git clone https://github.com/Sha5hank007/Financial-rag-chatbot.git
   cd Financial-rag-chatbot
   ```
