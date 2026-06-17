#!/usr/bin/env bash
# Run LoRA fine-tuning on call transcript data, then reload vLLM adapter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(dirname "$SCRIPT_DIR")"
DATA_FILE="${SCRIPT_DIR}/data/train.jsonl"
OUTPUT_DIR="${STACK_DIR}/data/lora-adapter"

# Stop vLLM to free GPU memory for training
if docker ps --format '{{.Names}}' | grep -q "^vllm-server$"; then
    echo "==> Stopping vLLM to free GPU memory..."
    docker stop vllm-server
fi

echo "==> Starting LoRA training"
echo "    Data:   $DATA_FILE"
echo "    Output: $OUTPUT_DIR"

[[ -f "$DATA_FILE" ]] || { echo "ERROR: $DATA_FILE not found"; exit 1; }
SAMPLES=$(wc -l < "$DATA_FILE")
echo "    Samples: $SAMPLES"

docker run --rm --gpus all \
    -v "${SCRIPT_DIR}:/workspace" \
    -v "${SCRIPT_DIR}/data:/data" \
    -v "${OUTPUT_DIR}:/output/lora-adapter" \
    -v "${STACK_DIR}/data/vllm-models:/models" \
    -e HF_HOME=/models/hub \
    localhost:5000/ai-training:latest \
    python3 -m src.train_lora \
        --config /workspace/src/config/lora_config.yaml

echo "==> Training complete. Adapter saved to $OUTPUT_DIR"

# Restart vLLM with LoRA adapter
MODEL_DIR="${STACK_DIR}/data/vllm-models"
echo "==> Restarting vLLM with LoRA adapter..."
docker stop vllm-server 2>/dev/null || true
docker rm vllm-server 2>/dev/null || true

docker run -d --name vllm-server --restart=unless-stopped \
    --gpus all \
    -p 8000:8000 \
    -v "${MODEL_DIR}:/models" \
    -v "${OUTPUT_DIR}:/lora-adapter" \
    -e HF_HOME=/models/hub \
    vllm/vllm-openai:v0.6.6 \
    --model Qwen/Qwen2.5-1.5B-Instruct \
    --dtype bfloat16 \
    --enforce-eager \
    --gpu-memory-utilization 0.60 \
    --max-model-len 2048 \
    --enable-lora \
    --lora-modules voice-agent=/lora-adapter \
    --max-lora-rank 32

echo "==> Waiting for vLLM to be ready (up to 5 min)..."
for i in $(seq 1 60); do
    if curl -s --max-time 2 http://localhost:8000/health | grep -q "{}"; then break; fi
    sleep 5
done
echo "==> vLLM ready. Models:"
curl -s http://localhost:8000/v1/models | python3 -c "
import sys,json
for m in json.load(sys.stdin).get('data',[]): print('  •', m['id'])
"

echo "==> Done!"
