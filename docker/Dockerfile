# Peptide Optimization Service
# ============================
# Multi-stage build for optimized Docker image

FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy package files
COPY pyproject.toml ./
COPY src/ ./src/

# Build wheel
RUN pip install build && python -m build --wheel

# ============================
# Runtime stage
# ============================
FROM python:3.11-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy wheel from builder
COPY --from=builder /build/dist/*.whl ./

# Install application
RUN pip install --no-cache-dir *.whl && rm -f *.whl

# Copy additional files
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
COPY vendor/ProteinMPNN/ ./vendor/ProteinMPNN/
COPY src/peptide_opt/config/settings.yaml ./config/settings.yaml

# Set permissions
RUN chmod +x /docker-entrypoint.sh && \
    chown -R appuser:appuser /app

# Create data directories
RUN mkdir -p /app/data/input /app/data/output /app/logs && \
    chown -R appuser:appuser /app/data /app/logs

USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["serve"]
