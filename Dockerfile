# Optimized multi-stage Docker build for uv build backend Python project
# Size-optimized for Unraid environment testing with multi-platform support
# Target: Reduce image size from ~151MB to ~100-110MB

# Stage 1: Build dependencies and compile
FROM --platform=$BUILDPLATFORM python:3.13-slim-bookworm AS builder

# Build arguments for multi-platform builds
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Install minimal system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies using temporary uv mount (saves ~10-15MB)
# Use --no-install-project to cache dependencies separately
# Use --no-editable for smaller final image
ENV UV_COMPILE_BYTECODE=1
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# Copy source code
COPY src/ ./src/
COPY README.md LICENSE ./

# Install the project itself using temporary uv mount
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Stage 2: Optimized runtime image
FROM python:3.13-slim-bookworm AS runtime

# Build arguments for multi-platform builds
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Install only essential runtime dependencies (removed procps and curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

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
ENV UV_COMPILE_BYTECODE=1

# Health check (simplified without curl dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mover_status; print('OK')" || exit 1

# Default command - can be overridden
CMD ["python", "-m", "mover_status", "--help"]

# Stage 3: Development image (optional)
FROM python:3.13-slim-bookworm AS development

# Build arguments for multi-platform builds
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Install runtime dependencies for development
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

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

# Install development dependencies using temporary uv mount
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group dev

# Switch to non-root user
USER app

# Ensure the virtual environment is activated
ENV PATH="/app/.venv/bin:$PATH"

# Set Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1

# Expose common development ports
EXPOSE 8000

# Override entrypoint for development
CMD ["bash"]