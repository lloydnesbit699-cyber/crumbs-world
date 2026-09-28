#!/usr/bin/env python3
"""Smoke-test Melody's real brain_chat: real SYSTEM_PROMPT, real TOOLS,
real key from env. Run in the Replit shell:  python3 tools/brain_smoke.py
Prints OK + reply on success, or the actual exception on failure."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import melody_agent as ma

backs = ma.brain_backends()
print("backends:", [(b[0], b[3]) for b in backs])
if not backs:
    print("NO BACKENDS CONFIGURED (no key in env)")
    sys.exit(2)

messages = [{"role": "system", "content": ma.SYSTEM_PROMPT},
            {"role": "user", "content": "say hi, this is a brain test"}]
try:
    reply, calls, backend = ma.brain_chat(messages, ma.TOOLS)
except Exception as exc:  # noqa: BLE001 - we want the real error text
    print("BRAIN FAILED:", type(exc).__name__ + ":", str(exc)[:600])
    sys.exit(1)

print("OK backend:", backend)
print("reply:", (reply or "")[:200])
print("tool_calls:", len(calls))
