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

- **Python 3.11**
- **Streamlit** (UI)
- **ChromaDB** (vector database)
- **SentenceTransformers** (`all-MiniLM-L12-v2`)
- **OpenRouter** (LLM API)
- **openpyxl / numpy / pandas**

---

## How to run locally (without Docker)

1. Clone the repository
   ```bash
   git clone https://github.com/Sha5hank007/Financial-rag-chatbot.git
   cd Financial-rag-chatbot
   ```
