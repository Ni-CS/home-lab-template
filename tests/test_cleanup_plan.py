"""Metadata-only planner tests. All files are synthetic; Docker is mocked."""

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/cleanup-plan.py"
spec = importlib.util.spec_from_file_location("cleanup_plan", SCRIPT)
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="homelab-reset-test-")
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        for suffix in ["media/downloads", "media/filmes", "media/series", "media/musicas/incoming",
                       "fooocus/models", "fooocus/outputs"]:
            (self.data / suffix).mkdir(parents=True)
        self.comfy = self.root / "AI/ComfyUI"
        (self.comfy / "custom_nodes").mkdir(parents=True)
        (self.comfy / "models").mkdir()
        (self.comfy / "main.py").write_text("# synthetic\n")
        (self.comfy / "user").mkdir()
        (self.comfy.parent / "comfy-env").mkdir()
        self.args = argparse.Namespace(data_root=self.data, comfy_root=self.comfy,
                                       project_directory=self.root)
        self.mounts = {Path("/"): "ext4", self.data: "ext4"}

    def tearDown(self):
        self.temp.cleanup()

    def group(self, group):
        return plan.filesystem_group(group, self.args, self.mounts)

    def container(self, name, image="image-fixture", binds=(), volumes=(), running=False):
        return {"name": "/" + name, "service": name, "image": image,
                "binds": list(binds), "volumes": list(volumes), "running": running,
                "state": "running" if running else "exited", "finished": "fixture-time"}

    def finances(self, group):
        root = self.root / "configs" / ("securo" if group == "finance-securo" else "actual-budget")
        binds = []
        for suffix, target in plan.FINANCE_BINDS[group].items():
            source = root / suffix
            source.mkdir(parents=True, exist_ok=True)
            binds.append({"source": str(source), "target": target})
        containers = [self.container(name, image="redis" if name == "securo-redis" else name)
                      for name in plan.FINANCE[group]]
        if group == "finance-actual":
            containers[0]["binds"] = binds
        else:
            for container in containers:
                if container["service"] == "securo-db":
                    container["binds"] = binds[:1]
                elif container["service"] in {"securo-backend", "securo-celery-worker", "securo-celery-beat"}:
                    container["binds"] = binds[1:]
        return containers

    def test_relative_root_parent_missing_and_symlink_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.data, target_is_directory=True)
        for path in [Path("relative"), Path("/"), self.root / "../escape", link,
                     link / "media", self.root / "missing", Path.home()]:
            with self.subTest(path=path), self.assertRaises((plan.Blocked, OSError)):
                plan.canonical(path)

    def test_unreadable_metadata_refuses(self):
        with patch.object(plan.os, "fwalk", side_effect=PermissionError("private-path")):
            with self.assertRaises(PermissionError):
                plan.scan(self.data, self.mounts)

    def test_mount_absent_and_nested_mount_block(self):
        with self.assertRaises(plan.Blocked):
            plan.scan(self.data, {Path("/"): "ext4"}, exact_mount=True)
        nested = dict(self.mounts, **{})
        nested[self.data / "media/downloads"] = "ext4"
        with self.assertRaises(plan.Blocked):
            plan.scan(self.data, nested)
        self.mounts = nested
        result = self.group("arr-media")
        self.assertIn("alvo_ausente_ou_metadados_mount_nao_verificados", result["blockers"])

    def test_cross_device_blocks(self):
        real = plan.os.stat
        def different(name, *args, **kwargs):
            info = real(name, *args, **kwargs)
            if name == "." and kwargs.get("dir_fd") is not None:
                values = list(info)
                values[2] += 100
                return os.stat_result(values)
            return info
        with patch.object(plan.os, "stat", side_effect=different):
            with self.assertRaises(plan.Blocked):
                plan.scan(self.data, self.mounts)

    def test_audio_anywhere_unknown_files_and_no_private_names(self):
        secret = self.data / "media/downloads/unexpected-private-track.flac"
        secret.write_bytes(b"synthetic audio")
        (secret.parent / "personal-private-document.xyz").write_bytes(b"synthetic")
        result = self.group("arr-media")
        self.assertEqual(result["targets"][0]["audio"]["files"], 1)
        self.assertIn("audio_exige_resgate_seletivo", result["blockers"])
        self.assertIn("arquivos_nao_classificados", result["blockers"])
        serialized = json.dumps(result)
        self.assertNotIn("private-track", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertIn("other", result["targets"][0]["extensions"])
        self.assertIn("processos_jobs_seedings_e_handles_abertos_nao_comprovados", result["blockers"])

    def test_hardlinks_union_counted_once_and_gain_unknown(self):
        original = self.data / "media/downloads/item.mkv"
        original.write_bytes(b"synthetic" * 1000)
        os.link(original, self.data / "media/filmes/item.mkv")
        result = self.group("arr-media")
        self.assertEqual(result["shared_inodes_between_targets"], 1)
        summed = sum(t["allocated_unique_bytes"] for t in result["targets"][:3])
        self.assertLess(result["observed_union_allocated_unique_bytes"], summed)
        self.assertIsNone(result["reclaimable_bytes"])

    def test_music_migration_protocol_copy_integrity_and_independent_inode(self):
        # A rehearsal only: these files were just created inside TemporaryDirectory.
        source = self.data / "media/downloads/song.flac"
        source.write_bytes(b"synthetic-fixture-audio")
        os.link(source, self.data / "media/filmes/shared.flac")
        target = self.data / "media/musicas/incoming/rescued.flac"
        with target.open("xb") as dest, source.open("rb") as src:
            shutil.copyfileobj(src, dest)
        digest = lambda p: hashlib.sha256(p.read_bytes()).digest()
        self.assertEqual(digest(source), digest(target))
        self.assertNotEqual(source.stat().st_ino, target.stat().st_ino)
        with self.assertRaises(FileExistsError):
            target.open("xb")
        self.assertTrue(source.exists())
        self.assertEqual(source.stat().st_nlink, 2)

    def test_comfy_full_includes_authorized_workflow_and_env(self):
        (self.comfy / "user/private-workflow.json").write_text("{}")
        result = self.group("comfyui-full")
        self.assertEqual([t["alias"] for t in result["targets"]], ["comfyui-full", "comfyui-env"])
        self.assertEqual(result["targets"][0]["files"], 2)
        self.assertTrue(result["blockers"])  # no proof that the env is dedicated/inactive

    def test_fooocus_outputs_excluded_and_bind_unverified(self):
        (self.data / "fooocus/outputs/private.png").write_bytes(b"keep")
        (self.data / "fooocus/models/model.bin").write_bytes(b"model")
        result = self.group("fooocus-models")
        self.assertEqual(result["targets"][0]["files"], 1)
        self.assertIn("bind_fooocus_e_referencias_externas_exigem_comprovacao_local", result["blockers"])
        self.assertTrue((self.data / "fooocus/outputs/private.png").exists())

    def test_symlink_entries_never_followed(self):
        (self.data / "media/downloads/link").symlink_to(self.comfy, target_is_directory=True)
        result = self.group("arr-media")
        self.assertIn("symlinks_na_arvore", result["blockers"])
        self.assertEqual(result["targets"][0]["files"], 0)

    def test_special_file_is_never_opened(self):
        os.mkfifo(self.data / "media/downloads/synthetic-pipe")
        with self.assertRaises(plan.Blocked):
            plan.scan(self.data, self.mounts)

    def test_all_groups_public_output_has_no_private_paths_or_file_contents(self):
        stream = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), "--data-root", str(self.data),
                                       "--comfy-root", str(self.comfy)]), \
                patch.object(plan, "docker_inventory", side_effect=plan.Blocked("daemon_negado")), \
                patch.object(plan, "mount_table", return_value=self.mounts), \
                contextlib.redirect_stdout(stream):
            self.assertEqual(plan.main(), 2)
        result = json.loads(stream.getvalue())
        self.assertEqual(len(result["groups"]), 7)
        self.assertFalse(result["private_paths_emitted"])
        self.assertNotIn(str(self.root), stream.getvalue())

    def test_missing_incoming_is_unknown_never_created(self):
        path = self.data / "media/musicas/incoming"
        path.rmdir()  # empty synthetic fixture only
        result = self.group("arr-media")
        self.assertEqual(result["targets"][-1]["status"], "DESCONHECIDO")
        self.assertFalse(path.exists())

    def test_scanner_never_reads_document_contents(self):
        (self.data / "media/downloads/private.txt").write_text("not-for-public-output")
        with patch("builtins.open", side_effect=AssertionError("content read forbidden")):
            result, _entries = plan.scan(self.data, self.mounts)
        self.assertEqual(result["files"], 1)
        self.assertNotIn("not-for-public-output", json.dumps(result))

    def test_private_manifest_cannot_be_redirected_to_repository(self):
        stream = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), "--local-manifest"]), \
                patch.object(plan, "docker_inventory") as docker, \
                contextlib.redirect_stdout(stream):
            self.assertEqual(plan.main(), 2)
            docker.assert_not_called()
        self.assertEqual(json.loads(stream.getvalue())["reason"], "manifesto_privado_exige_terminal_local")

    def test_finance_securo_never_selects_other_databases_and_shared_redis_retained(self):
        containers = self.finances("finance-securo")
        containers.extend([self.container("immich-postgres"), self.container("romm-db"),
                           self.container("docmost-db"), self.container("docmost-redis", image="redis")])
        result = plan.finance_group("finance-securo", self.args, ([], containers, set()), self.mounts)
        self.assertEqual(result["containers"], 6)
        self.assertTrue(any(i["planned_disposition"] == "preservar" for i in result["images"]))
        self.assertNotIn("immich-postgres", json.dumps(result))
        self.assertNotIn("binds_declarados_nao_comprovados_no_runtime", result["blockers"])

    def test_finance_wrong_bind_shared_bind_and_active_container_block(self):
        containers = self.finances("finance-actual")
        containers[0]["running"] = True
        containers[0]["binds"][0]["target"] = "/incorrect"
        containers.append(self.container("preserved-app", binds=containers[0]["binds"]))
        result = plan.finance_group("finance-actual", self.args, ([], containers, set()), self.mounts)
        self.assertIn("bind_financeiro_incorreto_ou_fora_allowlist", result["blockers"])
        self.assertIn("bind_compartilhado_com_servico_preservado", result["blockers"])
        self.assertIn("containers_ativos_parar_somente_em_operacao_futura_aprovada", result["blockers"])

    def test_ollama_already_removed_is_idempotent_without_removal_commands(self):
        result = plan.docker_group("ollama", ([], [], set()), self.mounts)
        self.assertEqual(result["state"], "ausente")
        self.assertEqual(result["containers"], 0)

    def test_preserved_host_root_and_symlink_bind_are_reported_never_added_to_targets(self):
        containers = self.finances("finance-actual")
        alias = self.root / "consumer-alias"
        alias.symlink_to(self.root / "configs/actual-budget", target_is_directory=True)
        containers.extend([self.container("host-monitor", binds=[{"source": "/", "target": "/rootfs"}]),
                           self.container("other", binds=[{"source": str(alias), "target": "/shared"}])])
        result = plan.finance_group("finance-actual", self.args, ([], containers, set()), self.mounts)
        self.assertIn("bind_compartilhado_com_servico_preservado", result["blockers"])
        self.assertEqual([t["alias"] for t in result["targets"]], ["finance-actual-bind"])

    def test_in_use_volume_orphan_and_active_process_are_blocked(self):
        volume = self.root / "volume"
        volume.mkdir()
        containers = [self.container("open-webui", volumes=["homelab_open-webui_data"], running=True),
                      self.container("preserved-app", volumes=["homelab_open-webui_data"])]
        def query(args):
            if "volume" in args:
                return json.dumps({"driver": "local", "options": False, "mountpoint": str(volume)})
            return "1234"
        with patch.object(plan, "query", side_effect=query):
            result = plan.docker_group("open-webui", ([], containers, set(plan.VOLUMES["open-webui"])), self.mounts)
        self.assertIn("volume_sem_prova_exclusiva_inclusive_orfao", result["blockers"])
        self.assertIn("container_ativo_ou_estado_nao_seguro", result["blockers"])

    def test_apply_refused_before_any_inventory_even_if_confirmation_supplied(self):
        with patch.object(sys, "argv", [str(SCRIPT), "--apply"]), \
                patch.object(plan, "mount_table") as mounts, \
                patch.object(plan, "docker_inventory") as docker, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(plan.main(), 2)
            mounts.assert_not_called()
            docker.assert_not_called()

    def test_missing_authorization_and_daemon_error_never_become_empty_success(self):
        stream = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), "--group", "finance-securo"]), \
                patch.object(plan, "docker_inventory", side_effect=PermissionError("private-secret")), \
                contextlib.redirect_stdout(stream):
            self.assertEqual(plan.main(), 2)
        data = json.loads(stream.getvalue())
        self.assertFalse(data["execution_authorized"])
        self.assertEqual(data["groups"][0]["status"], "BLOQUEADO")
        self.assertNotIn("private-secret", stream.getvalue())

    def test_no_generic_destructive_executor_or_financial_name_wildcard(self):
        self.assertEqual(plan.FINANCE["finance-actual"], ("actual-budget",))
        self.assertNotIn("immich-postgres", plan.FINANCE["finance-securo"])
        # Parse the implementation, not documentation, for forbidden mutation APIs.
        import ast
        tree = ast.parse(SCRIPT.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, {"unlink", "rmdir", "rmtree", "rename", "write_text", "write_bytes"})


if __name__ == "__main__":
    unittest.main()
