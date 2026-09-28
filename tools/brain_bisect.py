#!/usr/bin/env python3
"""Bisect the Groq 403: which part of the brain payload triggers it?
Tests: (1) system prompt only, (2) 9 tools only, (3) both (the real shape).
Prints Groq's actual error body on failure. Run: python3 tools/brain_bisect.py"""
import os
import sys
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import melody_agent as ma

backs = ma.brain_backends()
if not backs:
    print("NO BACKENDS CONFIGURED")
    sys.exit(2)
label, url, key, model = backs[0]
print("model:", model)


def post(payload, tag):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.load(resp)
            ch = (body.get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            print(f"[{tag}] HTTP 200 reply: {(msg.get('content') or '')[:80]}")
            return True
    except urllib.error.HTTPError as exc:
        try:
            ebody = exc.read().decode()[:800]
        except Exception:
            ebody = "<unreadable>"
        print(f"[{tag}] HTTP {exc.code}: {ebody}")
        return False


base = {"model": model, "max_tokens": 50, "temperature": 0.7}

print("--- 1: system prompt, NO tools ---")
post(dict(base, messages=[{"role": "system", "content": ma.SYSTEM_PROMPT},
                          {"role": "user", "content": "say hi"}]),
     "sysprompt-only")

print("--- 2: NO system prompt, 9 real tools ---")
post(dict(base, messages=[{"role": "user", "content": "say hi"}],
          tools=ma.TOOLS, tool_choice="auto"),
     "tools-only")

print("--- 3: system prompt + 9 real tools (the real brain shape) ---")
post(dict(base, messages=[{"role": "system", "content": ma.SYSTEM_PROMPT},
                          {"role": "user", "content": "say hi"}],
          tools=ma.TOOLS, tool_choice="auto"),
     "full")
