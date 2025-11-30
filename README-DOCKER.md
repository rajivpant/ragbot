# Ragbot.AI - Docker Deployment Guide

This guide explains how to run Ragbot.AI using Docker and Docker Compose for easy deployment and portability.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (version 20.10 or later)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0 or later)
- At least one AI provider API key (OpenAI, Anthropic, or Google Gemini)

## Quick Start

### 1. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example environment file
cp .env.docker .env

# Edit with your API keys
nano .env  # or use your preferred editor
```

Add at least one of these API keys:
```env
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
GEMINI_API_KEY=your-google-gemini-key-here
```

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

### Environment Variables

All configuration is done through environment variables in the `.env` file:

```env
# Required: At least one AI provider
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# Optional: AWS configuration
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=us-east-1

# Optional: Pinecone vector database
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...
```

### Using Your Own Data

Ragbot supports multiple methods for accessing your custom datasets and instructions:

#### Method 1: docker-compose.override.yml (Recommended for Separate Data Repos)

If you keep your data in a separate directory (like a private `ragbot-data/` git repository):

**Step 1:** Copy the example file:
```bash
cp docker-compose.override.example.yml docker-compose.override.yml
```

**Step 2:** Edit `docker-compose.override.yml` with your actual paths:
```yaml
version: '3.8'

services:
  ragbot-web:
    volumes:
      # Mount your private ragbot-data directory
      - /path/to/your/ragbot-data/datasets:/app/datasets:ro
      - /path/to/your/ragbot-data/instructions:/app/instructions:ro
      - /path/to/your/ragbot-data/profiles.yaml:/app/profiles.yaml:ro
```

**Step 3:** Restart Docker:
```bash
docker-compose down
docker-compose up -d
```

**Note:** `docker-compose.override.yml` is gitignored, so your private paths won't be committed.

#### Method 2: Local Directories (Quick Start)

Place your files directly in the ragbot directory:

```
ragbot/
├── datasets/        # Your knowledge base files
├── instructions/     # Custom instruction files
└── profiles.yaml           # User profiles (optional)
```

These directories are automatically mounted into the container at `/app/datasets` and `/app/instructions`.

#### Method 3: Symlinks (Convenient for Local Development)

Create symlinks from your ragbot directory to your data repository:

```bash
cd /path/to/ragbot
ln -s /path/to/your/ragbot-data/datasets ./datasets
ln -s /path/to/your/ragbot-data/instructions ./instructions
ln -s /path/to/your/ragbot-data/profiles.yaml ./profiles.yaml
```

#### Method 4: Environment Variable (Advanced)

Set `RAGBOT_DATA_DIR` in your `.env` file:

```bash
RAGBOT_DATA_DIR=/path/to/your/ragbot-data
```

Then update `docker-compose.yml` volumes to use this variable:
```yaml
volumes:
  - ${RAGBOT_DATA_DIR:-./datasets}/datasets:/app/datasets:ro
```

### Updating profiles.yaml for Docker

If you use profiles with absolute paths, update them to container paths:

**Before (local paths):**
```yaml
profiles:
  - name: "My Profile"
    curated_datasets:
      - "/Users/myname/ragbot-data/datasets/my-data/"
```

**After (container paths):**
```yaml
profiles:
  - name: "My Profile"
    curated_datasets:
      - "/app/datasets/my-data/"
```

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
  - ./profiles.yaml:/app/profiles.yaml:ro
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
