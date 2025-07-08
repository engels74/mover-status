# Unraid-Specific Docker Considerations

This document outlines specific considerations and best practices for running the mover-status application in Docker containers on Unraid systems.

## Unraid Docker Architecture

### Host Integration Requirements

Unraid systems require special consideration for Docker containers that need to monitor system processes and filesystems:

1. **Network Access**: Use `--network host` to access Unraid's network services
2. **Process Monitoring**: Use `--pid host` for process tree visibility
3. **Filesystem Access**: Mount Unraid-specific paths with appropriate permissions

### Pre-built Images

Use the pre-built multi-architecture images from GitHub Container Registry:

```bash
# Pull the appropriate image for your Unraid architecture
docker pull ghcr.io/engels74/mover-status:latest
```

### Critical Volume Mounts

```yaml
volumes:
  # Unraid array and cache drives
  - "/mnt:/mnt:ro"
  
  # System logs (mover logs are here)
  - "/var/log:/var/log:ro"
  
  # Process information
  - "/proc:/host/proc:ro"
  
  # System information
  - "/sys:/host/sys:ro"
  
  # Configuration (writable)
  - "./configs:/app/configs:ro"
```

## Unraid-Specific Optimizations

### Container Placement

For optimal performance on Unraid:

1. **CPU Pinning**: Consider pinning container to specific CPU cores
2. **Memory Limits**: Set appropriate memory limits to avoid interference
3. **Storage Location**: Store container data on cache drive for performance

### Docker Compose for Unraid

```yaml
# Enhanced docker-compose.yml for Unraid
services:
  mover-status:
    image: ghcr.io/engels74/mover-status:latest
    container_name: mover-status
    restart: unless-stopped
    
    # Unraid-specific settings
    network_mode: host
    pid: host
    privileged: false  # Avoid privileged mode when possible
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.1'
          memory: 128M
    
    # Volume mounts for Unraid
    volumes:
      - "/mnt:/mnt:ro"
      - "/var/log:/var/log:ro"
      - "/proc:/host/proc:ro"
      - "/sys:/host/sys:ro"
      - "/boot/config:/boot/config:ro"  # Unraid config
      - "./configs:/app/configs:ro"
    
    # Environment variables
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
      - TZ=America/New_York  # Set your timezone
    
    # Health check
    healthcheck:
      test: ["CMD", "python", "-c", "import mover_status; print('OK')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

## Security Considerations

### User Permissions

The container runs as a non-root user (UID 1000) for security:

```dockerfile
# In Dockerfile
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home app
USER app
```

### Read-Only Mounts

Most system directories are mounted read-only:
- `/mnt:ro` - Prevents accidental modification of array data
- `/var/log:ro` - Prevents log tampering
- `/proc:ro` and `/sys:ro` - System information access only

## Performance Optimization

### Startup Performance

1. **Bytecode Compilation**: Pre-compiled Python bytecode reduces startup time
2. **Dependency Caching**: UV cache optimization for faster container builds
3. **Minimal Base Image**: Python 3.13 slim reduces container size

### Runtime Performance

1. **Multi-stage Build**: Separates build dependencies from runtime
2. **Health Checks**: Monitors container health automatically
3. **Resource Limits**: Prevents resource exhaustion

## Monitoring and Logging

### Container Logs

```bash
# View container logs
docker logs mover-status

# Follow logs in real-time
docker logs -f mover-status

