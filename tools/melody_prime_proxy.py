#!/usr/bin/env python3
"""Loopback-only Groq gateway for Melody Prime.

The game process authenticates with a random bearer token. The Groq API key
is loaded only by this separate process and is never logged or returned.
"""

import argparse
import hmac
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = 8765
UPSTREAM = "https://api.groq.com/openai/v1/chat/completions"
MAX_REQUEST_BYTES = 512 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_IN_FLIGHT = threading.BoundedSemaphore(4)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def make_logger():
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "logs"),
                exist_ok=True)
    log_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "logs", "melody-prime.log"))
    logger = logging.getLogger("melody_prime")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000,
                                      backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


LOG = make_logger()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def check_upstream():
    """Check Groq authentication and configured model without spending a call."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("MELODY_PRIME_MODEL", "openai/gpt-oss-20b").strip()
    if not key:
        print("Groq key is not configured for Prime.", file=sys.stderr)
        return 2
    request = Request(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": "Bearer " + key, "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=15) as response:
            data = json.load(response)
    except HTTPError as exc:
        print("Groq credential check failed (HTTP %d)." % exc.code,
              file=sys.stderr)
        return 3
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        print("Groq credential check failed (%s)." % type(exc).__name__,
              file=sys.stderr)
        return 4
    models = data.get("data", []) if isinstance(data, dict) else []
    if not any(isinstance(row, dict) and row.get("id") == model for row in models):
        print("Groq accepted the credential, but the selected model is unavailable.",
              file=sys.stderr)
        return 5
    print("Groq credential accepted; selected model is available (key hidden).")
    return 0


class PrimeHandler(BaseHTTPRequestHandler):
    server_version = "MelodyPrime/1.0"
    sys_version = ""

    def log_message(self, _format, *_args):
        # Never log client addresses, headers, prompts, or credential material.
        return

    def send_json(self, status, value):
        data = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/healthz":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        key = os.environ.get("GROQ_API_KEY", "").strip()
        token = os.environ.get("MELODY_PROXY_TOKEN", "").strip()
        model = os.environ.get("MELODY_PRIME_MODEL", "openai/gpt-oss-20b")
        self.send_json(200, {"ok": True, "configured": bool(key and token),
                             "provider": "groq", "model": model})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        expected = os.environ.get("MELODY_PROXY_TOKEN", "").strip()
        supplied = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not expected or not supplied.startswith(prefix) or not hmac.compare_digest(
                supplied[len(prefix):].strip(), expected):
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            LOG.warning("request rejected: unauthorized")
            return
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            self.send_json(503, {"ok": False, "error": "Prime is not configured"})
            LOG.error("request rejected: Groq credential missing")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            self.send_json(400, {"ok": False, "error": "invalid content length"})
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self.send_json(413, {"ok": False, "error": "request size not allowed"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
            self.send_json(400, {"ok": False, "error": "invalid chat request"})
            return
        if payload.get("stream"):
            self.send_json(400, {"ok": False, "error": "streaming is not supported"})
            return
        payload["model"] = os.environ.get(
            "MELODY_PRIME_MODEL", "openai/gpt-oss-20b").strip()
        timeout = int(os.environ.get("MELODY_PRIME_TIMEOUT", "60"))
        body = json_bytes(payload)
        request = Request(
            UPSTREAM, data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + api_key,
                     "User-Agent": USER_AGENT})
        if not MAX_IN_FLIGHT.acquire(timeout=1):
            self.send_json(503, {"ok": False, "error": "Prime is busy"})
            return
        started = time.monotonic()
        try:
            with urlopen(request, timeout=timeout) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ValueError("upstream response too large")
                json.loads(data)
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            LOG.info("upstream success latency_ms=%d",
                     int((time.monotonic() - started) * 1000))
        except HTTPError as exc:
            # Do not relay upstream error bodies; they may contain request data.
            LOG.warning("upstream HTTP failure status=%d latency_ms=%d",
                        exc.code, int((time.monotonic() - started) * 1000))
            self.send_json(502, {"ok": False, "error": "Prime upstream failed"})
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            LOG.warning("upstream failure type=%s latency_ms=%d",
                        type(exc).__name__, int((time.monotonic() - started) * 1000))
            try:
                self.send_json(502, {"ok": False, "error": "Prime upstream unavailable"})
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            MAX_IN_FLIGHT.release()


class PrimeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-upstream", action="store_true",
                        help="check Groq key and model availability without a chat completion")
    args = parser.parse_args()
    if args.check_upstream:
        return check_upstream()
    if not os.environ.get("GROQ_API_KEY", "").strip():
        LOG.error("startup refused: Groq credential missing")
        return 2
    if not os.environ.get("MELODY_PROXY_TOKEN", "").strip():
        LOG.error("startup refused: bearer token missing")
        return 2
    try:
        server = PrimeServer((HOST, PORT), PrimeHandler)
    except OSError as exc:
        LOG.error("startup failed: %s", type(exc).__name__)
        return 3
    LOG.info("started host=%s port=%d provider=groq model=%s",
             HOST, PORT, os.environ.get("MELODY_PRIME_MODEL", "openai/gpt-oss-20b"))
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        LOG.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
