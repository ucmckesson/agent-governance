FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install SDK and test harness from local monorepo checkout.
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY adk-multiagent-test /app/adk-multiagent-test

RUN pip install --no-cache-dir --no-build-isolation -e /app \
    && pip install --no-cache-dir --no-build-isolation -e /app/adk-multiagent-test \
    && pip install --no-cache-dir fastapi uvicorn

WORKDIR /app/adk-multiagent-test/deploy/cloud_run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
