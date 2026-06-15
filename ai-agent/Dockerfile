FROM python:3.11-slim

WORKDIR /app

# System deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download silero VAD model at build time (avoids cold start)
RUN python -c "from livekit.plugins import silero; silero.VAD.load()"

COPY src/ ./src/

EXPOSE 8080

CMD ["python", "-m", "src.main"]
