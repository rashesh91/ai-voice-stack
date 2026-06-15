#!/usr/bin/env bash
set -euo pipefail

echo "=== Configuring NVIDIA GPU for k3s ==="

K3S_CONTAINERD_CONFIG="/var/lib/rancher/k3s/agent/etc/containerd/config.toml"

# Wait for k3s containerd config to be generated
until [ -f "$K3S_CONTAINERD_CONFIG" ]; do
  echo "Waiting for k3s containerd config..."
  sleep 3
done

# Configure nvidia-container-runtime for k3s containerd
nvidia-ctk runtime configure \
  --runtime=containerd \
  --config="$K3S_CONTAINERD_CONFIG" \
  --set-as-default

# Restart k3s to pick up new containerd config
systemctl restart k3s
echo "Waiting for k3s to restart..."
sleep 15
until kubectl get nodes &>/dev/null; do sleep 2; done
kubectl wait --for=condition=Ready node --all --timeout=120s

# Enable CDI (Container Device Interface) for GPU
nvidia-ctk cdi generate --output=/var/run/cdi/nvidia.yaml

echo "[OK] NVIDIA GPU runtime configured for k3s"
echo "[INFO] CDI spec written to /var/run/cdi/nvidia.yaml"
