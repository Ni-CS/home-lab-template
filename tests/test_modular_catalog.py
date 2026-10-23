"""Catalog, selection, portable rendering and metadata doctor tests."""

import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from homelab_lib import catalog, host
from homelab_lib.cli import main
from homelab_lib.source import ROOT, Refused, digest


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.data = catalog.load()
        self.site = catalog.site_config(ROOT / "templates/modular/site.example.json")

    def service(self, name):
        return next(s for s in self.data["services"] if s["id"] == name)

    def seal(self):
        self.data["source_shape_sha256"] = digest({s["id"]: s["observed"] for s in self.data["services"]})

    def test_catalog_44_exact_ids_and_11_renderable(self):
        self.assertEqual(len(self.data["services"]), 44)
        self.assertEqual(sum(s["availability"] == "renderable" for s in self.data["services"]), 11)
        self.assertEqual(len(catalog.validate(self.data)), 44)

    def test_default_minimum_no_finance_admin_ai(self):
        result = catalog.plan(self.data, [], "cpu")
        self.assertEqual(set(result["services"]), {"adguard", "npm", "homepage", "uptime-kuma"})
        self.assertFalse(result["execution_authorized"])

    def test_dependency_order_and_profiles_do_not_add_other_optional_services(self):
        order = catalog.resolve(self.data, ["open-webui"], "cpu")
        self.assertLess(order.index("ollama"), order.index("open-webui"))
        self.assertNotIn("fooocus", order)
        model = catalog.render(self.data, ["open-webui"], "cpu", self.site)
        self.assertEqual(model["services"]["open-webui"]["profiles"], ["ai"])
        self.assertNotIn("profiles", model["services"]["homepage"])
        self.assertEqual(model["services"]["open-webui"]["restart"], "no")

    def test_shared_music_integrations_do_not_require_arr_tv(self):
        order = catalog.resolve(self.data, ["qbittorrent", "prowlarr"], "cpu")
        self.assertNotIn("sonarr", order)
        self.assertNotIn("radarr", order)
        order = catalog.resolve(self.data, ["lidarr"], "cpu")
        self.assertNotIn("qbittorrent", order)  # integration is explicit, not an artificial dependency
        self.assertEqual(self.service("lidarr")["integrations"], ["qbittorrent", "prowlarr"])

    def test_unknown_and_planned_selection_refused(self):
        for name in ["unknown", "latex-overleaf", "comfyui", "--remove-orphans"]:
            with self.assertRaises(Refused):
                catalog.resolve(self.data, [name])

    def test_gpu_required_refuses_cpu_and_gpu_plan_is_not_detection(self):
        with self.assertRaises(Refused):
            catalog.plan(self.data, ["fooocus"], "cpu")
        result = catalog.plan(self.data, ["fooocus"], "gpu")
        self.assertFalse(result["hardware_detected"])
        self.assertIn("fooocus", result["inventory_only"])

    def test_all_renderable_cpu_models_have_no_gpu_and_preserve_persistence(self):
        selection = [s["id"] for s in self.data["services"] if s["availability"] == "renderable"]
        model = catalog.render(self.data, selection, "cpu", self.site)
        self.assertNotRegex(json.dumps(model).lower(), r'nvidia|cuda|"gpus"')
        self.assertIn("/srv/homelab/state/ollama:/root/.ollama", model["services"]["ollama"]["volumes"])
        self.assertNotIn("docker.sock", json.dumps(model))
        self.assertNotIn("/mnt/", json.dumps(model))

    def test_gpu_variants_have_real_nvidia_reservations_same_paths(self):
        cpu = catalog.render(self.data, ["ollama", "jellyfin"], "cpu", self.site)
        gpu = catalog.render(self.data, ["ollama", "jellyfin"], "gpu", self.site)
        for name in ["ollama", "jellyfin"]:
            self.assertEqual(cpu["services"][name]["volumes"], gpu["services"][name]["volumes"])
            reservation = gpu["services"][name]["deploy"]["resources"]["reservations"]["devices"][0]
            self.assertEqual(reservation["driver"], "nvidia")
            self.assertEqual(reservation["capabilities"], ["gpu"])

    def test_inventory_only_finance_and_unsupported_modules_never_render_silently(self):
        for name in ["actual-budget", "securo-frontend", "immich-server", "olivetin", "latex-overleaf"]:
            with self.assertRaises(Refused):
                catalog.render(self.data, [name], "cpu", self.site)

    def test_duplicate_id_unknown_dependency_cycle_and_port_conflict(self):
        self.data["services"].append(copy.deepcopy(self.data["services"][0]))
        with self.assertRaises(Refused):catalog.validate(self.data)
        self.data = catalog.load()
        self.service("homepage")["dependencies"] = ["absent"]
        with self.assertRaises(Refused):catalog.validate(self.data)
        self.data = catalog.load()
        self.service("ollama")["dependencies"] = ["open-webui"]
        with self.assertRaisesRegex(Refused, "ciclo"):
            catalog.resolve(self.data, ["open-webui"])
        self.data = catalog.load()
        self.service("navidrome")["observed"]["ports"][0]["published"] = 3001
        with self.assertRaisesRegex(Refused, "conflito"):
            catalog.resolve(self.data, ["navidrome"])

    def test_fingerprint_and_unauthorized_default_change_refused(self):
        self.service("homepage")["observed"]["restart"] = "no"
        with self.assertRaisesRegex(Refused, "fingerprint"):catalog.validate(self.data)
        self.data = catalog.load()
        self.service("olivetin")["execution"] = "always-on"
        with self.assertRaises(Refused):catalog.validate(self.data)

    def test_invalid_schema_template_escape_and_hardware_contract(self):
        self.service("ollama")["template"] = "../../private.json"
        with self.assertRaises(Refused):catalog.validate(self.data)
        self.data = catalog.load()
        self.service("ollama")["hardware"]["variants"] = ["cpu"]
        with self.assertRaises(Refused):catalog.validate(self.data)
        self.data = catalog.load()
        self.data["unexpected"] = "private"
        with self.assertRaises(Refused):catalog.validate(self.data)

    def test_drift_detection_does_not_require_secret_values(self):
        expected = {s["id"]: s["observed"] for s in self.data["services"]}
        changed = copy.deepcopy(expected)
        changed["homepage"]["ports"][0]["published"] = 12345
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "docker-compose.yml").write_text("services: {}")
            with patch.object(catalog, "ROOT", Path(folder)), patch.object(catalog, "synthetic_model", return_value={}), \
                    patch.object(catalog, "shape", return_value=changed):
                result = catalog.check_local(self.data)
        self.assertEqual(result["changed_services"], ["homepage"])
        self.assertFalse(result["matches_local_compose"])

    def test_site_refuses_secrets_relative_root_overlap_and_credential_url(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "site.json"
            for updates in [{"data_dir": "relative"}, {"data_dir": "/"}, {"data_dir": "/srv/homelab/state/child"},
                            {"base_url": "http://user:private@example.invalid"}, {"bind_address": "8.8.8.8"},
                            {"SECRET_KEY": "never-read-from-env"}, {"data_dir": "/invalid/@STATE@"}]:
                value = dict(self.site, **updates)
                path.write_text(json.dumps(value))
                with self.assertRaises((Refused, ValueError)):
                    catalog.site_config(path)

    def test_duplicate_json_keys_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "site.json"
            path.write_text('{"a":1,"a":2}')
            with self.assertRaises(Refused):catalog.read_json(path)

    def test_homepage_correct_admin_ports_honest_state_and_explicit_urls(self):
        cards = catalog.homepage(self.data, ["navidrome"], "cpu", self.site)
        text = json.dumps(cards)
        self.assertIn("http://homelab.example.invalid:81/", text)
        self.assertIn("http://homelab.example.invalid:3005/", text)
        self.assertNotIn(":53/", text)
        self.assertIn("desconhecido", text)
        self.assertNotIn("server", text)  # no socket status/control configured
        self.site["urls"] = {"navidrome": "https://music.example.invalid"}
        self.assertIn("https://music.example.invalid", json.dumps(catalog.homepage(self.data, ["navidrome"], "cpu", self.site)))
        self.site["base_url"] = "http://localhost"
        with self.assertRaises(Refused):catalog.homepage(self.data, [], "cpu", self.site)

    def test_apply_refused_before_loading_catalog_or_querying_host(self):
        with patch.object(catalog, "load") as loader, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["apply"]), 2)
        loader.assert_not_called()

    def test_doctor_cpu_never_queries_nvidia_and_keeps_install_blocked(self):
        with patch.object(host, "path_check", return_value={"exists": True}), \
                patch.object(host, "listening_ports", return_value=set()), patch.object(host, "run") as command:
            result = host.check(self.data, ["ollama"], "cpu", self.site)
        command.assert_not_called()
        self.assertFalse(result["ready_for_install"])
        self.assertFalse(result["execution_authorized"])

    def test_doctor_missing_mount_busy_port_and_gpu_unknown(self):
        with patch.object(host, "path_check", side_effect=Refused("private")), \
                patch.object(host, "listening_ports", return_value={(3001, "tcp")}), \
                patch.object(host, "run", side_effect=Refused("private")):
            result = host.check(self.data, ["ollama"], "gpu", self.site)
        self.assertTrue(result["blocked"])
        self.assertFalse(result["gpu_detected"])
        self.assertEqual(result["port_conflicts"][0]["service"], "homepage")
        self.assertNotIn("private", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
