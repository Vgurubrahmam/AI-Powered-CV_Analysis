# =============================================================================
#  Stage 1: Builder — install dependencies
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =============================================================================
#  Stage 2: Runtime — lean final image
# =============================================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install/lib /usr/local/lib
COPY --from=builder /install/bin /usr/local/bin

# Download spaCy model
RUN python -m spacy download en_core_web_sm --no-deps

# Create non-root user
RUN useradd --no-create-home --uid 1001 appuser && \
    mkdir -p /app /tmp/ats-uploads && \
    chown -R appuser:appuser /app /tmp/ats-uploads

# Copy application code
COPY --chown=appuser:appuser ./app ./app

USER appuser

EXPOSE 8000

# Default: run API server
# Override CMD to run Celery worker:
#   CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "-Q", "parsing,embeddings,llm,default"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info"]
