# Build stage with uv binary
FROM ghcr.io/astral-sh/uv:latest AS uv_bin
FROM python:3.14-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8000 \
    PATH="/app/.venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Install system dependencies (curl for container healthcheck, gcc/libpq-dev for DB drivers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from Astral image
COPY --from=uv_bin /uv /bin/uv

# Create a non-privileged user
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Install dependencies using uv (cached layer)
COPY pyproject.toml .
RUN uv sync --no-install-project --no-dev

# Copy application source code
COPY --chown=appuser:appgroup . .

# Complete project installation with uv
RUN uv sync --no-dev

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check instruction
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Start Uvicorn production server using uv run
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