# View last 100 lines
docker logs --tail 100 mover-status
```

### Application Logs

The application logs are available through:
1. Container stdout/stderr (captured by Docker)
2. Mounted log directories (if configured)
3. Notification providers (Discord, Telegram, etc.)

## Integration with Unraid WebUI

### Custom Docker Template

Create a custom template for Unraid's Docker tab:

```xml
<?xml version="1.0"?>
<Container version="2">
  <Name>mover-status</Name>
  <Repository>ghcr.io/engels74/mover-status</Repository>
  <Registry>https://github.com/engels74/mover-status/pkgs/container/mover-status</Registry>
  <Network>host</Network>
  <Privileged>false</Privileged>
  <Support>https://github.com/engels74/mover-status/issues</Support>
  <Project>https://github.com/engels74/mover-status</Project>
  <Overview>Monitor Unraid mover process and send notifications</Overview>
  <Category>Tools:</Category>
  <WebUI></WebUI>
  <TemplateURL></TemplateURL>
  <Icon>https://raw.githubusercontent.com/engels74/mover-status/main/mover-status.svg</Icon>
  <ExtraParams>--pid host</ExtraParams>
  <PostArgs></PostArgs>
  <CPUset></CPUset>
  <DateInstalled></DateInstalled>
  <DonateText></DonateText>
  <DonateLink></DonateLink>
  <Description>Monitor Unraid mover process and send notifications</Description>
  <Config Name="Config" Target="/app/configs" Default="" Mode="ro" Description="Configuration files" Type="Path" Display="always" Required="true" Mask="false"></Config>
  <Config Name="Unraid Array" Target="/mnt" Default="/mnt" Mode="ro" Description="Unraid array mount" Type="Path" Display="advanced" Required="true" Mask="false"></Config>
  <Config Name="System Logs" Target="/var/log" Default="/var/log" Mode="ro" Description="System logs" Type="Path" Display="advanced" Required="true" Mask="false"></Config>
  <Config Name="Process Info" Target="/host/proc" Default="/proc" Mode="ro" Description="Process information" Type="Path" Display="advanced" Required="true" Mask="false"></Config>
  <Config Name="System Info" Target="/host/sys" Default="/sys" Mode="ro" Description="System information" Type="Path" Display="advanced" Required="true" Mask="false"></Config>
</Container>
```

## Troubleshooting

### Common Unraid Issues

1. **Permission Denied on /mnt**: Ensure Docker has access to shares
2. **Network Issues**: Verify host networking is enabled
3. **Process Monitoring Fails**: Check if `--pid host` is set
4. **Config Not Loading**: Verify config directory permissions

### Debug Commands

```bash
# Check Unraid mounts
docker exec mover-status ls -la /mnt/user /mnt/cache

# Verify process access
docker exec mover-status ps aux | grep mover

# Check system access
docker exec mover-status ls -la /host/proc /host/sys

# Test configuration
docker exec mover-status python -c "
import os
print('Config dir:', os.listdir('/app/configs'))
print('Mnt dir:', os.listdir('/mnt'))
"
```

### Performance Tuning

```bash
# Monitor container resource usage
docker stats mover-status

# Check container health
docker inspect mover-status | grep -A 5 Health

# Verify bytecode compilation
docker exec mover-status find /app -name "*.pyc" | head -5
```

## Best Practices

1. **Use Docker Compose**: Easier management and configuration
2. **Set Resource Limits**: Prevent impact on Unraid system
3. **Regular Updates**: Keep container and dependencies updated
4. **Monitor Logs**: Watch for errors and performance issues
5. **Backup Configs**: Store configuration files in version control
6. **Test Changes**: Use development profile for testing

## Integration Examples

### With Unraid Notifications

The application can integrate with Unraid's notification system and other tools:

```yaml
# Example integration with other Unraid containers
services:
  mover-status:
    # ... main service configuration
    depends_on:
      - unraid-api
    
  unraid-api:
    image: unraid/webgui:latest
    # ... configuration for Unraid API access
```

### With Monitoring Stack

```yaml
# Integration with monitoring tools
services:
  mover-status:
    # ... main configuration
    labels:
      - "prometheus.io/scrape=true"
      - "prometheus.io/port=8000"
    
  prometheus:
    image: prom/prometheus:latest
    # ... prometheus configuration
```

This setup provides a robust, secure, and performant Docker environment for testing Python scripts on Unraid systems.