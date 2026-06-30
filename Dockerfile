# RecruitProof — Multi-stage Dockerfile
# ----------------------------------------------------------------------------
# Builds a production image with the Python engine, FastAPI server, embedding
# model pre-cached, and PDF/DOCX extraction tooling.
#
# Build:    docker build -t scrutexity/recruitproof:0.3.0 .
# Run:      docker-compose up -d
# Verify:   curl http://localhost:8000/health
#
# Image size: ~2.1 GB (Python 3.10-slim + torch CPU + sentence-transformers + poppler)

# ============================================================================
# Stage 1: Builder — install Python deps + pre-cache the embedding model
# ============================================================================
FROM python:3.10-slim AS builder

# System deps for PDF/DOCX extraction + compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ make \
        poppler-utils \
        libxml2 libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python deps to a dedicated prefix so we can copy them cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && pip install --no-cache-dir --prefix=/install \
        fastapi==0.128.0 uvicorn[standard]==0.44.0 \
        PyPDF2==3.0.0 python-docx==1.1.0 \
        reportlab==4.4.9 \
        cryptography

# Pre-download the embedding model so the container starts fast on first run
# (~440MB for all-MiniLM-L6-v2). Skipped if HF_HOME is bind-mounted at runtime.
RUN HF_HOME=/build/hf_cache python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# ============================================================================
# Stage 2: Runtime — slim image with only what's needed to run
# ============================================================================
FROM python:3.10-slim AS runtime

# Runtime system deps (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        libxml2 libxslt1-dev \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 recruitproof

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local
# Pre-cached embedding model from builder
COPY --from=builder /build/hf_cache /opt/hf_cache_default

WORKDIR /app

# Copy the source code (everything in the repo root)
COPY --chown=recruitproof:recruitproof . /app

# Create the data directory
RUN mkdir -p /data && chown -R recruitproof:recruitproof /data /app

USER recruitproof

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RECRUITPROOF_DATA_DIR=/data \
    HF_HOME=/data/.hf_cache \
    PATH="/usr/local/bin:${PATH}"

EXPOSE 8000

# Healthcheck — the FastAPI server exposes /health
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Default entrypoint: FastAPI server on port 8000
# Override with `docker run ... python search.py --jd ...` for CLI use
ENTRYPOINT ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
