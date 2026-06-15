#!/usr/bin/env bash
# =============================================================================
# AI Voice Stack — One-command installer
# Usage:  bash install.sh
#
# Requirements:
#   - Ubuntu 22.04 LTS
#   - NVIDIA GPU (L4 / A10 / A100 / 3090 / 4090 etc.)
#   - Minimum 16 GB RAM, 100 GB disk
#   - Root or passwordless sudo
#   - .env file in same directory (copy from .env.example)
# =============================================================================

set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log()   { echo -e "${GREEN}[$(date +%H:%M:%S)] ✓ $*${NC}"; }
info()  { echo -e "${BLUE}[$(date +%H:%M:%S)] ℹ $*${NC}"; }
warn()  { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠ $*${NC}"; }
error() { echo -e "${RED}[$(date +%H:%M:%S)] ✗ $*${NC}"; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}━━━  $*  ━━━${NC}\n"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# ── banner ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
cat << 'EOF'
  ╔═══════════════════════════════════════════════════════╗
  ║          AI Voice Stack — Automated Installer         ║
  ║  FreeSWITCH + LiveKit + vLLM + Sarvam.ai on k3s      ║
  ╚═══════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# ── pre-flight checks ─────────────────────────────────────────────────────────
step "Pre-flight checks"

[[ $EUID -eq 0 ]] || sudo -n true 2>/dev/null || error "Need root or passwordless sudo"

if [[ ! -f "$ENV_FILE" ]]; then
    error ".env file not found at $ENV_FILE\nCopy .env.example to .env and fill in your API keys:\n  cp .env.example .env && nano .env"
fi

# Validate required keys in .env
source "$ENV_FILE"
for var in SARVAM_API_KEY LIVEKIT_API_KEY LIVEKIT_API_SECRET ESL_PASSWORD POSTGRES_PASSWORD; do
    val="${!var:-}"
    [[ -n "$val" && "$val" != *"your_"* && "$val" != *"_here"* ]] || \
        error "$var is not set in .env. Please edit .env with real values."
done
chmod 600 "$ENV_FILE"
log ".env loaded and validated"

# OS check
. /etc/os-release
[[ "$ID" == "ubuntu" && "${VERSION_ID}" == "22.04" ]] || warn "Not Ubuntu 22.04 — install may still work"

# GPU check
if nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)
    log "GPU detected: $GPU"
else
    warn "nvidia-smi not found — GPU setup will run, but vLLM needs a GPU"
fi

# Disk space
FREE_GB=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
[[ $FREE_GB -ge 80 ]] || warn "Only ${FREE_GB}GB free — recommend 100GB+ (model weights need ~30GB)"
log "Disk: ${FREE_GB}GB free"

# Public IP (used to configure LiveKit SIP)
PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me || ip route get 1 | awk '{print $NF;exit}')
info "Detected public IP: $PUBLIC_IP"
echo "$PUBLIC_IP" > /tmp/ai-voice-public-ip

# ── install system dependencies ───────────────────────────────────────────────
step "System dependencies"

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
    curl wget git jq unzip ca-certificates gnupg lsb-release \
    build-essential python3 python3-pip software-properties-common \
    apt-transport-https net-tools 2>&1 | grep -E "^(Get:|Setting up)" | tail -5 || true
log "System packages installed"

# ── docker ───────────────────────────────────────────────────────────────────
step "Docker"

if docker version &>/dev/null; then
    log "Docker already installed: $(docker version --format '{{.Server.Version}}')"
else
    info "Installing Docker..."
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin
    sudo usermod -aG docker "$USER" || true
    log "Docker installed"
fi

# ── nvidia container toolkit ──────────────────────────────────────────────────
step "NVIDIA Container Toolkit"

if nvidia-smi &>/dev/null; then
    if ! dpkg -l nvidia-container-toolkit &>/dev/null; then
        info "Installing NVIDIA Container Toolkit..."
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
            sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
        sudo apt-get update -qq
        sudo apt-get install -y -qq nvidia-container-toolkit
        sudo nvidia-ctk runtime configure --runtime=docker
        sudo systemctl restart docker
        log "NVIDIA Container Toolkit installed"
    else
        log "NVIDIA Container Toolkit already installed"
    fi
else
    warn "No GPU found — skipping NVIDIA Container Toolkit"
fi

# ── k3s ───────────────────────────────────────────────────────────────────────
step "k3s Kubernetes"

if kubectl version --client &>/dev/null && k3s --version &>/dev/null; then
    log "k3s already installed: $(k3s --version | head -1)"
else
    info "Installing k3s..."
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik --write-kubeconfig-mode=644" sh -
    sleep 5
    sudo chmod 644 /etc/rancher/k3s/k3s.yaml
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc
    log "k3s installed"
fi

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Wait for k3s node ready
info "Waiting for k3s node to be ready..."
until kubectl get nodes 2>/dev/null | grep -q " Ready"; do sleep 3; done
log "k3s node ready: $(kubectl get nodes --no-headers | awk '{print $1,$2}')"

