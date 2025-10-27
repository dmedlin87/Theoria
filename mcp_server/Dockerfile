FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libmagic1 \
        poppler-utils \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
ENV PYTHONPATH=/app

RUN pip install --upgrade pip \
    && pip install ".[api]" -c constraints/api-constraints.txt \
    && pip install ".[ml]" -c constraints/ml-constraints.txt

ENV MCP_TOOLS_ENABLED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8050

CMD ["python", "-m", "mcp_server"]
