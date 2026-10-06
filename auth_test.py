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

print("== thumbnail vault isolation (v5.38.1) ==")
import io as _io


class _FakeThumbHandler:
    def __init__(self):
        self.headers = {}
        self.status = None
        self.wfile = _io.BytesIO()
        self.json_sent = None

    def send_response(self, c):
        self.status = c

    def send_header(self, k, v):
        self.headers[k] = v

    def end_headers(self):
        pass

    def _send_json(self, obj, code=200):
        self.json_sent = (obj, code)


_THUMB_TID = 7777
_save_vault, _save_cache, _save_public = h._active_vault, h._thumb_cache, h.PUBLIC_MODE
_orig_load_users = h._load_users
h.assets.tiles.pop(_THUMB_TID, None)
try:
    h.PUBLIC_MODE = True  # vault namespacing only applies in public mode
    _red = h.core.Image.new("RGBA", (32, 32), (255, 0, 0, 255))
    _blue = h.core.Image.new("RGBA", (32, 32), (0, 0, 255, 255))
    _cacheA, _cacheB = {}, {}

    # vault A snapshots its (red) art...
    h._active_vault, h._thumb_cache = "vaultA", _cacheA
    h.assets.tiles[_THUMB_TID] = {"frames": [_red]}
    _snapA = h._snapshot_tile_art(_THUMB_TID, "-")
    check("vault A snapshot captured", _snapA is not None and _snapA[0] == "img")
    check("snapshot holds vault A's own dict", _snapA[2] is _cacheA)
    check("cache key namespaced by vault", _snapA[3][0] == "vaultA")

    # ...then vault B activates BEFORE A's bytes are served (the interleave)
    h._active_vault, h._thumb_cache = "vaultB", _cacheB
    h.assets.tiles[_THUMB_TID] = {"frames": [_blue]}
    _snapB = h._snapshot_tile_art(_THUMB_TID, "-")

    _fa, _fb = _FakeThumbHandler(), _FakeThumbHandler()
    h.Handler._serve_thumb_snapshot(_fa, _snapA)
    h.Handler._serve_thumb_snapshot(_fb, _snapB)
    check("both thumbnails served 200", _fa.status == 200 and _fb.status == 200)
    _keyA, _keyB = _snapA[3], _snapB[3]
    check("A's bytes cached under A's key in A's dict", _keyA in _cacheA)
    check("B's bytes cached under B's key in B's dict", _keyB in _cacheB)
    check("no cross-vault cache write",
          _keyA not in _cacheB and _keyB not in _cacheA)
    check("vaults got their own art, not each other's",
          _cacheA[_keyA] != _cacheB[_keyB])
    _cc = _fa.headers.get("Cache-Control", "")
    check("thumbnail Cache-Control is private", "private" in _cc, _cc)
    check("thumbnail Cache-Control is not public", "public" not in _cc, _cc)

    # write-key request, no session, no owner record -> must deny, never
    # inherit the ambient vault
    h._load_users = lambda: {}
    _fh = _FakeThumbHandler()
    _fh._session_user = lambda: None
    _fh._write_key_ok = lambda: True
    h._active_vault = "someone_elses_vault"
    _r = h.Handler._auth_activate(_fh, "/api/thumb/5")
    check("no-vault identity denied", _r is False)
    check("ambient vault untouched on deny",
          h._active_vault == "someone_elses_vault")
    check("deny is 403", _fh.json_sent is not None and _fh.json_sent[1] == 403)
finally:
    h._load_users = _orig_load_users
    h._active_vault, h._thumb_cache = _save_vault, _save_cache
    h.PUBLIC_MODE = _save_public
    h.assets.tiles.pop(_THUMB_TID, None)

print("== patrol stop pauses (_clean_pauses) ==")
check("clean list passes through",
      h._clean_pauses([{"secs": 10, "mode": "stand"},
                       {"secs": 300, "mode": "sleep"}], 2)
      == [{"secs": 10, "mode": "stand"}, {"secs": 300, "mode": "sleep"}])
check("secs clamped to 3600",
      h._clean_pauses([{"secs": 99999, "mode": "stand"}], 1)[0]["secs"] == 3600)
check("negative secs clamped to 0",
      h._clean_pauses([{"secs": -5, "mode": "stand"}], 1)[0]["secs"] == 0)
