FROM python:3.11-slim
WORKDIR /app
COPY ../../pyproject.toml /app/pyproject.toml
COPY ../../src /app/src
RUN pip install -e .
COPY . /app
CMD ["python", "agent.py"]
