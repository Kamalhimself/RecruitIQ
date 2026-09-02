# ==============================================================================
# RecruitIQ Backend - Production Container
# Multi-stage secure build with spaCy NLP and headless Google API support
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
RUN /install/bin/python -m spacy download en_core_web_sm

# ------------------------------------------------------------------------------
# Final Runtime Stage
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed wheels and spaCy models from builder stage
COPY --from=builder /install /usr/local

# Security: Create non-privileged service user
RUN groupadd -g 1001 recruitiq && \
    useradd -u 1001 -g recruitiq -s /bin/bash -m recruitiq

# Copy application source code
COPY . .

# Set permissions for chroma_data and runtime dirs
RUN mkdir -p chroma_data && \
    chown -R recruitiq:recruitiq /app

USER recruitiq

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADLESS_MODE=true \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
