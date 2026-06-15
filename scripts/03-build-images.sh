#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-localhost:5000}"
TAG="${TAG:-latest}"

echo "=== Building Docker images ==="

# If using local registry, start it
if [[ "$REGISTRY" == "localhost:5000" ]]; then
  if ! docker ps | grep -q registry; then
    docker run -d -p 5000:5000 --name registry --restart=always registry:2
    echo "[OK] Local Docker registry started on :5000"
  fi
fi

# Build ai-agent
echo "Building ai-agent..."
docker build -t "${REGISTRY}/ai-agent:${TAG}" /opt/ai-voice-stack/ai-agent/
docker push "${REGISTRY}/ai-agent:${TAG}"
echo "[OK] ai-agent image pushed"

# Build training image
echo "Building training..."
docker build -t "${REGISTRY}/ai-training:${TAG}" /opt/ai-voice-stack/training/
docker push "${REGISTRY}/ai-training:${TAG}"
echo "[OK] ai-training image pushed"

echo ""
echo "=== Images built and pushed ==="
docker images | grep -E "(ai-agent|ai-training)"
