# Multi-stage Dockerfile for PharmAssist backend

FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100
WORKDIR /app

# System deps (if needed) - minimal now
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
# Create non-root user
RUN useradd -m -u 1001 pharmassist
COPY --from=builder /install /usr/local
COPY backend backend
COPY db db
COPY alembic alembic
COPY alembic.ini .
COPY requirements.txt ./
# Optional: copy scripts for scale / maintenance
COPY scripts scripts

USER pharmassist
EXPOSE 5000
ENV STRUCTURED_LOGGING=1 LOG_TIMING=1 SLOW_REQUEST_MS=600 SLOW_DB_MS=450

# Gunicorn entrypoint (adjust workers via env GUNICORN_WORKERS)
ENV GUNICORN_WORKERS=4
CMD ["bash", "-c", "gunicorn -w ${GUNICORN_WORKERS} -k gevent -t 90 backend.wsgi:app --bind 0.0.0.0:5000"]
