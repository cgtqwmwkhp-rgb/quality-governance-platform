# Build stage — base image pinned by digest for reproducibility
# Digest from Docker Hub tag `3.11-slim-bookworm` manifest (hub.docker.com API, 2026-04-06).
FROM python:3.11-slim-bookworm@sha256:420310dd2ff7895895f0f1f9d15cae5a95dabceb8f1d6b9a23ef33c2c1c542c3 AS builder

WORKDIR /app

# Install build dependencies (no apt-get upgrade — preserves digest-pinned reproducibility)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies (use lockfile for reproducible builds)
COPY requirements.txt requirements.lock* ./
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    if [ -f requirements.lock ]; then \
      pip install --no-cache-dir -r requirements.lock; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

# Production stage
FROM python:3.11-slim-bookworm@sha256:420310dd2ff7895895f0f1f9d15cae5a95dabceb8f1d6b9a23ef33c2c1c542c3 AS production

WORKDIR /app

# Runtime packages + bounded security upgrades (Security Scan / Trivy gate on push to main).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Upgrade system setuptools and wheel to resolve vendored CVEs
RUN pip install --no-cache-dir --upgrade setuptools wheel

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup alembic/ ./alembic/
COPY --chown=appuser:appgroup alembic.ini .
COPY --chown=appuser:appgroup certs/ ./certs/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
