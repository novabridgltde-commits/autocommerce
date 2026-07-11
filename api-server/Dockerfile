FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:${PATH}" \
    ENV=production \
    DEBUG=false \
    PORT=8000 \
    # P1-6 FIX: was 2 — config.py default is 4, docker-compose forces 4.
    # Harmonised to 4. Override via env var UVICORN_WORKERS at runtime.
    UVICORN_WORKERS=4

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/* && \
    groupadd --system app && \
    useradd --system --gid app --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN mkdir -p /app/logs && chmod +x /app/start.sh && chown -R app:app /app /home/app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["./start.sh"]
# P0-7 FIX: --forwarded-allow-ips was '*' (trust ALL proxies — IP spoofing risk).
# Now reads TRUSTED_PROXY_IPS env var (default: 127.0.0.1 for localhost only).
# In production behind nginx/ALB/Traefik: set TRUSTED_PROXY_IPS to the proxy IP range.
# Example: TRUSTED_PROXY_IPS=10.0.0.0/8 for AWS VPC internal traffic.
# For K8s with nginx-ingress: TRUSTED_PROXY_IPS=10.96.0.0/12
