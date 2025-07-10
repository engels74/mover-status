# Use a Python slim image as the base for the builder stage
FROM --platform=$BUILDPLATFORM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy project files needed for installation
COPY pyproject.toml uv.lock README.md ./

# Copy source code
COPY src/ src/

# Install dependencies into a virtual environment
# Use --no-install-project to separate dependency installation for better caching
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# Now install the project itself in non-editable mode
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Final stage: slim runtime image
FROM --platform=$TARGETPLATFORM python:3.13-slim

# Create a non-root user
RUN useradd -m appuser

# Set working directory
WORKDIR /app

# Copy the virtual environment from builder (no source code)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"

# Switch to non-root user
USER appuser

# Set the entrypoint to the project's CLI
ENTRYPOINT ["mover-status"]
CMD ["--help"] 