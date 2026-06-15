# AI Voice Stack

Production agentic AI voice telephony system for Indian languages.

**Stack:** FreeSWITCH · LiveKit · vLLM · Sarvam.ai · k3s Kubernetes · NVIDIA GPU

## What it does

- Answers inbound SIP calls in 10 Indian languages (Hindi, English, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Marathi, Hinglish)
- Real-time speech-to-text → LLM reasoning → text-to-speech pipeline
- LoRA fine-tunable on your own call transcripts
- Live dashboard showing transcripts and latency

## Quick install (new machine)

```bash
# 1. Clone the repo
git clone https://github.com/rashesh91/ai-voice-stack.git
cd ai-voice-stack

# 2. Set up your API keys
cp .env.example .env
nano .env          # fill in SARVAM_API_KEY, LIVEKIT keys, passwords

# 3. One-command install (15-20 min on first run — downloads model)
bash install.sh
```

Requires: Ubuntu 22.04, NVIDIA GPU (≥16GB VRAM), 100GB disk, 16GB RAM.

## Access after install

| Service | URL |
|---|---|
| **Dashboard** (live calls, transcripts, latency) | `http://YOUR_IP:30082` |
| vLLM API | `http://YOUR_IP:8000/v1/models` |
| LiveKit | `ws://YOUR_IP:30880` |
| FreeSWITCH SIP | `YOUR_IP:5060` |

## Test call

```bash
asterisk -rx "channel originate PJSIP/1002 extension 9999@from-phones"
```

## Demo accounts (say your mobile number during a call)

| Mobile | Name | Bill |
|---|---|---|
| 9876543210 | Ramesh Kumar | ₹450 due Jun 20 |
| 9876543211 | Priya Sharma | ₹780 due Jun 25 |
| 9123456789 | Amit Patel | ₹320 — Account BLOCKED |
| 8800001234 | Sunita Devi | ₹180 due Jun 30 |
| 7700123456 | Vijay Singh | ₹1200 — OVERDUE |
| 9988776655 | Kavita Mehta | ₹650 due Jun 22 |
| 8877665544 | Suresh Yadav | Prepaid ₹199 |
| 7766554433 | Deepika Joshi | ₹3500 Enterprise |
| 9900112233 | Mohammed Rafiq | ₹550 due Jun 28 |
| 8811223344 | Lakshmi Nair | ₹230 due Jul 5 |

Edit `ai-agent/src/agent.py` → `MOCK_ACCOUNTS` to change demo data.

## Architecture

```
PSTN/SIP caller
      │
      ▼
FreeSWITCH (SIP/RTP)
      │ SIP INVITE
      ▼
LiveKit SIP bridge ──► LiveKit Server (WebRTC)
                              │
                              ▼
                        AI Agent (Python)
                         │        │
                    Sarvam STT   Sarvam TTS
                    saaras:v3    bulbul:v2
                    codemix mode
                         │
                         ▼
                    vLLM (Qwen2.5-3B-AWQ + LoRA)
                         │
                      GPU (L4/A10/etc)
```

## LoRA training

```bash
# Add training samples to training/data/train.jsonl
# (chat format: system/user/assistant messages)

# Run training + auto-reload vLLM
cd training && bash run_training.sh
```

## Project structure

```
ai-voice-stack/
├── install.sh              ← one-command installer
├── .env.example            ← copy to .env, fill API keys
├── ai-agent/               ← LiveKit Agents Python app
│   ├── src/agent.py        ← main agent logic, mock accounts
│   ├── src/sarvam_stt.py   ← Sarvam STT with homophone correction
│   ├── src/sarvam_tts.py   ← Sarvam TTS with greeting pre-warm
│   ├── src/dashboard.py    ← web dashboard (port 8082)
│   └── src/vllm_llm.py     ← vLLM OpenAI-compatible client
├── training/               ← LoRA fine-tuning
│   ├── data/train.jsonl    ← training data (chat format)
│   ├── run_training.sh     ← train + reload vLLM
│   └── src/train_lora.py   ← TRL + PEFT training script
├── k8s/                    ← Kubernetes manifests
│   ├── deployments/        ← all service deployments
│   ├── services/           ← ClusterIP / NodePort services
│   ├── configmaps/         ← environment config
│   └── storage/            ← PersistentVolumeClaims
└── freeswitch/             ← FreeSWITCH dialplan config
```

## Key latency numbers (production)

| Metric | Value |
|---|---|
| Greeting latency | ~850ms |
| STT (saaras:v3) | ~400ms |
| LLM first token (3B AWQ) | ~60ms |
| TTS first sentence | ~500ms |
| **Total turn latency** | **~1.2s** |