# ── configure GPU in k3s ──────────────────────────────────────────────────────
step "GPU support in k3s"

if nvidia-smi &>/dev/null; then
    # Patch containerd config for nvidia runtime
    CONTAINERD_CFG="/var/lib/rancher/k3s/agent/etc/containerd/config.toml"
    if [[ -f "$CONTAINERD_CFG" ]] && ! grep -q "nvidia" "$CONTAINERD_CFG" 2>/dev/null; then
        sudo nvidia-ctk runtime configure --runtime=containerd --config="$CONTAINERD_CFG" 2>/dev/null || true
        sudo systemctl restart k3s
        sleep 5
        log "Containerd configured for NVIDIA GPU"
    else
        log "GPU already configured in containerd"
    fi

    # Deploy NVIDIA device plugin
    if ! kubectl get ds nvidia-device-plugin-daemonset -n kube-system &>/dev/null; then
        kubectl apply -f "$SCRIPT_DIR/k8s/nvidia-device-plugin.yaml"
        log "NVIDIA device plugin deployed"
    else
        log "NVIDIA device plugin already running"
    fi
else
    warn "No GPU — NVIDIA device plugin skipped"
fi

# ── local Docker registry ─────────────────────────────────────────────────────
step "Local Docker registry"

if docker ps | grep -q "registry:2"; then
    log "Local registry already running on :5000"
else
    docker run -d --name registry --restart=always -p 5000:5000 registry:2
    log "Local registry started on localhost:5000"
fi

# Tell k3s to trust the local insecure registry
MIRRORS_CFG="/etc/rancher/k3s/registries.yaml"
if [[ ! -f "$MIRRORS_CFG" ]]; then
    sudo tee "$MIRRORS_CFG" > /dev/null << 'REGEOF'
mirrors:
  "localhost:5000":
    endpoint:
      - "http://localhost:5000"
REGEOF
    sudo systemctl restart k3s
    sleep 5
    log "k3s registry mirror configured"
fi

# ── namespace + secrets ───────────────────────────────────────────────────────
step "Kubernetes namespace and secrets"

kubectl apply -f "$SCRIPT_DIR/k8s/00-namespace.yaml"

# Generate secrets from .env
kubectl create secret generic ai-voice-secrets -n ai-voice \
    --from-literal=SARVAM_API_KEY="$SARVAM_API_KEY" \
    --from-literal=LIVEKIT_API_KEY="$LIVEKIT_API_KEY" \
    --from-literal=LIVEKIT_API_SECRET="$LIVEKIT_API_SECRET" \
    --from-literal=ESL_PASSWORD="$ESL_PASSWORD" \
    --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    --dry-run=client -o yaml | kubectl apply -f -

log "Secrets applied"

# ── configmaps ────────────────────────────────────────────────────────────────
step "ConfigMaps"

kubectl apply -f "$SCRIPT_DIR/k8s/configmaps/"
log "ConfigMaps applied"

# ── storage ───────────────────────────────────────────────────────────────────
step "Persistent Volumes"

kubectl apply -f "$SCRIPT_DIR/k8s/storage/"
log "PVCs created"

# ── build docker images ───────────────────────────────────────────────────────
step "Building Docker images"

info "Building ai-agent image..."
docker build -t ai-agent:latest "$SCRIPT_DIR/ai-agent/" -q
docker tag ai-agent:latest localhost:5000/ai-agent:latest
docker push localhost:5000/ai-agent:latest -q
log "ai-agent image pushed"

# Only build training image if training dir has a Dockerfile
if [[ -f "$SCRIPT_DIR/training/Dockerfile" ]]; then
    info "Building training image..."
    docker build -t ai-training:latest "$SCRIPT_DIR/training/" -q
    docker tag ai-training:latest localhost:5000/ai-training:latest
    docker push localhost:5000/ai-training:latest -q
    log "ai-training image pushed"
fi

# ── deploy services ───────────────────────────────────────────────────────────
step "Deploying Kubernetes services"

info "Deploying Redis and PostgreSQL..."
kubectl apply -f "$SCRIPT_DIR/k8s/deployments/redis-deploy.yaml"
kubectl apply -f "$SCRIPT_DIR/k8s/deployments/postgres-deploy.yaml"
kubectl apply -f "$SCRIPT_DIR/k8s/services/redis-svc.yaml"
kubectl apply -f "$SCRIPT_DIR/k8s/services/postgres-svc.yaml"

# Wait for Redis and Postgres
for svc in redis postgres; do
    info "Waiting for $svc..."
    kubectl rollout status deployment/$svc -n ai-voice --timeout=120s
done
log "Redis and PostgreSQL ready"

info "Deploying LiveKit and FreeSWITCH..."
kubectl apply -f "$SCRIPT_DIR/k8s/deployments/livekit-deploy.yaml"
kubectl apply -f "$SCRIPT_DIR/k8s/deployments/freeswitch-deploy.yaml"
kubectl apply -f "$SCRIPT_DIR/k8s/services/livekit-svc.yaml"
kubectl apply -f "$SCRIPT_DIR/k8s/services/freeswitch-svc.yaml"
kubectl rollout status deployment/livekit -n ai-voice --timeout=120s
kubectl rollout status deployment/freeswitch -n ai-voice --timeout=120s
log "LiveKit and FreeSWITCH ready"

