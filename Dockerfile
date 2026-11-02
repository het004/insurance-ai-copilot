
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements from backend
COPY backend/requirements.txt ./requirements.txt

RUN pip install -r requirements.txt

# Copy Python application from backend
COPY backend/app ./app

# Create data directory and non-root user
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app /data /app

USER app

VOLUME ["/data"]

ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD curl -fs http://localhost:${PORT}/api/health || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
