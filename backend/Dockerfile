# Backend image. Used by docker-compose locally and by Render in production.
#
# The build context is the REPO ROOT, not backend/ (see render.yaml). That is
# forced by how the app resolves paths: `config.py` derives PROJECT_ROOT as the
# parent of the backend directory, so with the code at /app it looks for the
# catalog at /data/products/catalog.json, and `personalization.py` looks for the
# model at /ml/personalization/model/. Both sit outside backend/, so the layout
# below reproduces that shape rather than fighting it.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # train.py inserts "<repo>/backend" on sys.path, which resolves to /backend
    # here and does not exist. Naming /app explicitly is what lets the training
    # step import `app.*` at container start.
    PYTHONPATH=/app

WORKDIR /app

# Dependencies first: this layer only rebuilds when requirements.txt changes,
# and scikit-learn takes long enough that it matters.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code lands at /app, so /app is the backend directory and / is the
# project root -- exactly what config.py assumes.
COPY backend/ ./
COPY data/ /data/
COPY ml/ /ml/

ENV PORT=8000
EXPOSE 8000

# Startup does three idempotent things in order:
#   1. seed the catalog, but only into an empty database
#   2. train the segment classifier, but only if no artifact is present -- the
#      model is gitignored, so a fresh clone never carries one, and without
#      this every deploy would serve `status: model_unavailable`
#   3. serve
#
# Not `--reload`: it doubles memory and restarts the process on any file event,
# which on a container filesystem is not always a file you changed.
CMD ["sh", "-c", "python -m scripts.seed --if-empty && ([ -f /ml/personalization/model/segment_classifier.joblib ] || python /ml/personalization/train.py) && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
