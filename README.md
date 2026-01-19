# Financial RAG Chatbot (Dockerized — DB Included)

This repository provides a Retrieval-Augmented Generation (RAG) demo for financial data.
A pre-built ChromaDB vector database is **baked into the Docker image**, so users can run one command and query your data immediately.

## Image (use this)
`shashank123docker/financial-rag-with-db:latest`

## What’s included
- Streamlit UI (two variants included)
  - `new_streamlit_wth_node.py` — Multi-step router + planner (default)
  - `streamlit_app.py` — Single-step retrieval (lighter, faster)
- Pre-built ChromaDB vector DB baked into the image: `chromadb_vectors/global/`
- All required Python runtime and libs baked into the image for demo use

## Quick run (for other users)
1. Install Docker Desktop (Windows/Mac) or Docker Engine (Linux).
2. Pull image:
   ```bash
   docker pull shashank123docker/financial-rag-with-db:latest
   ```
3. Run (default — multi-step app):
   ```bash
   docker run -p 8501:8501 shashank123docker/financial-rag-with-db:latest
   ```
   Open: http://localhost:8501

4. Run the single-step UI instead:
   ```bash
   docker run -p 8501:8501 -e STREAMLIT_APP=streamlit_app.py shashank123docker/financial-rag-with-db:latest
   ```

5. Run read-only mode (extra safety — container filesystem read-only):
   ```bash
   docker run --read-only -p 8501:8501 shashank123docker/financial-rag-with-db:latest
   ```

6. Stop/cleanup:
   ```bash
   docker ps               # find container id
   docker stop <container_id>
   docker rm <container_id>
   ```

## If you want to run vector service separately (NOT required for baked image)
- The image already contains DB and Streamlit configured to use it. This section is optional.
- If you want a separate vector server image, use the two-container approach in repo (vector + streamlit).

## Notes / expectations
- The vector DB in the image is **read-only** — changes inside the running container do not persist.
- To update the DB you must update `chromadb_vectors/global` locally, rebuild the image, and push a new image tag.
- This setup is for demo / sharing only. Not production-grade multi-user storage.

## How to update DB and publish new image (author/dev)
1. Replace `chromadb_vectors/global` locally with updated DB.
2. Commit and push to GitHub:
   ```cmd
   git add -f chromadb_vectors
   git commit -m "update chromadb global DB"
   git push origin main
   ```
3. If you use GitHub Actions CI to build and push images, pushing to `main` triggers the workflow and publishes a new image. If building locally:
   ```bash
   docker build -t shashank123docker/financial-rag-with-db:latest .
   docker login
   docker push shashank123docker/financial-rag-with-db:latest
   ```

## Troubleshooting
- If Docker run fails, check `docker logs <container_id>`.
- If image pull fails: ensure correct image name and internet access.
- If GH Actions build fails: check action logs and adjust Dockerfile (we pinned CPU-only torch during CI to avoid CUDA issues).

--- END README.md CONTENT ---

--- START: COMMANDS YOU (AUTHOR) NEED TO RUN NOW (cmd.exe) ---
REM run these in your project root (Windows CMD)

REM 1) create README.md from the content above (paste manually), or:
notepad README.md
REM (paste the README content and save as README.md)

REM 2) add README and ensure chromadb_vectors is tracked (70MB you said)
git add README.md
git add -f chromadb_vectors

REM 3) commit and push to GitHub main
git commit -m "docs: add README and include baked chromadb_vectors global db"
git push origin main

REM If push fails due to remote changes:
git pull --rebase origin main
git push origin main
--- END: AUTHOR COMMANDS ---

--- START: WHAT OTHERS WILL COPY-RUN (one-shot) ---
REM Others (or you on another machine) paste these commands exactly:

REM Pull the image
docker pull shashank123docker/financial-rag-with-db:latest

REM Run default (multi-step router app)
docker run -p 8501:8501 shashank123docker/financial-rag-with-db:latest

REM OR run the single-step app instead
docker run -p 8501:8501 -e STREAMLIT_APP=streamlit_app.py shashank123docker/financial-rag-with-db:latest

REM Optional: run read-only for extra safety
docker run --read-only -p 8501:8501 shashank123docker/financial-rag-with-db:latest

REM Open browser at:
http://localhost:8501
--- END: OTHERS' COMMANDS ---

--- START: OPTIONAL QUICK NOTES FOR README (if you want to edit)
- To show which Streamlit file runs by default, check Dockerfile ENTRYPOINT or env var STREAMLIT_APP.
- If you want to tag versions:
  docker tag shashank123docker/financial-rag-with-db:latest shashank123docker/financial-rag-with-db:v1
  docker push shashank123docker/financial-rag-with-db:v1
- If you want CI to build new images automatically on push, the repo already contains a GitHub Actions workflow. Ensure Docker Hub secrets are set in repo secrets (DOCKERHUB_USERNAME, DOCKERHUB_TOKEN) with write permission.
--- END OPTIONAL NOTES ---
