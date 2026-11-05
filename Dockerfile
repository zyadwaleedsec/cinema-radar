# syntax=docker/dockerfile:1
#
# Cinema Radar is a long-polling worker: it never listens on a port.
# The SQLite database is expected at DB_PATH (see fly.toml) and is created
# automatically on first start.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Only the runtime requirements: the test/dev tools are not installed.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Mount point for the Fly.io volume that keeps the database across deploys.
RUN mkdir -p /data

CMD ["python", "-m", "main"]
