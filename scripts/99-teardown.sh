#!/usr/bin/env bash
set -euo pipefail

echo "=== Tearing down AI Voice Stack ==="
read -rp "This will delete ALL resources in namespace ai-voice. Continue? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 0

kubectl delete namespace ai-voice --ignore-not-found
kubectl delete -f /opt/ai-voice-stack/k8s/nvidia-device-plugin.yaml --ignore-not-found

echo "[OK] Kubernetes resources removed"
echo "[INFO] k3s itself is still running. To uninstall k3s: /usr/local/bin/k3s-uninstall.sh"
