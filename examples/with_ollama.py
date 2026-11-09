"""Real-model example: plug any OpenAI-compatible endpoint (local Ollama, etc.) into guard().

Uses only the standard library. Set the variables from .env.example first:

    export LFG_BASE_URL=http://localhost:11434/v1
    export LFG_MODEL=<a model you have pulled>
    # LFG_API_KEY is only needed for hosted endpoints
    python examples/with_ollama.py

Local models can be slow, so the timeout is generous (LFG_TIMEOUT seconds, default 300).
"""

import json
import os
import sys
import urllib.request

from llm_format_guard import guard

BASE_URL = os.environ.get("LFG_BASE_URL", "").rstrip("/")
MODEL = os.environ.get("LFG_MODEL", "")
API_KEY = os.environ.get("LFG_API_KEY", "")
TIMEOUT = float(os.environ.get("LFG_TIMEOUT", "300"))

if not BASE_URL or not MODEL:
    sys.exit("Set LFG_BASE_URL and LFG_MODEL first (see .env.example). "
             "For a no-key demo run examples/quickstart.py instead.")


def call_llm(messages):
    """The only glue guard() needs: a function from a message list to the answer text."""
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False}).encode()
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


messages = [
    {"role": "user", "content": "앞으로 세 줄로 요약해 줘"},
    {"role": "assistant", "content": "네."},
    {"role": "user", "content": "파이썬이 뭐야?"},
]
result = guard(messages, call_llm)
print(result.text)
print(f"\nviolations before={len(result.violations_before)} after={len(result.violations_after)} "
      f"adopted={result.adopted} llm_calls={result.llm_calls}")
