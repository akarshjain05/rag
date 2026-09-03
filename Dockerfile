# Lean image: OpenAI + Anthropic providers only (no sentence-transformers/torch).
# To bake in the free local embedding provider instead, swap the COPY/RUN
# lines below to use requirements-local.txt — see README.md.
FROM python:3.12-slim

# build-essential covers any transitive dependency without a prebuilt wheel
# for the target platform; harmless if nothing actually needs to compile.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
COPY requirements-local.txt .
RUN pip install --no-cache-dir -r requirements-local.txt

COPY app ./app
COPY eval ./eval
COPY scripts ./scripts
COPY main.py .

RUN mkdir -p /app/data/chroma \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROMA_PERSIST_DIR=/app/data/chroma

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
