# Dockerfile (multi-stage: vector and streamlit)
# Build target: "vector" (contains baked Chroma DB and vector service)
# Build target: "streamlit" (Streamlit UI)

####################
# VECTOR STAGE
####################
FROM python:3.12-slim AS vector

WORKDIR /vector_service

# minimal system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

# inline python deps for vector service (no external requirements file)
RUN pip install --no-cache-dir \
    flask \
    chromadb \
    sentence-transformers \
    openpyxl \
    numpy \
    pandas

# copy the vector service code (expects vector_service.py in repo)
COPY vector_service.py /vector_service/vector_service.py

# Copy your baked Chroma DB into the image (read-only inside image)
# Make sure your local chromadb_vectors/global exists before building
COPY chromadb_vectors/global /data/chromadb_vectors/global

ENV CHROMA_DIR=/data/chromadb_vectors
EXPOSE 8000

# default command for this target (for testing)
CMD ["python", "/vector_service/vector_service.py"]


####################
# STREAMLIT STAGE
####################
FROM python:3.12-slim AS streamlit

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

# inline python deps for streamlit UI
RUN pip install --no-cache-dir \
    streamlit \
    requests \
    openpyxl \
    numpy \
    pandas \
    chromadb

# copy project files (app scripts etc.)
COPY . /app

# small entrypoint script to choose which Streamlit file to run via env var
RUN printf '#!/bin/sh\nAPP="${STREAMLIT_APP:-new_streamlit_wth_node.py}"\nexec streamlit run "$APP" --server.port=8501 --server.headless=true\n' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

ENV STREAMLIT_APP=new_streamlit_wth_node.py
ENV VECTOR_STORE_URL=http://vector-store:8000

EXPOSE 8501
ENTRYPOINT ["/app/entrypoint.sh"]

