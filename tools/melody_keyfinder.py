"""melody_keyfinder.py -- find Lloyd's Groq key and load it for Melody.

Import this BEFORE anything reads GROQ_API_KEY from the environment:

    import melody_keyfinder  # noqa: F401 -- loads key into os.environ

Search order (first valid file wins):
  1. /home/david/token/Melodys_API_Key    (Lloyd's preferred name)
  2. /mnt/toybox2/david/.melody-groq-key  (service's expected path)
  3. ~/.melody-groq-key                   (home-directory fallback)

For each candidate the finder will:
  * skip it if it does not exist or is not a regular file,
  * ENFORCE owner-only permissions (chmod 600) when group/other bits are
    set and the chmod succeeds -- files it cannot tighten are skipped,
  * parse the key from either `export GROQ_API_KEY='...'` form or a bare
    key on its own line.

The key value is never printed or logged -- only which file was used.

Stdlib only. Safe to import at server startup.
"""

import os
import re
import stat
import sys

SEARCH_PATHS = [
    "/home/david/token/Melodys_API_Key",
    "/mnt/toybox2/david/.melody-groq-key",
    os.path.expanduser("~/.melody-groq-key"),
]

if os.name == "nt":  # Windows (Harley): same idea, local paths.
    _windir = os.path.expanduser("~")
    _repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (keyfinder lives in tools/)
    SEARCH_PATHS = [
        # The owner keeps the credential in an extensionless file inside the
        # active Desktop checkout. Search contents, not the filename.
        os.path.join(_windir, "OneDrive", "Desktop", "crumbs-world",
                     "melody", "not_trash"),
        # The owner's exported key file has also lived directly in the
        # repo's melody/ folder (including this checkout's Vault location).
        # Search it by its stable filename rather than assuming a Desktop
        # checkout path.
        os.path.join(_repo_dir, "melody", "Groq_Files.txt"),
        os.path.join(_repo_dir, "melody", "Groq_Files"),
        # Also support a copy stored beside this module.
        os.path.join(_repo_dir, "melody", "not_trash"),
        os.path.join("C:\\Melody", "Melodys_API_Key"),
        os.path.join(_windir, ".melody-groq-key"),
    ]

_ENV_VAR = "GROQ_API_KEY"
_EXPORT_RE = re.compile(r"""GROQ_API_KEY\s*=\s*['"]?([^'"\s;#]+)['"]?""")


def _note(msg):
    sys.stderr.write("[melody_keyfinder] %s\n" % msg)


def _tighten(path):
    """Enforce owner-only permissions. True if the file is now safe to read."""
    if os.name == "nt":
        # Windows uses ACLs, not Unix mode bits -- the key file lives in
        # the user's own profile/service dir, which is private by default.
        # The bootstrap script locks it down further with icacls.
        return True
    try:
        st = os.stat(path)
    except OSError:
        return False
    if not stat.S_ISREG(st.st_mode):
        return False
    if st.st_mode & 0o077:
        # Group or other could read it -- tighten to owner-only.
        try:
            os.chmod(path, 0o600)
        except OSError:
            _note("cannot tighten permissions on %s, skipping" % path)
            return False
        try:
            st = os.stat(path)
        except OSError:
            return False
        if st.st_mode & 0o077:
            return False
        _note("enforced chmod 600 on %s" % path)
    return True


def _parse_key(text):
    m = _EXPORT_RE.search(text or "")
    if m:
        key = m.group(1).strip()
        if key:
            return key
    stripped = (text or "").strip()
    # Bare-key file: one token, no '=' and no whitespace.
    if stripped and "=" not in stripped and len(stripped.split()) == 1:
        return stripped
    return ""


def _candidate_paths():
    """Return configured paths plus named Groq exports in melody/tools."""
    paths = list(SEARCH_PATHS)
    if os.name == "nt":
        # Support named exports regardless of whether the key was placed in
        # melody/ or melody/tools/. Keep discovery filename-based; never walk
        # arbitrary directories or print file contents.
        for export_dir in (os.path.join(_repo_dir, "melody"),
                           os.path.join(_repo_dir, "melody", "tools")):
            try:
                with os.scandir(export_dir) as entries:
                    named_exports = [
                        entry.path for entry in entries
                        if entry.is_file()
                        and os.path.splitext(entry.name)[0].casefold()
                        in ("groq_files", "groq-files")
                    ]
            except OSError:
                named_exports = []
            paths.extend(sorted(named_exports, key=str.casefold))
    return paths


def find_key():
    """Return (path, key) for the first usable key file, else (None, None)."""
    for path in _candidate_paths():
        if not path or not os.path.isfile(path):
            continue
        if not _tighten(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                key = _parse_key(f.read())
        except OSError:
            continue
        if key:
            return path, key
    return None, None


def load():
    """Load the key into the environment. Returns the file used, or None."""
    if os.environ.get(_ENV_VAR, "").strip():
        _note("using %s already present in environment" % _ENV_VAR)
        return None
    path, key = find_key()
    if path and key:
        os.environ[_ENV_VAR] = key
        _note("loaded key from %s" % path)
        return path
    _note("WARNING: no Groq key file found; starting without a key")
    return None


load()
