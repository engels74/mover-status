# Docker Setup for Unraid Testing

This document provides instructions for running the mover-status application in Docker containers on Unraid systems using pre-built images.

## Quick Start

### 1. Pull Pre-built Images

```bash
# Pull the latest stable release
docker pull ghcr.io/engels74/mover-status:latest

# Pull a specific version
docker pull ghcr.io/engels74/mover-status:v1.0.0

# Images are available for both amd64 and arm64 architectures
```

### 2. Run with Docker Compose (Recommended)

```bash
# Run the production container
docker-compose up -d

# Run the development container
docker-compose --profile dev up -d mover-status-dev

# Run tests
docker-compose --profile test run --rm mover-status-test
```

### 3. Manual Docker Run

```bash
# Production run
docker run -d \
  --name mover-status \
  --restart unless-stopped \
  --network host \
  --pid host \
  -v "$(pwd)/configs:/app/configs:ro" \
  -v "/mnt:/mnt:ro" \
  -v "/var/log:/var/log:ro" \
  -v "/proc:/host/proc:ro" \
  -v "/sys:/host/sys:ro" \
  mover-status

# Development run
docker run -it \
  --name mover-status-dev \
  --network host \
  --pid host \
  -v "$(pwd):/app" \
  -v "/mnt:/mnt:ro" \
  -v "/var/log:/var/log:ro" \
  -v "/proc:/host/proc:ro" \
  -v "/sys:/host/sys:ro" \
  mover-status:dev bash
```

## Docker Architecture

The Dockerfile uses a multi-stage build process:

### Stage 1: Builder
- Uses Python 3.13 slim image
- Installs build dependencies
- Copies uv binary from official image
- Installs Python dependencies with caching
- Compiles bytecode for optimization

### Stage 2: Runtime
- Uses Python 3.13 slim image
- Minimal runtime dependencies
- Non-root user for security
- Health check included
- Optimized for production

### Stage 3: Development
- Extends runtime stage
- Includes development dependencies
- Suitable for testing and debugging

## Unraid-Specific Considerations

### Volume Mounts
The container needs access to Unraid system directories:
- `/mnt` - Unraid array and cache drives
- `/var/log` - System logs
- `/proc` - Process information
- `/sys` - System information

### Network Configuration
- Uses `--network host` to access Unraid network services
- Uses `--pid host` for process monitoring capabilities

### Configuration
- Mount your config files to `/app/configs`
- Supports provider-specific configurations (Discord, Telegram, etc.)

## Commands

### Image Information

```bash
# Check available tags
docker images ghcr.io/engels74/mover-status

# Inspect image details
docker inspect ghcr.io/engels74/mover-status:latest

# Check supported platforms
docker manifest inspect ghcr.io/engels74/mover-status:latest
```

### Running

```bash
# Run application
docker run ghcr.io/engels74/mover-status:latest

# Run with custom config
docker run -v "$(pwd)/configs:/app/configs:ro" ghcr.io/engels74/mover-status:latest

# Run specific command
docker run ghcr.io/engels74/mover-status:latest python -m mover_status --help

# Interactive shell
docker run -it ghcr.io/engels74/mover-status:latest bash
```

### Testing

```bash
# Run all tests
docker-compose --profile test run --rm mover-status-test

# Run specific test
docker run ghcr.io/engels74/mover-status:latest python -m pytest tests/unit/

# Run with coverage
docker run ghcr.io/engels74/mover-status:latest python -m pytest --cov=src/mover_status --cov-report=html
```

### Debugging

```bash
# Enter running container
docker exec -it mover-status bash

# View logs
docker logs mover-status

# Follow logs
docker logs -f mover-status
```

## Optimization Features

### Caching
- UV cache is mounted during build for faster rebuilds
- Dependencies are cached separately from application code
- Bytecode compilation for improved startup performance

### Security
- Non-root user execution
- Minimal base image
- Read-only volume mounts where appropriate

### Multi-architecture Support
Pre-built images support multiple architectures common in Unraid:
- linux/amd64
- linux/arm64

Docker automatically pulls the correct architecture:
```bash
# Automatically selects the right architecture for your system
docker pull ghcr.io/engels74/mover-status:latest
```

## Environment Variables

Set these in your docker-compose.yml or docker run command:

```bash
# Python settings
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1

# Application settings (if needed)
LOG_LEVEL=INFO
CONFIG_PATH=/app/configs
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure volume mounts have correct permissions
2. **Network Issues**: Verify `--network host` is used
3. **Missing Dependencies**: Rebuild image with `--no-cache`
4. **Config Not Found**: Check config volume mount path

### Debug Commands

```bash
# Check container health
docker exec mover-status python -c "import mover_status; print('OK')"

# Verify mounts
docker exec mover-status ls -la /mnt /var/log

# Check Python environment
docker exec mover-status python -c "import sys; print(sys.path)"
```

## Performance Notes

- Uses Python 3.13 for optimal performance
- Bytecode compilation reduces startup time
- Multi-stage build minimizes final image size
- UV provides faster dependency resolution than pip

## Updating

To update the container:

```bash
# Pull latest image
docker pull ghcr.io/engels74/mover-status:latest

# Restart container with new image
docker-compose down && docker-compose up -d
```