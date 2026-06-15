#!/usr/bin/env bash
set -euo pipefail

K3S_VERSION="v1.32.5+k3s1"

echo "=== Installing k3s ${K3S_VERSION} ==="

# Install k3s (single-node, no traefik — we handle ingress ourselves)
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION="${K3S_VERSION}" \
  INSTALL_K3S_EXEC="server --disable traefik --disable servicelb" \
  sh -

# Wait for k3s to be ready
echo "Waiting for k3s to be ready..."
until kubectl get nodes &>/dev/null; do sleep 2; done
kubectl wait --for=condition=Ready node --all --timeout=120s

# Set kubeconfig for current user
mkdir -p ~/.kube
cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
chmod 600 ~/.kube/config
echo "export KUBECONFIG=~/.kube/config" >> ~/.bashrc

echo "[OK] k3s installed — $(kubectl version --short 2>/dev/null | head -2)"
echo "[OK] Node status:"
kubectl get nodes -o wide
