#!/usr/bin/env bash
set -euo pipefail

echo "=== Verifying vLLM model is loaded ==="

kubectl -n ai-voice port-forward svc/vllm 8000:8000 &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null || true" EXIT
sleep 3

echo "Waiting for vLLM to become healthy (max 15 min)..."
RETRIES=0
MAX_RETRIES=90   # 90 × 10s = 15 min
until curl -sf http://localhost:8000/health &>/dev/null; do
  RETRIES=$((RETRIES + 1))
  if [ "$RETRIES" -ge "$MAX_RETRIES" ]; then
    echo "[ERROR] vLLM did not become healthy after ${MAX_RETRIES} retries."
    echo "Check logs: kubectl -n ai-voice logs deploy/vllm --tail=50"
    exit 1
  fi
  echo "  attempt ${RETRIES}/${MAX_RETRIES} — waiting 10s..."
  sleep 10
done

echo "[OK] vLLM is healthy"
echo "Available models:"
curl -s http://localhost:8000/v1/models | python3 -m json.tool

echo ""
echo "Test inference (Hindi):"
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bartowski/Llama-3.2-3B-Instruct-AWQ",
    "messages": [{"role":"user","content":"नमस्ते, आप कैसे हैं?"}],
    "max_tokens": 50,
    "stream": false
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"

echo ""
echo "=== Model verification complete ==="
