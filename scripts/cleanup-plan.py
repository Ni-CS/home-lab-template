#!/usr/bin/env python3
"""Inventário de reset exclusivamente dry-run; nunca remove, move ou para serviços."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


GROUPS = ("ollama", "open-webui", "comfyui-full", "fooocus-models",
          "finance-securo", "finance-actual", "arr-media")
VOLUMES = {
    "ollama": ("homelab_ollama_data",),
    "open-webui": ("homelab_open-webui_data", "home-lab_open-webui_data", "open-webui"),
}
FINANCE = {
    "finance-securo": ("securo-frontend", "securo-backend", "securo-celery-worker",
                       "securo-celery-beat", "securo-redis", "securo-db"),
    "finance-actual": ("actual-budget",),
}
FINANCE_BINDS = {
    "finance-securo": {
        "postgres": "/var/lib/postgresql/data", "secrets": "/app/secrets",
        "attachments": "/app/data/attachments", "agent_knowledge": "/app/data/agent_knowledge",
        "agent_embedding_models": "/app/data/embedding_models",
    },
    "finance-actual": {".": "/data"},
}
AUDIO = frozenset(".mp3 .flac .m4a .aac .ogg .opus .wav .aiff .aif .alac .wma .ape .dsf .dff .mka .mp2 .ac3 .dts .amr .mid .midi .aifc .oga".split())
VIDEO = frozenset(".mkv .mp4 .avi .mov .m4v .webm .mpeg .mpg .ts .m2ts .vob .wmv".split())
KNOWN_EXTENSIONS = AUDIO | VIDEO | frozenset(".srt .ass .nfo .jpg .png .zip .rar .7z .part .torrent .safetensors .ckpt .bin .json .gguf .pt .pth".split())
LOCAL_TARGETS = {}


class Blocked(Exception):
    """Messages contain fixed reasons only, never OS error strings or paths."""


def canonical(path, *, directory=True):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise Blocked("path_relativo_ou_parent")
    if path in (Path("/"), Path.home(), Path("/home"), Path("/mnt"), Path("/var")):
        raise Blocked("raiz_proibida")
    for component in [*reversed(path.parents), path]:
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise Blocked("symlink_no_path")
    if directory and not path.is_dir():
        raise Blocked("diretorio_ausente")
    return path.resolve(strict=True)


def mount_table():
    # Kernel mount metadata only. Decode escapes without opening referenced files.
    mounts = {}
    with open("/proc/self/mountinfo") as stream:
        for line in stream:
            fields = line.split()
            separator = fields.index("-")
            target = fields[4]
            for source, replacement in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
                target = target.replace(source, replacement)
            mounts[Path(target)] = fields[separator + 1]
    return mounts


def scan(path, mounts, *, exact_mount=False):
    """lstat/fwalk only. File contents, hashes and filenames never enter output."""
    path = canonical(path)
    containing = [m for m in mounts if path == m or m in path.parents]
    if not containing or (exact_mount and path not in mounts):
        raise Blocked("mount_nao_comprovado")
    fs = mounts[max(containing, key=lambda m: len(m.parts))]
    if fs not in ("ext4", "xfs", "btrfs", "zfs"):
        raise Blocked("filesystem_nao_suportado")
    if any(path in m.parents for m in mounts):
        raise Blocked("mount_interno")
    device = path.stat().st_dev
    entries = {}
    extensions = Counter()
    audio = Counter()
    latest = None
    files = 0
    symlinks = 0
    unknown = 0

    def failed(_error):
        raise Blocked("metadados_ilegíveis")

    for _base, directories, names, fd in os.fwalk(path, follow_symlinks=False, onerror=failed):
        # fwalk does not follow symlink directories; count them explicitly.
        for name in [".", *directories, *names]:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if info.st_dev != device:
                raise Blocked("cross_device")
            if stat.S_ISLNK(info.st_mode):
                symlinks += 1
                continue
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise Blocked("arquivo_especial")
            entries[(info.st_dev, info.st_ino)] = (info.st_blocks * 512, info.st_nlink if stat.S_ISREG(info.st_mode) else 1)
            if name not in names:
                continue
            files += 1
            latest = max(latest or 0, info.st_mtime_ns)
            ext = Path(name).suffix.lower()
            alias = ext if ext in KNOWN_EXTENSIONS else "other"
            extensions[alias] += 1
            if ext in AUDIO:
                audio["files"] += 1
                audio["logical_bytes"] += info.st_size
                audio["allocated_bytes_per_entry"] += info.st_blocks * 512
            elif ext not in VIDEO:
                unknown += 1
    result = {
        "canonical_verified": True, "filesystem": fs, "files": files,
        "allocated_unique_bytes": sum(v[0] for v in entries.values()),
        "inode_count": len(entries), "multiply_linked_inodes": sum(v[1] > 1 for v in entries.values()),
        "extensions": dict(extensions), "audio": dict(audio),
        "unclassified_entries": unknown, "symlinks": symlinks,
        "latest_file_mtime_ns": latest,
        "activity": "DESCONHECIDO: mtime não prova ausência de escritores",
    }
    return result, entries


def query(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise Blocked("docker_consulta_indisponivel") from None
    if result.returncode:
        raise Blocked("docker_consulta_negada_ou_falhou")
    return result.stdout


def docker_inventory():
    # Same context precedence as Docker. Refuse remote daemons before inventory.
    context = os.environ.get("DOCKER_CONTEXT")
    endpoint = os.environ.get("DOCKER_HOST") if not context else None
    if not endpoint:
        endpoint = query(["docker", "context", "inspect", *([context] if context else []),
                          "--format", "{{.Endpoints.docker.Host}}"] ).strip()
    if not endpoint.startswith("unix://"):
        raise Blocked("daemon_remoto")
    # Explicit --host freezes every query without changing saved context.
    docker = ["docker", "--host", endpoint]
    identifiers = query(docker + ["ps", "--all", "--quiet", "--no-trunc"]).split()
    if len(identifiers) > 5000:
        raise Blocked("inventario_excessivo")
    template = ('{"name":{{json .Name}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
                '"state":{{json .State.Status}},"running":{{json .State.Running}},'
                '"finished":{{json .State.FinishedAt}},"image":{{json .Image}},"volumes":['
                '{{range .Mounts}}{{if eq .Type "volume"}}{{json .Name}},{{end}}{{end}}null],"binds":['
                '{{range .Mounts}}{{if eq .Type "bind"}}{"source":{{json .Source}},'
                '"target":{{json .Destination}}},{{end}}{{end}}null]}')
    containers = []
    for identifier in identifiers:
        data = json.loads(query(docker + ["inspect", "--type", "container", "--format", template, identifier]))
        if not isinstance(data, dict) or not isinstance(data.get("volumes"), list):
            raise Blocked("docker_metadados_invalidos")
        data["volumes"] = [v for v in data["volumes"] if isinstance(v, str)]
        data["binds"] = [v for v in data.get("binds", []) if isinstance(v, dict)]
        containers.append(data)
    names = set(query(docker + ["volume", "ls", "--format", "{{.Name}}"]).splitlines())
    return docker, containers, names


def docker_group(group, inventory, mounts):
    docker, containers, available = inventory
    selected = [c for c in containers if c["name"].lstrip("/") == group and c["service"] == group]
    if not selected and not any(c["name"].lstrip("/") == group for c in containers) and not set(VOLUMES[group]) & available:
        return {"group": group, "state": "ausente", "containers": 0, "volumes": [],
                "images": "não inferidas pela ausência de containers",
                "planned_operations": ["nenhuma remoção de container/volume a repetir"],
                "blockers": ["imagens_sem_consumidor_nao_inventariadas"]}
    blockers = []
    if len(selected) != 1:
        blockers.append("associacao_container_servico_nao_univoca")
    if any(c["running"] or c["state"] != "exited" for c in selected):
        blockers.append("container_ativo_ou_estado_nao_seguro")
    target = selected[0] if len(selected) == 1 else None
    if target and set(target["volumes"]) - set(VOLUMES[group]):
        blockers.append("volume_fora_allowlist")
    volumes = []
    for i, name in enumerate(VOLUMES[group], 1):
        item = {"alias": f"{group}-volume-{i}", "present": name in available}
        if name in available:
            consumers = [c for c in containers if name in c["volumes"]]
            exclusive = bool(target) and len(consumers) == 1 and consumers[0] is target
            item.update(consumers=len(consumers), exclusive_association=exclusive)
            if not exclusive:
                blockers.append("volume_sem_prova_exclusiva_inclusive_orfao")
            template = ('{"driver":{{json .Driver}},"mountpoint":{{json .Mountpoint}},'
                        '"options":{{if .Options}}true{{else}}false{{end}}}')
            metadata = json.loads(query(docker + ["volume", "inspect", "--format", template, name]))
            if metadata.get("driver") != "local" or metadata.get("options"):
                raise Blocked("volume_driver_ou_options_nao_suportados")
            try:
                item["storage"], _entries = scan(metadata["mountpoint"], mounts)
                LOCAL_TARGETS[item["alias"]] = canonical(metadata["mountpoint"])
            except (OSError, Blocked):
                item["storage"] = {"status": "DESCONHECIDO"}
                blockers.append("volume_nao_mensuravel")
        volumes.append(item)
    images = []
    if target:
        consumers = [c for c in containers if c["image"] == target["image"]]
        size = json.loads(query(docker + ["image", "inspect", "--format", "{{json .Size}}", target["image"]]))
        if not isinstance(size, int) or size < 0:
            raise Blocked("imagem_tamanho_invalido")
        images.append({"alias": group + "-image", "referenced_by_containers": len(consumers),
                       "virtual_size_bytes": size, "reclaimable_bytes": None})
        if len(consumers) != 1:
            blockers.append("imagem_compartilhada")
    blockers.extend(["atividade_de_processos_e_dependentes_exige_revisao_local",
                     "camadas_compartilhadas_e_bytes_recuperaveis_desconhecidos"])
    return {"group": group, "containers": len(selected),
            "state": target["state"] if target and target["state"] in {"exited", "running", "restarting", "created", "paused", "dead", "removing"} else "DESCONHECIDO",
            "last_container_activity": target["finished"] if target else None,
            "volumes": volumes, "images": images, "blockers": sorted(set(blockers)),
            "planned_operations": ["revalidar associações e aprovação local",
                                   "remover apenas alvos individualmente aprovados em janela futura",
                                   "preservar definições Compose para reinstalação"]}


def overlaps(first, second):
    return first == second or first in second.parents or second in first.parents


def finance_group(group, args, inventory, mounts):
    _docker, containers, _available = inventory
    names = set(FINANCE[group])
    selected = [c for c in containers if c["name"].lstrip("/") in names and c["service"] == c["name"].lstrip("/")]
    blockers = ["retencao_backup_revogacao_externa_e_aprovacao_local_pendentes"]
    if len(selected) != len(names):
        blockers.append("inventario_financeiro_parcial_ou_ja_removido")
    if any(c["running"] or c["state"] != "exited" for c in selected):
        blockers.append("containers_ativos_parar_somente_em_operacao_futura_aprovada")
    project = canonical(args.project_directory)
    root = canonical(project / "configs" / ("securo" if group == "finance-securo" else "actual-budget"))
    expected = {canonical(root / suffix): target for suffix, target in FINANCE_BINDS[group].items()}
    matched = set()
    for container in containers:
        if container in selected and container["volumes"]:
            blockers.append("volume_extra_nao_classificado")
        for bind in container["binds"]:
            if container in selected:
                source = canonical(bind["source"], directory=False)
                service = container["service"]
                allowed = (set(expected) if group == "finance-actual" else
                           {root / "postgres"} if service == "securo-db" else
                           set(expected) - {root / "postgres"} if service in
                           {"securo-backend", "securo-celery-worker", "securo-celery-beat"} else set())
                if source not in allowed or bind["target"] != expected.get(source):
                    blockers.append("bind_financeiro_incorreto_ou_fora_allowlist")
                else:
                    matched.add(source)
            else:
                # Other consumers may use a symlink alias or host-root mount.
                # Resolve metadata only for association; never add these to targets.
                try:
                    source = Path(bind["source"])
                    if not source.is_absolute():
                        raise ValueError()
                    source = source.resolve(strict=True)
                except (OSError, ValueError, RuntimeError):
                    blockers.append("bind_de_consumidor_preservado_nao_verificado")
                    continue
                if overlaps(root, source):
                    blockers.append("bind_compartilhado_com_servico_preservado")
    if matched != set(expected):
        blockers.append("binds_declarados_nao_comprovados_no_runtime")
    # A shared image is retained, including Redis used by Docmost.
    images = []
    for i, image in enumerate(sorted({c["image"] for c in selected}), 1):
        consumers = [c for c in containers if c["image"] == image]
        exclusive = all(c in selected for c in consumers)
        images.append({"alias": group + f"-image-{i}", "consumers": len(consumers),
                       "exclusive": exclusive, "planned_disposition": "revisar" if exclusive else "preservar"})
    data, _entries = scan(root, mounts)
    LOCAL_TARGETS[group + "-bind"] = root
    return {"group": group, "containers": len(selected), "targets": [{"alias": group + "-bind", **data}],
            "images": images, "blockers": sorted(set(blockers)), "reclaimable_bytes": None,
            "planned_operations": ["decidir retenção; export privado mínimo se desejado",
                                   "desabilitar apenas agendas/consumidores financeiros após aprovação",
                                   "remover apenas alvos financeiros comprovados em operação futura",
                                   "revisar entradas financeiras de .env manualmente, sem leitura pelo agente",
                                   "preservar todos os demais bancos, Redis compartilhado e rede"]}


def filesystem_group(group, args, mounts):
    blockers = []
    targets = []
    union = {}
    seen_targets = Counter()
    if group == "comfyui-full":
        root = canonical(args.comfy_root or Path.home() / "AI" / "ComfyUI")
        # Metadata markers prevent accidentally treating an arbitrary model tree as ComfyUI.
        if not (root / "main.py").is_file() or not (root / "custom_nodes").is_dir():
            raise Blocked("raiz_comfyui_nao_comprovada")
        if root.name != "ComfyUI":
            raise Blocked("nome_raiz_comfyui_incorreto")
        selections = [("comfyui-full", root), ("comfyui-env", root.parent / "comfy-env")]
    elif group == "fooocus-models":
        if not args.data_root:
            raise Blocked("data_root_obrigatorio")
        root = canonical(args.data_root)
        if root not in mounts:
            raise Blocked("data_root_nao_e_mount")
        selections = [("fooocus-models", root / "fooocus" / "models")]
        blockers.append("bind_fooocus_e_referencias_externas_exigem_comprovacao_local")
    else:
        if not args.data_root:
            raise Blocked("data_root_obrigatorio")
        root = canonical(args.data_root)
        if root not in mounts:
            raise Blocked("data_root_nao_e_mount")
        selections = [("arr-" + name, root / "media" / name)
                      for name in ("downloads", "filmes", "series")]
        # incoming only; never reorganize or recursively inventory the live library.
        selections.append(("music-incoming-preserve", root / "media" / "musicas" / "incoming"))
    device = root.stat().st_dev
    for alias, path in selections:
        try:
            if canonical(path).stat().st_dev != device:
                raise Blocked("cross_device")
            if any((m == path and path != root) or (m in path.parents and root in m.parents) for m in mounts):
                raise Blocked("mount_interno")
            data, entries = scan(path, mounts)
        except (OSError, Blocked):
            targets.append({"alias": alias, "status": "DESCONHECIDO", "allocated_unique_bytes": None})
            blockers.append("alvo_ausente_ou_metadados_mount_nao_verificados")
            continue
        targets.append({"alias": alias, **data})
        LOCAL_TARGETS[alias] = canonical(path)
        if alias != "music-incoming-preserve":
            union.update(entries)
            seen_targets.update(key for key, value in entries.items() if value[1] > 1)
        if data["symlinks"]:
            blockers.append("symlinks_na_arvore")
        if group == "arr-media" and alias != "music-incoming-preserve":
            if data["audio"]:
                blockers.append("audio_exige_resgate_seletivo")
            if data["unclassified_entries"]:
                blockers.append("arquivos_nao_classificados")
    blockers.append("processos_jobs_seedings_e_handles_abertos_nao_comprovados")
    if group == "arr-media":
        blockers.extend(["conteudo_pessoal_nao_excluido_por_extensao",
                         "consumidores_lidarr_qbittorrent_prowlarr_exigem_mapa_local"])
    return {"group": group, "targets": targets,
            "observed_union_allocated_unique_bytes": sum(v[0] for v in union.values()) if union else None,
            "shared_inodes_between_targets": sum(count > 1 for count in seen_targets.values()),
            "reclaimable_bytes": None, "blockers": sorted(set(blockers)),
            "planned_operations": (["classificar áudio/pessoais em TODOS os alvos",
                                    "planejar cópia seletiva sem overwrite para incoming",
                                    "verificar integridade e hardlinks antes de qualquer remoção",
                                    "exportar Arr de filmes/séries; preservar consumidores de música"]
                                   if group == "arr-media" else
                                   ["revalidar processos, dependências e aprovação por alvo",
                                    ("descartar instalação ComfyUI e ambiente dedicado em etapa humana futura"
                                     if group == "comfyui-full" else "descartar somente modelos Fooocus; preservar outputs/aplicativo")])}


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "Argumentos inválidos; use --help. Nenhum alvo alterado.\n")


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument("--group", action="append", choices=GROUPS)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--comfy-root", type=Path)
    parser.add_argument("--project-directory", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--apply", action="store_true", help="sempre recusado; não existe executor")
    parser.add_argument("--local-manifest", action="store_true",
                        help="inclui paths/UUID privados somente em terminal local; nunca publicar")
    args = parser.parse_args()
    if args.apply:
        print(json.dumps({"mode": "refused", "reason": "executor_destrutivo_nao_implementado"}))
        return 2
    if args.local_manifest and not sys.stdout.isatty():
        print(json.dumps({"mode": "refused", "reason": "manifesto_privado_exige_terminal_local"}))
        return 2
    LOCAL_TARGETS.clear()
    groups = list(dict.fromkeys(args.group or GROUPS))
    result = {"mode": "dry-run-only", "execution_authorized": False,
              "private_paths_emitted": False, "groups": []}
    inventory = None
    docker_error = None
    try:
        mounts = mount_table()
    except (OSError, ValueError):
        mounts = {}
    for group in groups:
        try:
            if group in VOLUMES or group in FINANCE:
                if inventory is None and docker_error is None:
                    try:
                        inventory = docker_inventory()
                    except (Blocked, OSError, ValueError, TypeError, KeyError):
                        docker_error = "docker_inventario_incompleto"
                if docker_error:
                    raise Blocked(docker_error)
                item = (docker_group(group, inventory, mounts) if group in VOLUMES else
                        finance_group(group, args, inventory, mounts))
            else:
                item = filesystem_group(group, args, mounts)
            result["groups"].append(item)
        except (Blocked, OSError, ValueError, TypeError, KeyError, RuntimeError):
            error = sys.exc_info()[1]
            result["groups"].append({"group": group, "status": "BLOQUEADO",
                                     "reason": str(error) if isinstance(error, Blocked) else "metadados_inacessiveis_ou_invalidos",
                                     "reclaimable_bytes": None})
    if args.local_manifest:
        private = []
        for alias, path in LOCAL_TARGETS.items():
            uuid = None
            try:
                value = subprocess.run(["findmnt", "--noheadings", "--output", "UUID", "--target", str(path)],
                                       capture_output=True, text=True, timeout=10)
                if value.returncode == 0 and re.fullmatch(r"[a-zA-Z0-9-]+", value.stdout.strip()):
                    uuid = value.stdout.strip()
            except (OSError, subprocess.SubprocessError):
                pass
            private.append({"alias": alias, "canonical_path": str(path), "filesystem_uuid": uuid})
        result["private_local_manifest_do_not_publish"] = private
        result["private_paths_emitted"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Exit 2 is expected: no inventory can authorize this tool to delete.
    return 2


if __name__ == "__main__":
    sys.exit(main())
