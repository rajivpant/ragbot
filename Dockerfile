# Multi-stage Dockerfile for Ragbot.AI
# Supports CLI, API (FastAPI), and Web (Streamlit) interfaces

# Stage 1: Base image with dependencies
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Dependencies installation
FROM base as dependencies

# Copy only requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Final application image
FROM base as final

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY engines.yaml .
COPY ragbot ragbot_web ragbot_api ./

# Make shell scripts executable
RUN chmod +x ragbot ragbot_web ragbot_api

# Create directories for data persistence
RUN mkdir -p /root/.local/share/ragbot/sessions && \
    mkdir -p /app/datasets && \
    mkdir -p /app/instructions

# Expose both API and Streamlit ports
EXPOSE 8000 8501

# Health check for API (primary service)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command runs the API server
# Can be overridden in docker-compose or docker run
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
