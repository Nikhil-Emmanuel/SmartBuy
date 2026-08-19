# Backend image. Used by docker-compose locally and by Render in production.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first: this layer only rebuilds when requirements.txt changes,
# and scikit-learn takes long enough that it matters.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The catalog seed is idempotent and cheap, but it needs a database to exist.
# Run it from the entrypoint rather than baking it into the image, so the
# image works against both SQLite and a Postgres URL supplied at runtime.
ENV PORT=8000
EXPOSE 8000

# Not `--reload`: it doubles memory and restarts the process on any file event,
# which on a container filesystem is not always a file you changed.
CMD ["sh", "-c", "python -m scripts.seed --if-empty && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