# ── vLLM ─────────────────────────────────────────────────────────────────────
step "vLLM (LLM inference server)"

if docker ps --format '{{.Names}}' | grep -q "^vllm-server$"; then
    log "vLLM container already running"
else
    info "Starting vLLM with Qwen2.5-3B-Instruct-AWQ..."
    info "First run downloads ~3GB model weights — this may take 5-10 minutes"

    MODEL_DIR="$SCRIPT_DIR/data/vllm-models"
    LORA_DIR="$SCRIPT_DIR/data/lora-adapter"
    mkdir -p "$MODEL_DIR" "$LORA_DIR"

    # Build lora-modules arg only if adapter exists
    LORA_ARGS=""
    if [[ -d "$LORA_DIR" && -f "$LORA_DIR/adapter_config.json" ]]; then
        LORA_ARGS="--enable-lora --lora-modules voice-agent=/models/lora-adapter"
        info "LoRA adapter found — loading voice-agent adapter"
    fi

    docker run -d --name vllm-server --restart=unless-stopped \
        $(nvidia-smi &>/dev/null && echo "--gpus all") \
        -p 8000:8000 \
        -v "$MODEL_DIR:/models" \
        -e HF_HOME=/models/hub \
        vllm/vllm-openai:v0.6.6 \
        --model Qwen/Qwen2.5-3B-Instruct-AWQ \
        --quantization awq_marlin \
        --enable-chunked-prefill \
        --gpu-memory-utilization 0.7 \
        --max-model-len 4096 \
        $LORA_ARGS

    info "Waiting for vLLM to load model (up to 10 min)..."
    VLLM_UP=false
    for i in $(seq 1 120); do
        if curl -s --max-time 2 http://localhost:8000/health | grep -q "{}"; then
            VLLM_UP=true; break
        fi
        sleep 5
    done
    $VLLM_UP && log "vLLM ready" || warn "vLLM not responding yet — check: docker logs vllm-server"
fi

# ── update vLLM base URL in configmap ─────────────────────────────────────────
VLLM_URL="http://${PUBLIC_IP}:8000/v1"
kubectl patch configmap ai-agent-config -n ai-voice \
    --type merge \
    -p "{\"data\":{\"VLLM_BASE_URL\":\"$VLLM_URL\"}}" 2>/dev/null || true
info "vLLM URL set to $VLLM_URL"

# ── deploy ai-agent ───────────────────────────────────────────────────────────
step "AI Agent"

kubectl apply -f "$SCRIPT_DIR/k8s/deployments/ai-agent-deploy.yaml"
kubectl apply -f "$SCRIPT_DIR/k8s/services/ai-agent-svc.yaml"
kubectl rollout status deployment/ai-agent -n ai-voice --timeout=120s
log "AI Agent deployed"

# ── livekit-sip ───────────────────────────────────────────────────────────────
step "LiveKit SIP bridge"

if [[ -f "$SCRIPT_DIR/k8s/deployments/livekit-sip-deploy.yaml" ]]; then
    kubectl apply -f "$SCRIPT_DIR/k8s/deployments/livekit-sip-deploy.yaml"
    kubectl apply -f "$SCRIPT_DIR/k8s/services/livekit-sip-svc.yaml" 2>/dev/null || true
    log "LiveKit SIP deployed"
fi

# ── verification ──────────────────────────────────────────────────────────────
step "Verification"

echo ""
echo -e "${BOLD}Pods status:${NC}"
kubectl get pods -n ai-voice -o wide 2>&1

echo ""
echo -e "${BOLD}Services:${NC}"
kubectl get svc -n ai-voice 2>&1

echo ""
echo -e "${BOLD}vLLM models available:${NC}"
curl -s http://localhost:8000/v1/models 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for m in d.get('data',[]): print('  •', m['id'])
" || echo "  (vLLM not yet ready)"

# ── summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  ✓  Installation complete!${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${CYAN}Dashboard:${NC}     http://${PUBLIC_IP}:30082"
echo -e "  ${CYAN}vLLM API:${NC}      http://${PUBLIC_IP}:8000/v1/models"
echo -e "  ${CYAN}LiveKit:${NC}       ws://${PUBLIC_IP}:30880"
echo -e "  ${CYAN}FreeSWITCH SIP:${NC} ${PUBLIC_IP}:5060"
echo ""
echo -e "  ${YELLOW}To make a test call:${NC}"
echo -e "  asterisk -rx \"channel originate PJSIP/1002 extension 9999@from-phones\""
echo ""
echo -e "  ${YELLOW}To view live logs:${NC}"
echo -e "  kubectl logs -n ai-voice deployment/ai-agent -f"
echo ""
echo -e "  ${YELLOW}To run LoRA training:${NC}"
echo -e "  cd $SCRIPT_DIR/training && bash run_training.sh"
echo ""
