# RecruitProof — Pilot Executor Docker Image
# ============================================
# Self-contained image for Rudy's one-click pilot.
# Build:   docker build -t scrutexity/recruitproof-pilot:latest -f pilot.Dockerfile .
# Run:     docker compose -f docker-compose.pilot.yml up
#
# Air-gapped by default (network_mode: none in docker-compose).
# All processing happens locally — zero data leaves the machine.

FROM python:3.10-slim

WORKDIR /app

# System deps: PDF parsing, OCR fallback, docx
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        libxml2 libxslt1-dev \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 recruitproof

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        fpdf2 \
        PyPDF2==3.0.0 \
        python-docx==1.1.0 \
        reportlab==4.4.9

# Pre-cache the embedding model so first run is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy the source code
COPY --chown=recruitproof:recruitproof . /app

RUN mkdir -p /data /input /output && chown -R recruitproof:recruitproof /app /data /input /output

USER recruitproof

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RECRUITPROOF_DATA_DIR=/data \
    HF_HOME=/data/.hf_cache

ENTRYPOINT ["python", "pilot_executor.py"]
