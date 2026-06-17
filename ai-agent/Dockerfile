# Build arg: LOCAL_MODELS=0 (default, Sarvam cloud) or 1 (local GPU inference)
ARG LOCAL_MODELS=0

# ── Stage: base ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Silero VAD (avoids cold-start delay)
RUN python -c "from livekit.plugins import silero; silero.VAD.load()"

COPY src/ ./src/

EXPOSE 8080
CMD ["python", "-m", "src.main"]

# ── Stage: local-models (GPU) ────────────────────────────────────────────────
# Built with: docker build --build-arg LOCAL_MODELS=1 -t ai-agent:local .
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS local-models-base

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf python3.11 /usr/bin/python3 \
    && ln -sf python3 /usr/bin/python

WORKDIR /app

COPY requirements.txt requirements-local-models.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-local-models.txt

# Pre-download Silero VAD
RUN python -c "from livekit.plugins import silero; silero.VAD.load()"

COPY src/ ./src/

# Models are downloaded at first startup (bind-mount /root/.cache/huggingface)
ENV USE_LOCAL_STT=true
ENV USE_LOCAL_TTS=true

EXPOSE 8080
CMD ["python", "-m", "src.main"]

# ── Final stage selection ────────────────────────────────────────────────────
FROM base AS final-0
FROM local-models-base AS final-1
FROM final-${LOCAL_MODELS} AS final
