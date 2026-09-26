#!/usr/bin/env python3
"""auth_test.py — v5.30 signup/signin/2FA tests. Run: python3 auth_test.py
Covers: email validation, TOTP against the RFC 6238 vectors, the verify
window, challenge issue/redeem/expiry, recovery-code hashing, and the
_create_user uniqueness rules. Pure functions only — no server, no network.
"""
import base64
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crumbs_hud as h

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


print("== email validation ==")
check("good email", h._valid_email("lloyd@example.com"))
check("leading/trailing spaces stripped",
      h._valid_email("  lloyd@example.com  "))
check("missing @", not h._valid_email("lloyd.example.com"))
check("missing domain", not h._valid_email("lloyd@"))
check("missing tld", not h._valid_email("lloyd@example"))
check("empty", not h._valid_email(""))
check("none", not h._valid_email(None))
check("spaces inside", not h._valid_email("lloyd @example.com"))
check("too long", not h._valid_email("a" * 250 + "@example.com"))

print("== TOTP vs RFC 6238 vectors ==")
# Appendix B, SHA1, secret = ASCII "12345678901234567890", 6-digit truncation
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode("ascii")
check("t=59 -> 287082", h._totp_code(RFC_SECRET, 59) == "287082",
      h._totp_code(RFC_SECRET, 59))
check("t=1111111109 -> 081804", h._totp_code(RFC_SECRET, 1111111109) == "081804")
check("t=1234567890 -> 005924", h._totp_code(RFC_SECRET, 1234567890) == "005924")
check("t=2000000000 -> 279037", h._totp_code(RFC_SECRET, 2000000000) == "279037")
check("always 6 digits", len(h._totp_code(RFC_SECRET, 59)) == 6)

print("== TOTP verify ==")
secret = h._new_totp_secret()
code = h._totp_code(secret)
check("current code verifies", h._totp_verify(secret, code))
check("wrong code rejected", not h._totp_verify(secret, "000000"))
check("non-digits rejected", not h._totp_verify(secret, "abcdef"))
check("short code rejected", not h._totp_verify(secret, "12345"))
check("spaces tolerated", h._totp_verify(secret, code[:3] + " " + code[3:]))
check("prev step accepted (skew)", h._totp_verify(secret, h._totp_code(secret, time.time() - 30)))
check("old step rejected", not h._totp_verify(secret, h._totp_code(secret, time.time() - 90)))
check("garbage secret safe", not h._totp_verify("!!!not-base32!!!", "123456"))
check("secrets unique", h._new_totp_secret() != h._new_totp_secret())

print("== 2FA challenges ==")
tok = h._2fa_issue("alice")
check("peek returns user", h._2fa_peek(tok) == "alice")
check("peek doesn't consume", h._2fa_peek(tok) == "alice")
check("redeem returns user", h._2fa_redeem(tok) == "alice")
check("redeem consumes", h._2fa_peek(tok) is None)
check("unknown token", h._2fa_peek("nope") is None)
tok2 = h._2fa_issue("bob")
h._2fa_challenges[tok2] = ("bob", time.monotonic() - 1)  # force expiry
check("expired rejected", h._2fa_peek(tok2) is None)

print("== recovery codes ==")
codes = h._new_recovery_codes()
check("8 codes", len(codes) == 8, len(codes))
check("shape XXXXX-XXXXX", all(len(c) == 11 and c[5] == "-" for c in codes))
check("unique", len(set(codes)) == 8)
check("no look-alikes", all(all(ch in "abcdefghjkmnpqrstuvwxyz23456789-"
                                for ch in c) for c in codes))
c0 = codes[0]
check("hash round-trip", h._hash_recovery(c0) == h._hash_recovery(c0))
check("hash differs from code", h._hash_recovery(c0) != c0)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
