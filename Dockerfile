FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

RUN mkdir -p /app/data/logs /app/data/outputs /app/data/db

EXPOSE 8000

# One process. A second worker would double the RSS on the 512MB starter
# instance. Keep-alive is 120s so it stays open longer than Render's edge
# (about 75s). The default of 5s makes the edge reuse a socket this process
# already closed, and the client sees a clean TLS close with no status line.
# The access log is off: it records client IPs and the raw query string
# (OAuth code and state on the store callbacks). RequestLogMiddleware records
# method, route template, status and duration instead.
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 120 --no-access-log"]
