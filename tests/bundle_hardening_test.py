import io
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (tests live in tests/)
sys.path.insert(0, HERE)

import crumbs_hud as h


def _bundle_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("map.json", json.dumps({
            "width": 1, "height": 1, "tiles": [[0]]
        }))
        zf.writestr("manifest.json", json.dumps({
            "app": "crumbs-hud",
            "schema": h.SCHEMA_VERSION,
            "map": "map.json",
        }))
    return buf.getvalue()


def test_import_does_not_replace_file_created_after_collision_check(
        tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_vault_base", lambda: str(tmp_path))
    original_link = os.link

    def create_collision_then_link(source, target):
        with open(target, "x", encoding="utf-8") as f:
            f.write("keep this file")
        return original_link(source, target)

    monkeypatch.setattr(h.os, "link", create_collision_then_link)

    ok, message = h._import_bundle(_bundle_bytes(), "saved.json")

    assert not ok
    assert message == "an import with that name already exists; retry"
    assert (tmp_path / "saved.json").read_text(encoding="utf-8") == "keep this file"
    assert not list(tmp_path.glob("*.import-tmp-*"))
