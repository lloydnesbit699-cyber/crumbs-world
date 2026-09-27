#!/usr/bin/env python3
"""auth_test.py — v5.30 signup/signin/2FA tests. Run: python3 auth_test.py
Covers: email validation, phone validation (v5.32), TOTP against the
RFC 6238 vectors, the verify window, challenge issue/redeem/expiry,
recovery-code hashing, the _create_user uniqueness + phone rules, and the
v5.36 signup-time 2FA pending tickets + otpauth URL helper.
Pure functions only — no server, no network.
"""
import base64
import os
import shutil
import sys
import tempfile
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

print("== phone validation (v5.32) ==")
check("empty ok (optional)", h._valid_phone(""))
check("none ok (optional)", h._valid_phone(None))
check("us dashes", h._valid_phone("229-582-0009"))
check("intl plus", h._valid_phone("+1 (229) 582-0009"))
check("dots", h._valid_phone("229.582.0009"))
check("parens and spaces", h._valid_phone("(229) 582 0009"))
check("leading/trailing spaces stripped", h._valid_phone("  229-582-0009  "))
check("32 chars ok", h._valid_phone("1" * 32))
check("letters rejected", not h._valid_phone("call-me-maybe"))
check("garbage rejected", not h._valid_phone("not-a-number!!!"))
check("no digits rejected", not h._valid_phone("+()- "))
check("33 chars rejected", not h._valid_phone("1" * 33))

print("== _create_user phone ==")
# _create_user writes users.json + a vault dir; point both at a temp dir so
# the real user database is never touched. The signup handler returns 400
# "enter a valid phone number" exactly when _valid_phone rejects, which the
# cases above already cover.
_tmpu = tempfile.mkdtemp(prefix="auth-phone-")
_orig_users_file = h._USERS_FILE
_orig_vaults_dir = h._vaults_dir
h._USERS_FILE = os.path.join(_tmpu, "users.json")
h._vaults_dir = lambda: os.path.join(_tmpu, "vaults")
try:
    ok, err = h._create_user("phonecarl", "s3cret!!",
                             email="carl@example.com",
                             phone="+1 (229) 582-0009")
    check("signup with phone succeeds", ok, err)
    rec = h._load_users().get("phonecarl")
    check("phone stored on record",
          isinstance(rec, dict) and rec.get("phone") == "+1 (229) 582-0009",
          rec.get("phone") if isinstance(rec, dict) else rec)
    ok2, err2 = h._create_user("nophone", "s3cret!!",
                               email="nophone@example.com")
    check("signup without phone succeeds", ok2, err2)
    rec2 = h._load_users().get("nophone")
    check("phone empty when omitted",
          isinstance(rec2, dict) and not rec2.get("phone"),
          rec2.get("phone") if isinstance(rec2, dict) else rec2)
    ok3, err3 = h._create_user("badphone", "s3cret!!",
                               email="bad@example.com",
                               phone="not-a-number!!!")
    check("bad phone rejected", not ok3 and err3 == "bad phone", err3)
    check("bad phone not stored", "badphone" not in h._load_users())
finally:
    h._USERS_FILE = _orig_users_file
    h._vaults_dir = _orig_vaults_dir
    shutil.rmtree(_tmpu, ignore_errors=True)

print("== signup-time 2FA pending tickets (v5.36) ==")
_rec = {"username": "tfa-newbie", "password": "s3cret!!",
        "email": "newbie@example.com", "phone": "",
        "totp_secret": h._new_totp_secret()}
_t = h._signup_pending_issue(_rec)
check("ticket issued", isinstance(_t, str) and len(_t) >= 16)
_t2 = h._signup_pending_issue(dict(_rec))
check("tickets unique", _t != _t2)
check("peek returns record", h._signup_pending_peek(_t) == _rec)
check("peek doesn't consume", h._signup_pending_peek(_t) == _rec)
check("redeem returns record", h._signup_pending_redeem(_t) == _rec)
check("redeem consumes", h._signup_pending_peek(_t) is None)
check("unknown ticket peek", h._signup_pending_peek("nope") is None)
check("unknown ticket redeem", h._signup_pending_redeem("nope") is None)
h._signup_pending[_t2] = (_rec, time.monotonic() - 1)  # force expiry
check("expired peek rejected", h._signup_pending_peek(_t2) is None)
check("expired redeem rejected", h._signup_pending_redeem(_t2) is None)

print("== otpauth URL helper (v5.36) ==")
_u = h._totp_otpauth_url("alice", "JBSWY3DPEHPK3PXP")
check("url carries secret", "secret=JBSWY3DPEHPK3PXP" in _u)
check("url carries user", "CrumbsHUD:alice" in _u)
check("url carries issuer+period", "issuer=CrumbsHUD" in _u and "period=30" in _u)

print("== otpauth URI structure for QR (v5.38) ==")
from urllib.parse import urlparse, parse_qs
_p = urlparse(_u)
_q = parse_qs(_p.query)
check("scheme is otpauth", _p.scheme == "otpauth")
check("type is totp", _p.netloc == "totp")
check("label is issuer:account", _p.path.strip("/") == "CrumbsHUD:alice")
check("secret param present", _q.get("secret") == ["JBSWY3DPEHPK3PXP"])
check("issuer param matches label", _q.get("issuer") == ["CrumbsHUD"])
check("digits=6 period=30", _q.get("digits") == ["6"] and _q.get("period") == ["30"])
# worst case: 24-char username still fits a version-10-M QR (byte mode cap 233)
_long = h._totp_otpauth_url("a" * 24, "A" * 32)
check("max url under QR byte-mode cap", len(_long) <= 233)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
