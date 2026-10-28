# ==============================================================================
# Multi-Stage Dockerfile for Bangalore Hangout Recommender
# Author: Ayush Bomanwar (PRN: 1262243601)
# Course: TYCSE — Cloud Computing and DevOps (CCA 2)
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install compilation tools needed for C-extensions in scikit-learn / numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into /install prefix for clean multi-stage extraction
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: Hardened, Ultra-Lightweight Production Runner
FROM python:3.11-slim AS runner

# Install curl for container healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled dependencies from builder stage
COPY --from=builder /install /usr/local

# Security: Create and switch to unprivileged non-root user (appuser, UID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Copy application assets and datasets with non-root ownership
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup data/ ./data/
COPY --chown=appuser:appgroup web/ ./web/
COPY --chown=appuser:appgroup server.py ./
COPY --chown=appuser:appgroup version.py ./

# Enforce non-root execution
USER appuser

# Expose internal application HTTP port
EXPOSE 8000

# Container-level Liveness/Readiness Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production WSGI/ASGI entrypoint
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
