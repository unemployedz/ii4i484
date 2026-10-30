FROM python:3.14.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git curl build-essential && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir "uv>=0.13.6" && uv sync --no-dev

EXPOSE 8082
CMD ["uv", "run", "--no-sync", "fcc-server"]
