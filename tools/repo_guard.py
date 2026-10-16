#!/usr/bin/env python3
"""Crumbs World release consistency bot (safe, deterministic repo edits only)."""
from __future__ import annotations

import argparse
import ast
from datetime import date
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFETY_IGNORES = (
    ".crumbs_hud.pid", ".crumbs_secret", "users.json", "users.json.*.bak",
    "vaults/", "bug-reports/", "logs/", "*.log", ".venv/",
    "__pycache__/", "*.pyc", ".pytest_cache/", ".map_thumb_cache/",
    ".crumbs_recovery/", ".crumbs_last_deployed", ".crumbs_deploy_failed",
    ".crumbs_deploy.lock", "backup-keep/", "cleanup-root.py",
    "finish-rename.py", "kill-crumbs.ps1",
)


def _python_string_list(source: str, variable: str) -> list[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise ValueError(f"{variable} must be a literal list of strings")
            return value
    raise ValueError(f"could not find {variable} in crumbs_hud.py")


def _js_array(source: str, variable: str) -> tuple[list[str], re.Match[str]]:
    match = re.search(rf"const\s+{re.escape(variable)}\s*=\s*\[(.*?)\];", source, re.S)
    if not match:
        raise ValueError(f"could not find JavaScript array {variable} in editor.html")
    values = re.findall(r"[\"']([^\"']+)[\"']", match.group(1))
    return values, match


def _format_js_array(variable: str, values: list[str]) -> str:
    lines = "\n".join(f'        "{value}",' for value in values)
    return f"const {variable} = [\n{lines}\n      ];"


def _ensure_ignores(text: str) -> tuple[str, list[str]]:
    present = {line.strip() for line in text.splitlines()}
    missing = [rule for rule in SAFETY_IGNORES if rule not in present]
    if not missing:
        return text, []
    block = "\n# BEGIN CRUMBS MAINTENANCE SAFETY RULES\n"
    block += "\n".join(missing)
    block += "\n# END CRUMBS MAINTENANCE SAFETY RULES\n"
    return text.rstrip() + block, missing


def inspect(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    py_path = root / "crumbs_hud.py"
    html_path = root / "editor.html"
    changelog_path = root / "CHANGELOG.md"
    try:
        py = py_path.read_text(encoding="utf-8")
        html = html_path.read_text(encoding="utf-8")
        changelog = changelog_path.read_text(encoding="utf-8")
        match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', py, re.M)
        if not match:
            errors.append("APP_VERSION is missing or not a quoted literal")
            version = None
        else:
            version = match.group(1)
        top = re.search(r"^##\s+v([^\s—-]+)", changelog, re.M)
        if not top:
            errors.append("CHANGELOG.md has no version heading")
        elif version and top.group(1) != version:
            errors.append(f"CHANGELOG top version v{top.group(1)} != APP_VERSION {version}")

        manifests = {
            "names": _python_string_list(py, "UPDATE_FILES"),
            "artNames": _python_string_list(py, "UPDATE_ART_FILES"),
        }
        for js_name, expected in manifests.items():
            actual, _ = _js_array(html, js_name)
            missing = [name for name in expected if name not in actual]
            extra = [name for name in actual if name not in expected]
            if missing or extra:
                errors.append(f"editor.html {js_name} differs from server manifest; missing={missing}, extra={extra}")
            for name in expected:
                if not (root / name).is_file():
                    errors.append(f"updater manifest references missing file: {name}")
    except (OSError, SyntaxError, ValueError) as exc:
        errors.append(f"release metadata could not be read: {exc}")

    ignore_path = root / ".gitignore"
    try:
        ignores = {line.strip() for line in ignore_path.read_text(encoding="utf-8").splitlines()}
        for rule in SAFETY_IGNORES:
            if rule not in ignores:
                errors.append(f".gitignore is missing safety rule: {rule}")
    except OSError as exc:
        errors.append(f"could not read .gitignore: {exc}")

    if (root / ".git").exists():
        try:
            tracked = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z"],
                check=True, capture_output=True,
            ).stdout.decode("utf-8", "replace").split("\0")
            private = [name for name in tracked if name and (
                name == ".crumbs_secret" or name == "users.json" or
                (name.startswith("users.json.") and name.endswith(".bak")) or
                name.startswith("vaults/") or name.startswith("bug-reports/"))]
            for name in private:
                errors.append(f"private runtime data is tracked by Git: {name}")
        except (OSError, subprocess.CalledProcessError) as exc:
            errors.append(f"could not inspect Git's tracked-file list: {exc}")
    return errors


def fix(root: Path = ROOT) -> list[str]:
    """Repair only updater-manifest parity and missing standard ignore rules."""
    changes: list[str] = []
    py = (root / "crumbs_hud.py").read_text(encoding="utf-8")
    html_path = root / "editor.html"
    html = html_path.read_text(encoding="utf-8")
    for variable, python_name in (("names", "UPDATE_FILES"), ("artNames", "UPDATE_ART_FILES")):
        expected = _python_string_list(py, python_name)
        actual, match = _js_array(html, variable)
        if actual != expected:
            html = html[:match.start()] + _format_js_array(variable, expected) + html[match.end():]
            changes.append(f"synchronized editor.html {variable} with {python_name}")
    if html != html_path.read_text(encoding="utf-8"):
        html_path.write_text(html, encoding="utf-8", newline="\n")

    ignore_path = root / ".gitignore"
    ignore, missing = _ensure_ignores(ignore_path.read_text(encoding="utf-8"))
    if missing:
        ignore_path.write_text(ignore, encoding="utf-8", newline="\n")
        changes.append("added missing safety ignores: " + ", ".join(missing))
    return changes


def create_release(root: Path, notes: str, bump: str = "patch") -> str:
    """Bump APP_VERSION and prepend the matching changelog heading."""
    if not notes or not notes.strip():
        raise ValueError("release notes are required for a version bump")
    py_path = root / "crumbs_hud.py"
    changelog_path = root / "CHANGELOG.md"
    py = py_path.read_text(encoding="utf-8")
    changelog = changelog_path.read_text(encoding="utf-8")
    app_match = re.search(r'(?m)^APP_VERSION\s*=\s*["\'](\d+)\.(\d+)\.(\d+)["\']', py)
    head_match = re.search(r"(?m)^##\s+v(\d+\.\d+\.\d+)\b", changelog)
    if not app_match or not head_match:
        raise ValueError("expected semantic APP_VERSION and a versioned top changelog heading")
    current = ".".join(app_match.groups())
    if head_match.group(1) != current:
        raise ValueError(f"release blocked: changelog has v{head_match.group(1)} but APP_VERSION is {current}")
    major, minor, patch = map(int, app_match.groups())
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    elif bump == "patch":
        patch += 1
    else:
        raise ValueError("bump must be patch, minor, or major")
    version = f"{major}.{minor}.{patch}"
    py = py[:app_match.start(1)] + version + py[app_match.end(3):]
    changelog = changelog[:head_match.start()] + f"## v{version} — {date.today().isoformat()}\n\n{notes.strip()}\n\n" + changelog[head_match.start():]
    py_path.write_text(py, encoding="utf-8", newline="\n")
    changelog_path.write_text(changelog, encoding="utf-8", newline="\n")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="apply safe manifest and .gitignore fixes")
    parser.add_argument("--check", action="store_true", help="check only (the default)")
    parser.add_argument("--release", action="store_true", help="bump APP_VERSION and add changelog notes")
    parser.add_argument("--bump", choices=("patch", "minor", "major"), default="patch")
    parser.add_argument("--notes", help="release notes used with --release")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.release:
        try:
            version = create_release(args.root.resolve(), args.notes or "", args.bump)
            print(f"RELEASE: prepared v{version}")
        except (OSError, ValueError) as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
    if args.fix:
        for change in fix(args.root.resolve()):
            print("FIX: " + change)
    errors = inspect(args.root.resolve())
    if errors:
        for error in errors:
            print("FAIL: " + error, file=sys.stderr)
        return 1
    print("PASS: version, changelog, updater manifests, files, and safety ignores are aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
