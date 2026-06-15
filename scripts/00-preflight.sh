#!/usr/bin/env bash
set -euo pipefail

echo "=== Preflight Checks ==="

# Docker
if ! command -v docker &>/dev/null; then
  echo "[FAIL] Docker not found"; exit 1
fi
echo "[OK] Docker $(docker --version | awk '{print $3}' | tr -d ',')"

# NVIDIA GPU
if ! command -v nvidia-smi &>/dev/null; then
  echo "[FAIL] nvidia-smi not found"; exit 1
fi
GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
echo "[OK] GPU: $GPU — $VRAM"

# nvidia-container-toolkit
if ! command -v nvidia-ctk &>/dev/null; then
  echo "[FAIL] nvidia-container-toolkit not found"; exit 1
fi
echo "[OK] nvidia-ctk $(nvidia-ctk --version 2>&1 | head -1)"

# Disk space (need at least 100 GB free)
FREE_GB=$(df /opt --output=avail -BG | tail -1 | tr -d 'G ')
if [ "$FREE_GB" -lt 100 ]; then
  echo "[WARN] Only ${FREE_GB}GB free on /opt, recommend 100GB+"
else
  echo "[OK] Disk: ${FREE_GB}GB free"
fi

# Ports
for PORT in 5060 8021 8080 8000 6379 5432; do
  if ss -tuln | grep -q ":$PORT "; then
    echo "[WARN] Port $PORT already in use"
  else
    echo "[OK] Port $PORT free"
  fi
done

# SARVAM_API_KEY
if [ -z "${SARVAM_API_KEY:-}" ]; then
  echo "[WARN] SARVAM_API_KEY not set — export SARVAM_API_KEY=<your-key> before deploying"
fi

echo ""
echo "=== Preflight complete ==="
