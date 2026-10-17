import tempfile
import unittest
from pathlib import Path
import subprocess

import repo_guard


class RepoGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="crumbs-repo-guard-")
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "crumbs_hud.py").write_text(
            'APP_VERSION = "1.2.3"\nUPDATE_FILES = ["editor.html", "crumbs_hud.py"]\n'
            'UPDATE_ART_FILES = ["logo.png"]\n', encoding="utf-8")
        (self.root / "editor.html").write_text(
            'const names = ["editor.html"];\nconst artNames = ["logo.png"];\n',
            encoding="utf-8")
        (self.root / "docs" / "CHANGELOG.md").write_text(
            "# Changes\n\n## v1.2.3 — today\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("# local files\n", encoding="utf-8")
        for name in ("editor.html", "crumbs_hud.py", "logo.png"):
            (self.root / name).touch()

    def tearDown(self):
        self.temp.cleanup()

    def test_finds_manifest_mismatch_and_missing_secret_ignores(self):
        failures = repo_guard.inspect(self.root)
        self.assertTrue(any("names differs from server manifest" in item for item in failures), failures)
        self.assertTrue(any(".crumbs_secret" in item for item in failures), failures)

    def test_fix_syncs_js_lists_and_adds_safety_ignores(self):
        changes = repo_guard.fix(self.root)
        self.assertTrue(changes)
        self.assertEqual(repo_guard.inspect(self.root), [])
        self.assertEqual(repo_guard.fix(self.root), [])

    def test_check_rejects_version_changelog_mismatch(self):
        (self.root / "docs" / "CHANGELOG.md").write_text("# Changes\n\n## v1.2.2 — old\n", encoding="utf-8")
        self.assertTrue(any("CHANGELOG top version" in item for item in repo_guard.inspect(self.root)))

    def test_check_rejects_tracked_private_profile_data(self):
        if not __import__("shutil").which("git"):
            self.skipTest("git is unavailable")
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        secret = self.root / ".crumbs_secret"
        secret.write_text("not a real secret", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", ".crumbs_secret"], check=True)
        failures = repo_guard.inspect(self.root)
        self.assertTrue(any("private runtime data is tracked by Git" in item for item in failures), failures)

    def test_release_bumps_version_and_changelog_together(self):
        version = repo_guard.create_release(self.root, "Add a safe release test.", "minor")
        self.assertEqual(version, "1.3.0")
        py = (self.root / "crumbs_hud.py").read_text(encoding="utf-8")
        log = (self.root / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn('APP_VERSION = "1.3.0"', py)
        self.assertTrue(log.startswith("# Changes\n\n## v1.3.0 — "))
        repo_guard.fix(self.root)
        self.assertEqual(repo_guard.inspect(self.root), [])

    def test_deploy_is_gated_by_green_main_commit_and_health_check(self):
        workflow = (repo_guard.ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
        deploy = (repo_guard.ROOT / "deployment/harley_verified_deploy.ps1").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", workflow)
        self.assertIn("name: repo-verify", workflow)
        self.assertIn("$latestCheck.conclusion -ne 'success'", deploy)
        self.assertIn("$origin -notmatch", deploy)
        self.assertIn("$localBranch -ne $branch", deploy)
        self.assertIn("merge-base --is-ancestor", deploy)
        self.assertIn("Wait-ForVersion", deploy)
        self.assertIn("@('reset', '--hard', $oldHead)", deploy)


if __name__ == "__main__":
    unittest.main()
