# METAENGINE Phase 66 — Docker + Deployment

# Dockerfile for MetaEngine API Server + Core Engine
# Uses Python 3.12 slim image
FROM python:3.12-slim

LABEL maintainer="MetaEngine"
LABEL description="Constitutionally-safe self-improving AI system"
LABEL version="2.3.0-alpha.1"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy MetaEngine source
COPY METAENGINE_SLICE3_RESTORED/metaengine/ /app/metaengine/
COPY METAENGINE_SLICE3_RESTORED/config/ /app/config/
COPY METAENGINE_SLICE3_RESTORED/prisma/ /app/prisma/
COPY METAENGINE_SLICE3_RESTORED/devfabric/ /app/devfabric/
COPY METAENGINE_SLICE3_RESTORED/reference-vault/ /app/reference-vault/
COPY METAENGINE_SLICE3_RESTORED/schemas/ /app/schemas/
COPY METAENGINE_SLICE3_RESTORED/storage/ /app/storage/
COPY METAENGINE_SLICE3_RESTORED/tests/ /app/tests/
COPY METAENGINE_SLICE3_RESTORED/pyproject.toml /app/
COPY METAENGINE_SLICE3_RESTORED/pytest.ini /app/
COPY METAENGINE_SLICE3_RESTORED/.env /app/.env

# Install Python dependencies
RUN pip install --no-cache-dir \
    pytest \
    httpx \
    pypdf

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Run API server
CMD ["python", "-m", "metaengine.api_server", "--root", "/app", "--port", "8080"]
