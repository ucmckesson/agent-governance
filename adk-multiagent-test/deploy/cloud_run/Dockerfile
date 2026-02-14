FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install SDK and test harness from local monorepo checkout.
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY adk-multiagent-test /app/adk-multiagent-test

RUN pip install --no-cache-dir -e /app \
    && pip install --no-cache-dir -e /app/adk-multiagent-test \
    && pip install --no-cache-dir fastapi uvicorn

WORKDIR /app/adk-multiagent-test/deploy/cloud_run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
