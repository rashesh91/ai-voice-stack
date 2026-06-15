FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-devel

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Training runs as a Job, not a long-running service
CMD ["python", "src/train_lora.py", "--config", "src/config/lora_config.yaml"]
