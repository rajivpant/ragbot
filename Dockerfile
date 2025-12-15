# Dockerfile for Ragbot.AI
# FastAPI backend for CLI and React web interface

FROM python:3.12-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

FROM base as dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base as final

COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY engines.yaml .
COPY ragbot ragbot_api ./

RUN chmod +x ragbot ragbot_api

RUN mkdir -p /root/.local/share/ragbot/sessions && \
    mkdir -p /root/.config/ragbot && \
    mkdir -p /app/ragbot-data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
