"""Private metadata manifests and review gates; no real user data or daemon."""

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from homelab_lib import reset
from homelab_lib.source import Refused


class ResetManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="homelab-manifest-test-")
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        for suffix in ["media/downloads", "media/filmes", "media/series", "media/musicas/incoming",
                       "fooocus/models", "fooocus/outputs"]:
            (self.data / suffix).mkdir(parents=True)
        (self.data / "media/downloads/unexpected-audio.flac").write_bytes(b"synthetic-not-real-audio")
        (self.data / "fooocus/models/model.bin").write_bytes(b"synthetic-model")
        (self.data / "fooocus/outputs/preserved.png").write_bytes(b"synthetic-output")
        self.module = reset.planner()
        self.context = {"data_root": str(self.data), "comfy_root": None, "project_directory": str(self.root)}
        self.path = self.root / "homelab-reset-arr.json"
        self.patches = [patch.object(reset, "planner", return_value=self.module),
                        patch.object(self.module, "mount_table", return_value={Path("/"): "ext4", self.data: "ext4"}),
                        patch.object(self.module, "docker_inventory", side_effect=self.module.Blocked("denied")),
                        patch.object(reset, "mount_identity", return_value={"uuid": "fixture-uuid", "fstype": "ext4", "target": "/fixture"}),
                        patch.object(reset, "process_usage", return_value={"inspected_processes": 1, "matching_processes": 0,
                                     "coverage": "incomplete", "absence_of_open_handles_proven": False})]
        for item in self.patches:item.start()

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()

    def capture(self, group="arr-media"):
        return reset.capture(group, self.context)

    def test_private_manifest_music_rescue_never_exposes_filenames_or_copies_content(self):
        record = self.capture()
        self.assertEqual(len(record["music_rescue"]), 1)
        self.assertIn("music_rescue_required_before_arr", record["blockers"])
        self.assertFalse(record["execution_authorized"])
        self.assertFalse(record["music_rescue"][0]["content_integrity_verified"])
        public = json.dumps(reset.public_summary(record))
        self.assertNotIn("unexpected-audio", public)
        self.assertNotIn("fixture-uuid", public)
        self.assertNotIn(str(self.root), public)
        self.assertFalse(any((self.data / "media/musicas/incoming").iterdir()))

    def test_save_0600_no_overwrite_and_mismatched_group_refused(self):
        record = self.capture()
        reset.save(self.path, record)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(reset.read_manifest(self.path, "arr-media")["fingerprint"], record["fingerprint"])
        with self.assertRaises(FileExistsError):reset.save(self.path, record)
        with self.assertRaises(Refused):reset.read_manifest(self.path, "finance-actual")

    def test_manifest_never_written_to_repository_or_symlink(self):
        record = self.capture()
        with self.assertRaises(Refused):reset.save(reset.ROOT / "homelab-reset-private.json", record)
        original = self.root / "keep.json"
        original.write_text("synthetic")
        self.path.symlink_to(original)
        with self.assertRaises(OSError):reset.save(self.path, record)
        with self.assertRaises(OSError):reset.read_manifest(self.path, "arr-media")
        self.assertEqual(original.read_text(), "synthetic")

    def test_changed_file_invalidates_metadata_fingerprint_without_content_hash(self):
        before = self.capture()
        (self.data / "media/downloads/new.mp3").write_bytes(b"new synthetic")
        after = self.capture()
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])

    def test_shared_hardlink_outside_targets_blocks_review(self):
        os.link(self.data / "media/downloads/unexpected-audio.flac", self.root / "preserved-link.flac")
        record = self.capture()
        self.assertIn("hardlinks_outside_observed_roots", record["blockers"])

    def test_fooocus_outputs_are_preserved_manifest_root(self):
        record = self.capture("fooocus-models")
        protected = [r for r in record["roots"] if r["preserve"]]
        self.assertEqual(protected[0]["alias"], "fooocus-outputs-preserve")
        self.assertNotIn("preserved.png", json.dumps(reset.public_summary(record)))

    def test_financial_daemon_unknown_is_blocked_not_empty_or_authorized(self):
        record = self.capture("finance-securo")
        self.assertIn("docker_inventory_unknown", record["blockers"])
        self.assertIsNone(record["protected_container_states"])
        self.assertEqual(record["roots"], [])

    def test_review_requires_tty_specific_group_and_fingerprint(self):
        record = self.capture()
        reset.save(self.path, record)
        args = argparse.Namespace(action="review", group="arr-media", manifest=str(self.path))
        with patch.object(reset.sys.stdin, "isatty", return_value=False):
            with self.assertRaises(Refused):reset.dispatch(args)
        with patch.object(reset.sys.stdin, "isatty", return_value=True), \
                patch.object(reset.sys.stdout, "isatty", return_value=True), \
                patch("builtins.input", return_value="yes"), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(Refused):reset.dispatch(args)
        with patch.object(reset.sys.stdin, "isatty", return_value=True), \
                patch.object(reset.sys.stdout, "isatty", return_value=True), \
                patch("builtins.input", return_value="REVISAR arr-media " + record["fingerprint"][:12]), \
                contextlib.redirect_stderr(io.StringIO()):
            result = reset.dispatch(args)
        self.assertTrue(result["operator_reviewed"])
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(result["blocked"])

    def test_postcheck_does_not_invent_reset_success_and_preserves_audio(self):
        before = self.capture()
        result = reset.postcheck(before, self.capture())
        self.assertFalse(result["targets_absent_or_empty"])
        self.assertTrue(result["preserved_files_metadata_unchanged"])
        self.assertIsNone(result["preserved_containers_unchanged"])
        self.assertFalse(result["target_reset_verified"])

    def test_process_symlinks_only_detect_active_target_and_redact_identifiers(self):
        # Use the real function rather than the capture fixture's process mock.
        self.patches[-1].stop()
        proc = self.root / "fake-proc"
        process = proc / "123"
        (process / "fd").mkdir(parents=True)
        (process / "cwd").symlink_to(self.data / "fooocus/models", target_is_directory=True)
        (process / "exe").symlink_to(self.data / "fooocus/models/model.bin")
        (process / "cmdline").write_text("do-not-read")
        result = reset.process_usage([self.data / "fooocus/models"], proc=proc)
        self.assertEqual(result["matching_processes"], 1)
        self.assertNotIn("123", json.dumps(result))
        self.assertNotIn("do-not-read", json.dumps(result))
        self.assertFalse(result["absence_of_open_handles_proven"])


if __name__ == "__main__":
    unittest.main()
