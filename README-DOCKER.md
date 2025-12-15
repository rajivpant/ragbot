# Ragbot.AI - Docker Deployment Guide

This guide explains how to run Ragbot.AI using Docker and Docker Compose for easy deployment and portability.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (version 20.10 or later)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0 or later)
- At least one AI provider API key (OpenAI, Anthropic, or Google Gemini)

## Quick Start

### 1. Set Up API Keys

Create the keys configuration file:

```bash
mkdir -p ~/.config/ragbot
cat > ~/.config/ragbot/keys.yaml << 'EOF'
# Ragbot API Keys
default:
  anthropic: "sk-ant-your-key-here"
  openai: "sk-your-key-here"
  google: "your-gemini-key-here"
EOF
chmod 600 ~/.config/ragbot/keys.yaml
```

Edit with your actual API keys.

### 2. Build and Start the Web Interface

```bash
# Build the Docker image
docker-compose build

# Start the web interface
docker-compose up -d

# View logs
docker-compose logs -f ragbot-web
```

### 3. Access the Application

Open your browser and navigate to:
```
http://localhost:8501
```

The Streamlit web interface should now be running!

## Usage Examples

### Web Interface (Streamlit)

**Start the web interface:**
```bash
docker-compose up -d ragbot-web
```

**Stop the web interface:**
```bash
docker-compose down
```

**View real-time logs:**
```bash
docker-compose logs -f ragbot-web
```

**Restart after config changes:**
```bash
docker-compose restart ragbot-web
```

### CLI Interface

The CLI can be run as a one-off command using `docker-compose run`:

**Get help:**
```bash
docker-compose run --rm ragbot-cli --help
```

**Run with a prompt:**
```bash
docker-compose run --rm ragbot-cli -p "Your prompt here"
```

**Interactive mode:**
```bash
docker-compose run --rm ragbot-cli -i
```

**With custom dataset:**
```bash
docker-compose run --rm ragbot-cli -p "Analyze this data" -d /app/datasets
```

**Note:** To enable the CLI service, uncomment the `ragbot-cli` section in `docker-compose.yml`.

## Configuration

### API Keys

API keys are stored in `~/.config/ragbot/keys.yaml`:

```yaml
# Ragbot API Keys
default:
  anthropic: "sk-ant-..."
  openai: "sk-..."
  google: "..."

# Optional: workspace-specific key overrides
workspaces:
  example-client:
    anthropic: "sk-ant-client-specific-key..."
```

This file should have restrictive permissions (`chmod 600`).

### AI Knowledge Repositories

Ragbot automatically discovers workspaces from `ai-knowledge-*` repositories. For Docker:

**Mount your ai-knowledge directory:**

Create `docker-compose.override.yml`:
```yaml
version: '3.8'

services:
  ragbot-web:
    volumes:
      # Mount ai-knowledge repos
      - /path/to/ai-knowledge:/app/ai-knowledge:ro
      # Mount keys configuration
      - ~/.config/ragbot:/root/.config/ragbot:ro
```

The workspaces are discovered automatically based on the `ai-knowledge-*` naming convention.

### Engines Configuration

The `engines.yaml` file is included in the Docker image. To customize it:

1. Edit `engines.yaml` locally
2. Rebuild the image: `docker-compose build`
3. Restart: `docker-compose up -d`

## Data Persistence

Session data is persisted using Docker volumes:

```bash
# List volumes
docker volume ls | grep ragbot

# Inspect session data
docker volume inspect ragbot_ragbot-sessions

# Backup sessions
docker run --rm -v ragbot_ragbot-sessions:/data -v $(pwd):/backup alpine tar czf /backup/sessions-backup.tar.gz -C /data .

# Restore sessions
docker run --rm -v ragbot_ragbot-sessions:/data -v $(pwd):/backup alpine tar xzf /backup/sessions-backup.tar.gz -C /data
```

## Development Mode

For local development with hot-reload:

```bash
# The docker-compose.override.yml is automatically loaded
docker-compose up

# Your code changes in ./src will automatically reload the Streamlit app
```

### Run Tests

```bash
# Run the test suite
docker-compose run --rm ragbot-test

# Run specific test file
docker-compose run --rm ragbot-test tests/test_ragbot.py

# Run with verbose output
docker-compose run --rm ragbot-test -v -s
```

## Production Deployment

### Security Best Practices

1. **Use Docker secrets** instead of environment variables:
```yaml
secrets:
  openai_api_key:
    external: true
```

2. **Run as non-root user** (uncomment in Dockerfile):
```dockerfile
USER ragbot
```

3. **Mount sensitive files as read-only:**
```yaml
volumes:
  - ~/.config/ragbot:/root/.config/ragbot:ro
```

### Resource Limits

Add resource constraints in `docker-compose.yml`:

```yaml
services:
  ragbot-web:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          memory: 512M
```

### Reverse Proxy (Nginx/Traefik)

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name ragbot.yourdomain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker Compose Production Override

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  ragbot-web:
    restart: always
    deploy:
      resources:
        limits:
          memory: 2G
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Run with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Container won't start

**Check logs:**
```bash
docker-compose logs ragbot-web
```

**Verify environment variables:**
```bash
docker-compose config
```

### Port already in use

Change the port mapping in `docker-compose.yml`:
```yaml
ports:
  - "8502:8501"  # Use port 8502 instead
```

### API key not recognized

**Verify environment variables are loaded:**
```bash
docker-compose exec ragbot-web env | grep API_KEY
```

**Rebuild if needed:**
```bash
docker-compose down
docker-compose up --build
```

### Session data not persisting

**Check volume is created:**
```bash
docker volume ls | grep ragbot
```

**Inspect volume mount:**
```bash
docker-compose exec ragbot-web ls -la /root/.local/share/ragbot/sessions/
```

### Permission issues with mounted volumes

**On Linux, you may need to set permissions:**
```bash
sudo chown -R 1000:1000 datasets instructions
```

Or uncomment the non-root user section in the Dockerfile.

## Publishing to Docker Hub

```bash
# Tag the image
docker tag ragbot:latest yourusername/ragbot:latest
docker tag ragbot:latest yourusername/ragbot:v1.0.0

# Push to Docker Hub
docker push yourusername/ragbot:latest
docker push yourusername/ragbot:v1.0.0
```

Then others can use:
```bash
docker pull yourusername/ragbot:latest
docker run -p 8501:8501 -e OPENAI_API_KEY=your-key yourusername/ragbot:latest
```

## Advanced Usage

### Custom Streamlit Configuration

Create `.streamlit/config.toml`:

```toml
[server]
port = 8501
address = "0.0.0.0"
headless = true

[theme]
primaryColor = "#F63366"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
```

Mount it:
```yaml
volumes:
  - ./.streamlit:/app/.streamlit:ro
```

### Multi-stage Deployment

Build once, deploy everywhere:

```bash
# Build
docker-compose build

# Save image
docker save ragbot:latest | gzip > ragbot-docker-image.tar.gz

# On another server
gunzip -c ragbot-docker-image.tar.gz | docker load
docker-compose up -d
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Cleanup

```bash
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: deletes session data)
docker-compose down -v

# Remove images
docker rmi ragbot:latest

# Complete cleanup
docker system prune -a
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/rajivpant/ragbot/issues
- Documentation: See main README.md

## License

Same as Ragbot.AI - see LICENSE file.
