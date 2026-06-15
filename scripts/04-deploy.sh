#!/usr/bin/env bash
set -euo pipefail

K8S=/opt/ai-voice-stack/k8s

echo "=== Deploying AI Voice Stack to k3s ==="

# Inject SARVAM_API_KEY into secrets.yaml at deploy time
if [ -z "${SARVAM_API_KEY:-}" ]; then
  echo "[ERROR] SARVAM_API_KEY not set. Run: export SARVAM_API_KEY=<your-key>"; exit 1
fi

SARVAM_B64=$(echo -n "$SARVAM_API_KEY" | base64 -w0)
ESL_PASSWORD_B64=$(echo -n "${ESL_PASSWORD:-ClueCon}" | base64 -w0)
POSTGRES_PASSWORD_B64=$(echo -n "${POSTGRES_PASSWORD:-aivoice2024}" | base64 -w0)
LIVEKIT_API_KEY_B64=$(echo -n "${LIVEKIT_API_KEY:-devkey}" | base64 -w0)
LIVEKIT_API_SECRET_B64=$(echo -n "${LIVEKIT_API_SECRET:-devsecret}" | base64 -w0)

echo "Phase 1: Namespace + NVIDIA device plugin"
kubectl apply -f "${K8S}/00-namespace.yaml"
kubectl apply -f "${K8S}/nvidia-device-plugin.yaml"

echo "Secrets"
sed -e "s|SARVAM_API_KEY_B64|${SARVAM_B64}|g" \
    -e "s|ESL_PASSWORD_B64|${ESL_PASSWORD_B64}|g" \
    -e "s|POSTGRES_PASSWORD_B64|${POSTGRES_PASSWORD_B64}|g" \
    -e "s|LIVEKIT_API_KEY_B64|${LIVEKIT_API_KEY_B64}|g" \
    -e "s|LIVEKIT_API_SECRET_B64|${LIVEKIT_API_SECRET_B64}|g" \
    "${K8S}/01-secrets.yaml" | kubectl apply -f -

echo "Phase 2: Storage"
kubectl apply -f "${K8S}/storage/"

echo "Phase 3: ConfigMaps"
kubectl apply -f "${K8S}/configmaps/"

echo "Phase 4: Stateful services (Redis, PostgreSQL)"
kubectl apply -f "${K8S}/deployments/redis-deploy.yaml"
kubectl apply -f "${K8S}/deployments/postgres-deploy.yaml"
kubectl -n ai-voice wait --for=condition=Available deploy/redis --timeout=120s
kubectl -n ai-voice wait --for=condition=Available deploy/postgres --timeout=120s
echo "[OK] Redis and PostgreSQL ready"

echo "Phase 5: AI services (vLLM, FreeSWITCH, AI Agent)"
kubectl apply -f "${K8S}/deployments/vllm-deploy.yaml"
kubectl apply -f "${K8S}/deployments/freeswitch-deploy.yaml"
kubectl apply -f "${K8S}/deployments/ai-agent-deploy.yaml"

echo "Phase 6: Services"
kubectl apply -f "${K8S}/services/"

echo ""
echo "=== Deployment submitted. Monitoring pods... ==="
echo "(vLLM will take 5-10 min to download model on first run)"
kubectl -n ai-voice get pods -w &
WATCH_PID=$!

# Wait for all deployments to be available (up to 15 min for model download)
kubectl -n ai-voice wait --for=condition=Available deploy --all --timeout=900s
kill $WATCH_PID 2>/dev/null || true

echo ""
echo "=== All services deployed ==="
kubectl -n ai-voice get pods -o wide
kubectl -n ai-voice get svc
