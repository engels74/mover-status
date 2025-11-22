# syntax=docker/dockerfile:1

# Multi-stage build for mover-status (Unraid monitoring application)
# Based on uv Docker best practices: https://docs.astral.sh/uv/guides/integration/docker/

# ============================================================================
# Stage 1: Builder - Install dependencies using uv
# ============================================================================
FROM python:3.14-slim-bookworm AS builder

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies in a virtual environment
# --frozen: Use exact versions from uv.lock (no resolution)
# --no-dev: Skip development dependencies
# --no-install-project: Only install deps, not the package itself yet
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ ./src/

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.14-slim-bookworm

# Install runtime dependencies (if any needed beyond Python)
# Note: Most dependencies are Python packages already installed
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Required for process inspection (ps command in healthcheck)
        procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# UID 1000 is standard for first user on most Linux systems (including Unraid)
RUN groupadd --gid 1000 mover-status && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home mover-status

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=mover-status:mover-status /app/.venv /app/.venv

# Copy source code from builder
COPY --from=builder --chown=mover-status:mover-status /app/src /app/src

# Copy uv binary for runtime execution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Place venv binaries in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create tmpfs mount point for runtime temp files
# (Required since we'll run with read-only root filesystem)
RUN mkdir -p /tmp && chown mover-status:mover-status /tmp

# Switch to non-root user
USER mover-status:mover-status

# Volume mount points (documentation only - actual mounts in docker-compose.yml)
# REQUIRED mounts for Unraid integration:
# - /var/run:/var/run:ro          (PID file monitoring)
# - /mnt/cache:/mnt/cache:ro      (disk usage tracking)
# - /proc:/proc:ro                (process validation)
# - ./config:/app/config:ro       (YAML configuration files)
#
# OPTIONAL mounts:
# - /dev/log:/dev/log:rw          (syslog integration, can use --no-syslog if unavailable)
VOLUME ["/app/config"]

# Expose no ports (outbound-only application)

# Health check: Verify process is running
# Note: This just checks the container process, not mover monitoring status
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD ps aux | grep -v grep | grep -q mover-status || exit 1

# Default command: Run mover-status application
# Override in docker-compose.yml or docker run to add flags like --dry-run
ENTRYPOINT ["uv", "run", "mover-status"]

# Default arguments (can be overridden)
# Example overrides:
#   docker run mover-status --dry-run
#   docker run mover-status --no-syslog
#   docker run mover-status --log-level DEBUG
CMD []
