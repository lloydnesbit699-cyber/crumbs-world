"""pytest bootstrap: make the repo root importable for tests living in tests/.

The suite imports crumbs_hud / crumbs_core / melody_agent directly; those
modules stay at the repo root, so the root goes on sys.path here. Individual
test files also carry their own HERE guard, so `python3 tests/x_test.py`
works without pytest too.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
