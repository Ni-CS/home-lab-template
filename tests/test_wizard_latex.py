"""Interactive staging and private Toolkit configuration with synthetic fixtures."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from homelab_lib import catalog, latex, wizard
from homelab_lib.source import ROOT, Refused, synthetic_model


class WizardLatexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="homelab-wizard-test-")
        self.folder = Path(self.temp.name)
        self.site = catalog.site_config(ROOT / "templates/modular/site.example.json")
        self.data = catalog.load()

    def tearDown(self):
        self.temp.cleanup()

    def test_interactive_cpu_selection_generates_private_compose_and_dashboard_without_start(self):
        destination = self.folder / "installation"
        with patch.object(sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", side_effect=["open-webui,navidrome", "cpu"]), \
                contextlib.redirect_stderr(io.StringIO()):
            result = wizard.interactive(self.data, self.site, destination)
        self.assertFalse(result["started"])
        self.assertFalse(result["downloaded"])
        model = json.loads((destination / "docker-compose.yml").read_text())
        self.assertIn("ollama", model["services"])
        self.assertNotIn("fooocus", model["services"])
        self.assertNotIn("nvidia", json.dumps(model).lower())
        self.assertEqual((destination / "site.local.json").stat().st_mode & 0o777, 0o600)
        self.assertTrue((destination / "homepage/custom.css").exists())
        self.assertIn("desconhecido", (destination / "homepage/services.yaml").read_text())

    def test_unknown_selection_and_non_terminal_create_nothing(self):
        destination = self.folder / "installation"
        with patch.object(sys.stdin, "isatty", return_value=False):
            with self.assertRaises(Refused):wizard.interactive(self.data, self.site, destination)
        with patch.object(sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", side_effect=["unknown-module", "cpu"]), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(Refused):wizard.interactive(self.data, self.site, destination)
        self.assertFalse(destination.exists())

    def test_toolkit_config_private_loopback_no_socket_and_separate_databases(self):
        destination = self.folder / "latex-config"
        with patch.object(latex.secrets, "token_urlsafe", return_value="synthetic-test-token"):
            result = latex.scaffold(destination, self.site, "6.0.0", 3007)
        rc = (destination / "overleaf.rc").read_text()
        self.assertIn("SERVER_PRO=false", rc)
        self.assertIn("SIBLING_CONTAINERS_ENABLED=false", rc)
        self.assertIn("OVERLEAF_LISTEN_IP=127.0.0.1", rc)
        self.assertIn("PROJECT_NAME=homelab-latex", rc)
        self.assertNotIn("docker.sock", rc)
        self.assertNotIn("immich", rc)
        self.assertEqual((destination / "variables.env").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("synthetic-test-token", json.dumps(result))
        self.assertFalse(result["started"])
        with self.assertRaises(Refused):latex.scaffold(destination, self.site, "6.0.0")

    def test_toolkit_refuses_unreviewed_version_public_url_and_parent_paths(self):
        destination = self.folder / "latex-config"
        for version in ["latest", "main", "5.0.0", "6.0.0;echo bad"]:
            with self.assertRaises(Refused):latex.scaffold(destination, self.site, version)
        self.site["base_url"] = "http://8.8.8.8"
        with self.assertRaises(Refused):latex.scaffold(destination, self.site, "6.0.0")
        with self.assertRaises(Refused):latex.private_directory(self.folder / "../escape")
        self.assertFalse(destination.exists())

    def test_latex_selection_is_explicit_external_toolkit_module(self):
        result = catalog.plan(self.data, ["latex-overleaf"], "cpu")
        self.assertEqual(result["external_toolkit_modules"], ["latex-overleaf"])
        self.assertNotIn("latex-overleaf", result["services"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
