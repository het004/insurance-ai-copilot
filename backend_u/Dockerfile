FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/data
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Run as a non-root user; /data holds the SQLite DB, Customer 360 workbook, Chroma index and uploads
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown -R app /data /app
USER app

VOLUME ["/data"]
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD curl -fs http://localhost:${PORT}/api/health || exit 1
# Cloud Run injects PORT (8080); docker compose uses 8000. --proxy-headers so https URLs are seen correctly.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
