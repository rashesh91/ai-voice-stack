#!/usr/bin/env bash
# Run LoRA fine-tuning on call transcript data, then reload vLLM adapter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(dirname "$SCRIPT_DIR")"
DATA_FILE="${SCRIPT_DIR}/data/train.jsonl"
OUTPUT_DIR="${STACK_DIR}/data/lora-adapter"

echo "==> Starting LoRA training"
echo "    Data:   $DATA_FILE"
echo "    Output: $OUTPUT_DIR"

[[ -f "$DATA_FILE" ]] || { echo "ERROR: $DATA_FILE not found"; exit 1; }
SAMPLES=$(wc -l < "$DATA_FILE")
echo "    Samples: $SAMPLES"

docker run --rm --gpus all \
    -v "${SCRIPT_DIR}:/workspace" \
    -v "${OUTPUT_DIR}:/output/lora-adapter" \
    -v "${STACK_DIR}/data/vllm-models:/models" \
    -e HF_HOME=/models/hub \
    localhost:5000/ai-training:latest \
    python3 -m src.train_lora \
        --config /workspace/src/config/lora_config.yaml \
        --data /workspace/data/train.jsonl \
        --output /output/lora-adapter

echo "==> Training complete. Adapter saved to $OUTPUT_DIR"

# Restart vLLM to pick up new adapter
if docker ps --format '{{.Names}}' | grep -q "^vllm-server$"; then
    echo "==> Restarting vLLM to load new adapter..."
    docker restart vllm-server
    echo "==> Waiting for vLLM to be ready..."
    until curl -s --max-time 2 http://localhost:8000/health | grep -q "{}"; do sleep 5; done
    echo "==> vLLM ready. Models:"
    curl -s http://localhost:8000/v1/models | python3 -c "
import sys,json
for m in json.load(sys.stdin).get('data',[]): print('  •', m['id'])
"
fi

echo "==> Done!"
