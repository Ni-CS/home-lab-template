"""The public bundle is an explicit hash allowlist, never a working-tree copy."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from homelab_lib import baseline
from homelab_lib.source import Refused


class PublicBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="homelab-public-test-")
        self.folder = Path(self.temp.name)
        self.root = self.folder / "source"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "scripts/clean.py").write_text("# public fixture\n")
        (self.root / "configs").mkdir()
        (self.root / "configs/private.db").write_bytes(b"synthetic-never-read")
        (self.root / ".env").write_text("synthetic-never-read")
        self.manifest = self.folder / "allowlist.json"
        self.items = [{"source": "scripts/clean.py", "destination": "scripts/clean.py",
                       "sha256": hashlib.sha256((self.root / "scripts/clean.py").read_bytes()).hexdigest()}]

    def tearDown(self):
        self.temp.cleanup()

    def export(self, destination=None):
        self.manifest.write_text(json.dumps({"schema_version": 1, "files": self.items}))
        with patch.object(baseline, "ROOT", self.root):
            return baseline.export(destination or self.folder / "bundle", self.manifest)

    def test_only_approved_files_exported_without_git_or_private_configs(self):
        result = self.export()
        target = self.folder / "bundle"
        self.assertFalse(result["git_modified"])
        self.assertTrue((target / "scripts/clean.py").is_file())
        self.assertFalse((target / "configs").exists())
        self.assertFalse((target / ".env").exists())
        self.assertFalse((target / ".git").exists())

    def test_source_drift_refuses_before_creating_bundle(self):
        (self.root / "scripts/clean.py").write_text("# changed after review\n")
        with self.assertRaises(Refused):self.export()
        self.assertFalse((self.folder / "bundle").exists())

    def test_private_source_paths_and_parent_escape_refused(self):
        for name in ["configs/private.db", ".env", "../escape", "/etc/passwd", ".git/config"]:
            with self.assertRaises(Refused):baseline.safe_relative(name)

    def test_symlink_source_and_destination_refused(self):
        (self.root / "scripts/alias.py").symlink_to(self.root / "scripts/clean.py")
        self.items[0]["source"] = "scripts/alias.py"
        with self.assertRaises(Refused):self.export()
        self.items[0]["source"] = "scripts/clean.py"
        parent = self.folder / "link"
        parent.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(Refused):self.export(parent / "bundle")

    def test_existing_destination_no_overwrite_or_merge(self):
        target = self.folder / "bundle"
        target.mkdir()
        (target / "keep").write_text("synthetic")
        with self.assertRaises(Refused):self.export()
        self.assertEqual((target / "keep").read_text(), "synthetic")

    def test_duplicate_destination_and_inside_repo_refused(self):
        self.items *= 2
        with self.assertRaises(Refused):self.export()
        self.items = self.items[:1]
        with self.assertRaises(Refused):self.export(self.root / "bundle")


if __name__ == "__main__":
    unittest.main()
