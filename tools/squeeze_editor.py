#!/usr/bin/env python3
"""Prepare a smaller, derived editor page without changing editor.html.

The script can externalize supported base64 image data URIs. It uses rjsmin
and rcssmin only when installed; without them it leaves JS/CSS unchanged.
Generated output is written atomically, and image names are content-addressed
so existing assets are never silently overwritten.

Usage:
    python tools/squeeze_editor.py
    python tools/squeeze_editor.py --check  # report only; write nothing
"""

import argparse
import base64
import binascii
import hashlib
import os
import re
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "editor.html"
DST = REPO_ROOT / "editor.min.html"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 24 * 1024 * 1024

try:
    import rjsmin as _rjsmin
except ImportError:
    _rjsmin = None
try:
    import rcssmin as _rcssmin
except ImportError:
    _rcssmin = None

_IMAGE_TYPES = {
    "image/jpeg": ("jpg", lambda b: b.startswith(b"\xff\xd8\xff")),
    "image/png": ("png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/gif": ("gif", lambda b: b.startswith((b"GIF87a", b"GIF89a"))),
    "image/webp": ("webp", lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
}


def _minify_js(source):
    # A home-grown JS minifier can change ASI, template, regex, or comment
    # semantics. Prefer preserving behavior to shrinking a page unsafely.
    return _rjsmin.jsmin(source) if _rjsmin is not None else source


def _minify_css(source):
    # CSS regex minification can alter strings, data URLs, and custom values.
    return _rcssmin.cssmin(source) if _rcssmin is not None else source


def _extract_images(html):
    """Replace valid supported image data URIs with content-addressed files."""
    extracted = {}
    total_bytes = 0

    def replace(match):
        nonlocal total_bytes
        mime = match.group("mime").lower()
        spec = _IMAGE_TYPES.get(mime)
        if spec is None:
            return match.group(0)
        try:
            raw = base64.b64decode(match.group("data"), validate=True)
        except (ValueError, binascii.Error):
            return match.group(0)
        if not raw or len(raw) > MAX_IMAGE_BYTES or not spec[1](raw):
            return match.group(0)
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_IMAGE_BYTES:
            raise ValueError("embedded image data exceeds the 24 MiB extraction limit")
        digest = hashlib.sha256(raw).hexdigest()[:20]
        name = "embedded-%s.%s" % (digest, spec[0])
        extracted[name] = raw
        return match.group("prefix") + name + match.group("suffix")

    # Rewrite only actual resource references. A broad search across the whole
    # page could alter a JavaScript string that happens to contain a data URI.
    pattern = re.compile(
        r"(?P<prefix>\b(?:src|srcset|href)\s*=\s*[\"']?|url\(\s*[\"']?)"
        r"data:(?P<mime>[^;,]+);base64,(?P<data>[A-Za-z0-9+/=]+)"
        r"(?P<suffix>[\"']?\s*\)?)",
        flags=re.IGNORECASE,
    )
    result = pattern.sub(replace, html)
    return result, extracted


def _atomic_write(path, data):
    """Atomically replace a generated file using a temp file in its directory."""
    path = Path(path)
    if path.parent.resolve() != REPO_ROOT:
        raise ValueError("refusing to write outside the repository root")
    if path.is_symlink():
        raise ValueError("refusing to replace a symlink: %s" % path.name)
    fd, temp_name = tempfile.mkstemp(prefix=".squeeze-", suffix=".tmp",
                                     dir=str(REPO_ROOT))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _write_images(images):
    for name, raw in images.items():
        path = REPO_ROOT / name
        if path.is_symlink():
            raise ValueError("refusing to use a symlink image target: %s" % name)
        if path.exists():
            if not path.is_file() or path.read_bytes() != raw:
                raise FileExistsError("existing image differs from generated content: %s" % name)
            continue
        _atomic_write(path, raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report the derived size without writing files")
    args = parser.parse_args()

    if SRC.is_symlink() or not SRC.is_file():
        raise FileNotFoundError("editor.html is missing or is not a regular file")
    html = SRC.read_text(encoding="utf-8")
    original_size = len(html.encode("utf-8"))
    html, images = _extract_images(html)

    def min_js(match):
        return "<script%s>%s</script>" % (match.group(1), _minify_js(match.group(2)))

    def min_css(match):
        return "<style%s>%s</style>" % (match.group(1), _minify_css(match.group(2)))

    # Preserve attributes such as type=module/defer and avoid touching external
    # script resources (including the valid `src =` spelling).
    html = re.sub(r"<script(?![^>]*\bsrc\s*=)([^>]*)>(.*?)</script>",
                  min_js, html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style([^>]*)>(.*?)</style>", min_css, html,
                  flags=re.DOTALL | re.IGNORECASE)

    for stamp in ("%%CRUMBS_VERSION%%", "%%TESTER_SHELL%%"):
        if stamp not in html:
            raise ValueError("required server stamp is missing: %s" % stamp)

    output = html.encode("utf-8")
    print("editor.html:      %10d bytes" % original_size)
    print("editor.min.html:  %10d bytes (%.0f%% of original)" %
          (len(output), len(output) / max(1, original_size) * 100))
    print("images extracted: %s" % (", ".join(
        "%s (%dKB)" % (name, len(raw) // 1024)
        for name, raw in images.items()) or "none"))
    print("JS minifier:  %s" % ("rjsmin" if _rjsmin else "unchanged (safe fallback)"))
    print("CSS minifier: %s" % ("rcssmin" if _rcssmin else "unchanged (safe fallback)"))

    if args.check:
        print("check only: no files written")
        return
    _write_images(images)
    _atomic_write(DST, output)
    print("wrote %s" % DST)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit("squeeze_editor: %s" % exc)
