# ── Build stage ───────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/deps -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="flask-otel-demo"
LABEL org.opencontainers.image.description="Flask app con OpenTelemetry completo"

RUN groupadd --gid 1001 app && useradd --uid 1001 --gid 1001 --no-create-home app

WORKDIR /app
COPY --from=builder /deps /usr/local
COPY . .

RUN mkdir -p /tmp && chown app:app /tmp

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000 \
    ENVIRONMENT=production \
    SERVICE_VERSION=1.0.0 \
    DB_PATH=/tmp/app.db

USER app
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health/live')" || exit 1

CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
