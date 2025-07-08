# Multi-stage Docker build for uv build backend Python project
# Optimized for Unraid environment testing with multi-platform support

# Stage 1: Build dependencies and compile
FROM --platform=$BUILDPLATFORM python:3.13-slim-bookworm AS builder

# Build arguments for multi-platform builds
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image (supports multi-platform)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create app directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies in a separate layer for better caching
# Use --no-install-project to cache dependencies separately
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --compile-bytecode

# Copy source code
COPY src/ ./src/
COPY README.md LICENSE ./

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --compile-bytecode

# Stage 2: Runtime image
FROM --platform=$TARGETPLATFORM python:3.13-slim-bookworm AS runtime

# Build arguments for multi-platform builds
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy uv for runtime use
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-root user for security
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home app

# Create app directory
WORKDIR /app

# Copy the virtual environment from builder stage
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy project files
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/pyproject.toml /app/uv.lock /app/README.md /app/LICENSE ./

# Create configs directory for mounting
RUN mkdir -p /app/configs && chown app:app /app/configs

# Switch to non-root user
USER app

# Ensure the virtual environment is activated
ENV PATH="/app/.venv/bin:$PATH"

# Set Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mover_status; print('OK')" || exit 1

# Default command - can be overridden
CMD ["python", "-m", "mover_status", "--help"]

# Stage 3: Development image (optional)
FROM runtime AS development

# Install development dependencies
RUN uv sync --locked --group dev --compile-bytecode

# Expose common development ports
EXPOSE 8000

# Override entrypoint for development
CMD ["bash"]