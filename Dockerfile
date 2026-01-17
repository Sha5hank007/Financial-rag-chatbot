FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# 🔴 COPY YOUR VECTOR DB INTO THE IMAGE
COPY chromadb_vectors/global /app/chromadb_vectors/global

# Tell the app where the DB is
ENV CHROMA_DIR=/app/chromadb_vectors

EXPOSE 8501

# Run the multi-step Streamlit app by default
CMD ["streamlit", "run", "new_streamlit_wth_node.py", "--server.port=8501", "--server.headless=true"]


