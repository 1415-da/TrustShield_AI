# Build context is the repository root (so the seed script is available).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/backend

COPY backend/requirements.txt .
RUN pip install -r requirements.txt \
 && python -m spacy download en_core_web_sm

COPY backend/ /srv/backend/
COPY scripts/ /srv/scripts/

RUN useradd --create-home trustshield && chown -R trustshield /srv
USER trustshield

EXPOSE 8000
CMD ["sh", "/srv/backend/entrypoint.sh"]
