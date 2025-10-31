FROM mcr.microsoft.com/powershell:7.4-ubuntu-22.04

WORKDIR /app

COPY . /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip nodejs npm curl \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv .venv \
    && ./.venv/bin/pip install --upgrade pip \
    && ./.venv/bin/pip install ".[api]" -c constraints/guardrails.txt -c constraints/prod.txt \
    && ./.venv/bin/pip install ".[ml]" -c constraints/guardrails.txt -c constraints/prod.txt \
    && ./.venv/bin/pip install ".[dev]" -c constraints/guardrails.txt -c constraints/dev.txt \
    && npm install --prefix theo/services/web

EXPOSE 8000 8100 3000 3300 9101

ENTRYPOINT ["pwsh", "-NoLogo", "-NoProfile", "-File", "/app/start-theoria.ps1"]
