"""Real installed Compose parser only; never contacts a daemon or reads .env."""

import json
import shutil
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from homelab_lib import catalog
from homelab_lib.source import ROOT, synthetic_model


@unittest.skipUnless(shutil.which("docker"), "Docker CLI parser not installed")
class ModularSyntaxTests(unittest.TestCase):
    def test_current_compose_and_catalog_match_without_real_env(self):
        if not (ROOT / "docker-compose.yml").exists():
            self.skipTest("public bundle does not contain the installed Compose")
        self.assertTrue(catalog.check_local(catalog.load())["matches_local_compose"])

    def test_every_renderable_cpu_and_two_real_gpu_variants_parse(self):
        data = catalog.load()
        site = catalog.site_config(ROOT / "templates/modular/site.example.json")
        selections = [[s["id"]] for s in data["services"] if s["availability"] == "renderable"]
        selections.append([s["id"] for s in data["services"] if s["availability"] == "renderable"])
        for selected in selections:
            with self.subTest(selected=selected):
                model = catalog.render(data, selected, "cpu", site)
                parsed = synthetic_model(json.dumps(model))
                self.assertEqual(set(model["services"]), set(parsed["services"]))
                self.assertNotIn("nvidia", json.dumps(parsed).lower())
        for name in ["ollama", "jellyfin"]:
            parsed = synthetic_model(json.dumps(catalog.render(data, [name], "gpu", site)))
            self.assertIn("nvidia", json.dumps(parsed).lower())


if __name__ == "__main__":
    unittest.main()