check("bad secs become 0",
      h._clean_pauses([{"secs": "soon", "mode": "stand"}], 1)[0]["secs"] == 0)
check("unknown mode becomes stand",
      h._clean_pauses([{"secs": 5, "mode": "dance"}], 1)[0]["mode"] == "stand")
check("missing mode becomes stand",
      h._clean_pauses([{"secs": 5}], 1)[0] == {"secs": 5, "mode": "stand"})
check("non-dict entry becomes idle stand",
      h._clean_pauses(["nap"], 1)[0] == {"secs": 0, "mode": "stand"})
check("length mismatch rejected",
      h._clean_pauses([{"secs": 5, "mode": "stand"}], 2) is None)
check("non-list rejected", h._clean_pauses("nope", 1) is None)
check("zero stays zero (walk on)",
      h._clean_pauses([{"secs": 0, "mode": "sleep"}], 1)[0]["secs"] == 0)

print("== owner device registration (v5.56) ==")
# Device helpers write users.json; point it at a temp dir so the real user
# database is never touched (same pattern as the _create_user tests above).
_tmpd = tempfile.mkdtemp(prefix="auth-devices-")
_orig_users_file2 = h._USERS_FILE
_orig_vaults_dir2 = h._vaults_dir
h._USERS_FILE = os.path.join(_tmpd, "users.json")
h._vaults_dir = lambda: os.path.join(_tmpd, "vaults")
try:
    ok, err = h._create_user("devowner", "s3cret!!", is_owner=True)
    check("owner created", ok, err)
    users = h._load_users()
    check("no devices initially", h._owner_devices(users) == [])

    # enrollment codes: issue -> peek -> redeem -> gone (single-use)
    code = h._enroll_issue("devowner")
    check("code is 8 chars, no look-alikes", len(code) == 8 and
          all(c in "abcdefghjkmnpqrstuvwxyz23456789" for c in code), code)
    check("peek returns the user", h._enroll_peek(code) == "devowner")
    check("redeem returns the user", h._enroll_redeem(code) == "devowner")
    check("redeemed code is dead", h._enroll_peek(code) is None)
    check("bogus code peeks None", h._enroll_peek("zzzzzzzz") is None)
    check("bogus code redeems None", h._enroll_redeem("zzzzzzzz") is None)

    # registration: token validates, wrong token does not
    dev, raw = h._register_device(users, "devowner", "Test iPhone")
    check("register returns record + raw token",
          isinstance(dev, dict) and isinstance(raw, str) and len(raw) >= 32)
    check("label stored", dev.get("label") == "Test iPhone")
    check("only the hash is stored",
          dev.get("token_hash") == h._device_token_hash(raw) and
          "token" not in str(dev.get("token_hash")))
    users = h._load_users()
    hit = h._device_token_ok(users, raw)
    check("presented token validates",
          isinstance(hit, dict) and hit.get("id") == dev.get("id"))
    check("wrong token rejected", h._device_token_ok(users, "nope") is None)
    check("empty token rejected", h._device_token_ok(users, "") is None)
    check("device listed", len(h._owner_devices(h._load_users())) == 1)

    # a second device enrolls independently; revoking is list surgery
    dev2, raw2 = h._register_device(h._load_users(), "devowner", "PC")
    users = h._load_users()
    check("two devices", len(h._owner_devices(users)) == 2)
    check("second token validates",
          h._device_token_ok(users, raw2).get("id") == dev2.get("id"))
    check("first still validates",
          h._device_token_ok(users, raw).get("id") == dev.get("id"))

    # non-owner accounts are never device-gated
    ok2, err2 = h._create_user("devplayer", "s3cret!!")
    check("player created", ok2, err2)
    check("owner devices unchanged by player",
          len(h._owner_devices(h._load_users())) == 2)

    # UA labeling
    check("iphone UA", h._device_label_from_ua(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)") == "iPhone")
    check("windows UA", h._device_label_from_ua(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == "Windows PC")
    check("empty UA", h._device_label_from_ua("") == "Browser")

    # cookie format
    cv = h._device_cookie_value("tok123")
    check("device cookie format",
          "crumbs_dev=tok123" in cv and "HttpOnly" in cv and
          "SameSite=Lax" in cv and "Max-Age=31536000" in cv, cv)
finally:
    h._USERS_FILE = _orig_users_file2
    h._vaults_dir = _orig_vaults_dir2
    shutil.rmtree(_tmpd, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
