"""Installer boundary tests. Docker, storage checks and starts are only mocks."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from homelab_lib import catalog, install, wizard
from homelab_lib.source import ROOT, Refused


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="homelab-install-test-")
        self.root = Path(self.temp.name)
        self.site = catalog.site_config(ROOT / "templates/modular/site.example.json")
        self.site.update(data_dir=str(self.root / "data"), state_dir=str(self.root / "state"))
        Path(self.site["data_dir"]).mkdir()
        Path(self.site["state_dir"]).mkdir()
        self.prepared = self.root / "prepared"
        with patch.object(sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", side_effect=["open-webui", "cpu"]), \
                contextlib.redirect_stderr(io.StringIO()):
            wizard.interactive(catalog.load(), self.site, self.prepared)
        self.model = catalog.read_json(self.prepared / "docker-compose.yml")

    def tearDown(self):
        self.temp.cleanup()

    def test_dry_run_checks_storage_without_creating_application_directories(self):
        with patch.object(install, "run", return_value="") as command, \
                patch.object(install.host, "check", return_value={"blocked": False}):
            result = install.execute(self.prepared)
        self.assertFalse(result["started"])
        self.assertFalse(any(Path(self.site["state_dir"]).iterdir()))
        self.assertTrue(any('--storage-only' in c.args[0] for c in command.call_args_list))
        self.assertFalse(any('up' in c.args[0] for c in command.call_args_list))

    def test_existing_project_and_populated_persistence_never_start_or_overwrite(self):
        with patch.object(install, "run", return_value="existing"):
            with self.assertRaises(Refused):install.execute(self.prepared, True, 30)
        (Path(self.site["state_dir"]) / "ollama").mkdir()
        keep = Path(self.site["state_dir"]) / "ollama/keep"
        keep.write_text("synthetic preserved state")
        with patch.object(install, "run", return_value="") as command, \
                patch.object(install.host, "check", return_value={"blocked": False}):
            with self.assertRaises(Refused):install.execute(self.prepared, True, 30)
        self.assertEqual(keep.read_text(), "synthetic preserved state")
        self.assertFalse(any('up' in c.args[0] for c in command.call_args_list))

    def test_unknown_capacity_refuses_before_creating_paths(self):
        with patch.object(install, "run", side_effect=["", Refused("unavailable")]), \
                patch.object(install.host, "check", return_value={"blocked": False}):
            with self.assertRaises(Refused):install.execute(self.prepared, True, 30)
        self.assertFalse(any(Path(self.site["state_dir"]).iterdir()))

    def test_missing_budget_or_default_dry_run_never_installs(self):
        with patch.object(install, "run", return_value="") as command, \
                patch.object(install.host, "check", return_value={"blocked": False}):
            with self.assertRaises(Refused):install.execute(self.prepared, True)
            result = install.execute(self.prepared)
            self.assertFalse(result['started'])
        self.assertFalse(any('up' in c.args[0] for c in command.call_args_list))
        self.assertFalse(any(Path(self.site["state_dir"]).iterdir()))

    def test_explicit_new_install_only_delegates_to_shared_guard_and_keeps_floors(self):
        phrase = "INSTALAR NOVO PROJETO " + ",".join(sorted(self.model["services"]))
        with patch.object(install, "run", return_value="") as command, \
                patch.object(install.host, "check", return_value={"blocked": False}), \
                patch.object(sys.stdin, "isatty", return_value=True), patch("builtins.input", return_value=phrase), \
                contextlib.redirect_stderr(io.StringIO()):
            result = install.execute(self.prepared, True, 30)
        self.assertTrue(result["started"])  # mocked guard only; no daemon exists in this test
        call = command.call_args_list[-1]
        self.assertIn('--new-project-only', call.args[0])
        self.assertIn('up', call.args[0])
        self.assertGreaterEqual(int(call.kwargs['env']['HOMELAB_MIN_FREE_GIB']), 50)
        self.assertGreaterEqual(int(call.kwargs['env']['HOMELAB_MIN_FREE_PERCENT']), 10)
        self.assertEqual(call.kwargs['env']['COMPOSE_REMOVE_ORPHANS'], '0')

    def test_compose_tampering_or_dotenv_refused_before_querying_docker(self):
        model = dict(self.model, name="existing-project")
        (self.prepared / "docker-compose.yml").write_text(json.dumps(model))
        with patch.object(install, "run") as command:
            with self.assertRaises(Refused):install.execute(self.prepared)
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
