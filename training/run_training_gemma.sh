#!/usr/bin/env bash
# Fine-tune Indic-gemma-7b on UGVCL train_v2.jsonl, then reload vLLM with LoRA adapter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(dirname "$SCRIPT_DIR")"
DATA_FILE="${SCRIPT_DIR}/data/train_v2.jsonl"
OUTPUT_DIR="${STACK_DIR}/data/lora-adapter-gemma"
MODEL_CACHE="${STACK_DIR}/data/vllm-models"

echo "=== UGVCL — Indic-gemma-7b LoRA fine-tuning ==="
echo "    Data:   $DATA_FILE"
echo "    Output: $OUTPUT_DIR"
SAMPLES=$(wc -l < "$DATA_FILE")
echo "    Samples: $SAMPLES"
echo ""

[[ -f "$DATA_FILE" ]] || { echo "ERROR: $DATA_FILE not found"; exit 1; }

mkdir -p "$OUTPUT_DIR"

# ── 1. Stop vLLM to free full GPU for training ────────────────────────────
echo "==> Scaling down vLLM to release GPU memory..."
kubectl -n ai-voice scale deployment vllm --replicas=0
echo "    Waiting for vLLM pod to terminate..."
kubectl -n ai-voice wait --for=delete pod -l app=vllm --timeout=120s 2>/dev/null || true
echo "    vLLM stopped. GPU freed."
echo ""

# ── 2. Run LoRA fine-tuning ───────────────────────────────────────────────
echo "==> Starting LoRA training on Indic-gemma-7b..."
echo "    This takes ~1.5–2 hours on an L4 GPU."
echo ""

docker run --rm --gpus all \
    -w /workspace \
    -v "${SCRIPT_DIR}:/workspace" \
    -v "${SCRIPT_DIR}/data:/data" \
    -v "${OUTPUT_DIR}:/output/lora-adapter-gemma" \
    -v "${MODEL_CACHE}:/models" \
    -e HF_HOME=/models/hub \
    -e TRANSFORMERS_CACHE=/models/hub \
    -e HF_HUB_DISABLE_XET=1 \
    -e TMPDIR=/models/tmp \
    -e HF_HUB_CACHE=/models/hub/hub \
    localhost:5000/ai-training:latest \
    python3 -m src.train_lora \
        --config /workspace/src/config/lora_config_gemma.yaml

echo ""
echo "==> Training complete. Adapter saved to $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR/"

# ── 3. Update vLLM deployment to serve with LoRA ─────────────────────────
echo ""
echo "==> Patching vLLM deployment to load LoRA adapter..."

# Add LoRA args to the vLLM container command
kubectl -n ai-voice patch deployment vllm --type='json' -p='[
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--enable-lora"},
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--lora-modules"},
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"indic-gemma=/lora-adapter-gemma"},
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--max-lora-rank"},
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"16"}
]' 2>/dev/null || echo "    (patch may already be applied)"

# Mount the adapter directory into the vLLM pod
kubectl -n ai-voice patch deployment vllm --type='json' -p='[
  {"op":"add","path":"/spec/template/spec/containers/0/volumeMounts/-",
   "value":{"name":"lora-adapter-gemma","mountPath":"/lora-adapter-gemma"}},
  {"op":"add","path":"/spec/template/spec/volumes/-",
   "value":{"name":"lora-adapter-gemma","hostPath":{"path":"'"$OUTPUT_DIR"'","type":"Directory"}}}
]' 2>/dev/null || echo "    (volume patch may already be applied)"

# ── 4. Scale vLLM back up ─────────────────────────────────────────────────
echo ""
echo "==> Scaling vLLM back up (replicas=1)..."
kubectl -n ai-voice scale deployment vllm --replicas=1

echo "    Waiting for vLLM to become ready (model load takes ~3–5 min)..."
kubectl -n ai-voice wait --for=condition=available deployment/vllm --timeout=600s
echo "    vLLM is ready!"
echo ""

# ── 5. Update VLLM_MODEL in ai-agent configmap ───────────────────────────
kubectl -n ai-voice patch configmap ai-agent-config \
    --type merge \
    -p '{"data":{"VLLM_MODEL":"indic-gemma"}}'

# ── 6. Restart ai-agent to pick up new model name ─────────────────────────
echo "==> Rolling restart of ai-agent..."
kubectl -n ai-voice rollout restart deployment ai-agent
kubectl -n ai-voice rollout status deployment ai-agent --timeout=120s

echo ""
echo "=== Done! ==="
echo ""
echo "    LLM model: indic-gemma (Indic-gemma-7b + UGVCL LoRA)"
echo "    STT:       sarvamai/sarvam-2b-v0.5 (local)"
echo "    TTS:       ai4bharat/indic-parler-tts (local)"
echo ""
echo "    To verify: curl http://localhost:8000/v1/models"
