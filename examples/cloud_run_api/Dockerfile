FROM python:3.11-slim
WORKDIR /app
COPY ../../pyproject.toml /app/pyproject.toml
COPY ../../src /app/src
RUN pip install -e .
RUN pip install fastapi uvicorn
COPY . /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
