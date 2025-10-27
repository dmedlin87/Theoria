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

COPY theo/services/api/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY . /app
ENV PYTHONPATH=/app

CMD ["uvicorn", "theo.infrastructure.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]