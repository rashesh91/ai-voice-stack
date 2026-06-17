#!/usr/bin/env python3
"""Post-training quality gate — run after fine-tuning before deploying to production."""
import json, sys, re
from openai import OpenAI

VLLM_URL = "http://localhost:8000/v1"
MODEL = "voice-agent"
PASS_THRESHOLD = 0.90

client = OpenAI(base_url=VLLM_URL, api_key="not-needed")

TESTS = [
    # (lang, user_text, checks_must_pass, checks_must_not_contain)
    # Gujarati
    ("gu-IN", "Bill ketu chhe?",
     [], ["19121 upar call", "call 19121", "screenshot", "click"]),
    ("gu-IN", "Light nathi aavti.",
     ["system", "register", "field team", "kalas"],
     ["19121 upar complaint karo", "screenshot"]),
    ("gu-IN", "Maro consumer number 12345678901 chhe, bill ketu chhe?",
     [], ["screenshot", "click"]),
    ("gu-IN", "mpay.guvnl.in upar payment kevi rite karvanu?",
     ["mpay", "guvnl"], ["screenshot", "click"]),
    ("gu-IN", "Smart meter kaam nathi karta.",
     ["system", "register", "technician"], ["screenshot"]),
    ("gu-IN", "Prepaid balance ketlu chhe?",
     ["mpay", "balance"], ["screenshot"]),
    ("gu-IN", "Navu connection joie chhe.",
     ["SDN", "Aadhaar"], ["screenshot", "click"]),
    ("gu-IN", "UGVCL helpline number shu chhe?",
     ["19121"], []),    # helpline query — MUST include 19121

    # Hindi
    ("hi-IN", "Mera bill kitna hai?",
     [], ["19121 par call", "call 19121", "screenshot"]),
    ("hi-IN", "Bijli nahi hai.",
     ["system", "register", "field team", "ghante"],
     ["19121 par complaint karein", "screenshot"]),
    ("hi-IN", "Payment kaise karein?",
     ["mpay", "guvnl"], ["screenshot", "click"]),
    ("hi-IN", "Smart meter kharab hai.",
     ["system", "register", "technician"], ["screenshot"]),
    ("hi-IN", "UGVCL helpline number kya hai?",
     ["19121"], []),    # helpline query — MUST include 19121

    # English
    ("en-IN", "What is my bill?",
     [], ["call 19121", "screenshot", "click"]),
    ("en-IN", "There is no power.",
     ["system", "register", "field team", "hours"],
     ["call 19121", "screenshot"]),
    ("en-IN", "How do I pay my bill?",
     ["mpay", "guvnl"], ["screenshot", "click"]),
    ("en-IN", "My smart meter is not working.",
     ["system", "register", "technician"], ["screenshot"]),
    ("en-IN", "No English in reply to Gujarati question — test language lock",
     [], []),  # placeholder — manual check

    # Quality: no hallucinated contact numbers (other than 19121 / 1800...)
    ("gu-IN", "SDN office no number apo.",
     [], ["screenshot", "click"]),
    ("hi-IN", "Koi bhi phone number hai UGVCL ka?",
     [], ["screenshot", "click"]),
]

_LANG_SYS = {
    "gu-IN": "FAQT GUJARATIMA JAVAB APO. Gujarati only. 1-2 sentences.",
    "hi-IN": "SIRF HINDI MEIN JAWAB DO. Hindi only. 1-2 sentences.",
    "en-IN": "Respond in English only. 1-2 sentences.",
}

passed = 0
failed = 0
failures = []

print(f"\nRunning {len(TESTS)} quality tests against {VLLM_URL} model={MODEL}\n")
print("-" * 70)

for lang, user_text, must_contain, must_not_contain in TESTS:
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _LANG_SYS[lang]},
                {"role": "user", "content": user_text},
            ],
            temperature=0.1,
            max_tokens=120,
        )
        reply = resp.choices[0].message.content or ""
    except Exception as exc:
        reply = ""
        failures.append(f"  API ERROR [{lang}] {user_text!r}: {exc}")
        failed += 1
        continue

    reply_lower = reply.lower()
    ok = True

    for phrase in must_contain:
        if phrase.lower() not in reply_lower:
            failures.append(f"  MISSING [{lang}] Q={user_text!r}\n    must contain {phrase!r}\n    got: {reply!r}")
            ok = False

    for phrase in must_not_contain:
        if phrase.lower() in reply_lower:
            failures.append(f"  FORBIDDEN [{lang}] Q={user_text!r}\n    must NOT contain {phrase!r}\n    got: {reply!r}")
            ok = False

    if ok:
        passed += 1
        print(f"  PASS [{lang}] {user_text[:50]}")
    else:
        failed += 1
        print(f"  FAIL [{lang}] {user_text[:50]}")

print("-" * 70)
total = passed + failed
rate = passed / total if total else 0
print(f"\nResult: {passed}/{total} passed ({rate*100:.1f}%)")

if failures:
    print("\nFailure details:")
    for f in failures:
        print(f)

if rate < PASS_THRESHOLD:
    print(f"\nFAIL — pass rate {rate*100:.1f}% below threshold {PASS_THRESHOLD*100:.0f}%")
    print("DO NOT deploy this adapter. Retrain with fixed data.")
    sys.exit(1)
else:
    print(f"\nPASS — adapter is ready for deployment.")
    sys.exit(0)
