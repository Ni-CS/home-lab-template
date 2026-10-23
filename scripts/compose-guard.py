#!/usr/bin/env python3
"""Gate local Compose growth on measured storage; never clean or create paths."""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


class Refused(Exception):
    pass


POLICY = {
    "HOMELAB_MIN_FREE_GIB": "20",
    "HOMELAB_MIN_FREE_PERCENT": "10",
    "HOMELAB_MIN_FREE_INODES_PERCENT": "5",
    "HOMELAB_REQUIRED_MOUNTS": "",
    "HOMELAB_EXTRA_STORAGE_PATHS": "",
}


def command(args):
    """Do not echo commands, resolved configs, paths, secrets or raw errors."""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise Refused("consulta indisponível ou excedeu 30s") from None


def output(args, label):
    result = command(args)
    if result.returncode:
        raise Refused(f"{label}: consulta falhou; stderr privado omitido")
    return result.stdout


def as_json(text, label):
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise Refused(f"{label}: resposta inválida") from None


def policy(project, read_env=True):
    # Only literal safety settings are accepted; dotenv is never executed.
    values = dict(POLICY)
    env_file = project / ".env"
    if read_env and env_file.exists():
        try:
            with env_file.open() as stream:
                for line in stream:
                    match = re.match(r"^\s*(?:export\s+)?([A-Z_]+)\s*=(.*)$", line)
                    if match and match[1] in POLICY:
                        value = match[2].strip()
                        if value[:1] in ("'", '"'):
                            if len(value) < 2 or value[-1] != value[0]:
                                raise Refused("política: aspas inválidas")
                            value = value[1:-1]
                        else:
                            value = value.split(" #", 1)[0].rstrip()
                        values[match[1]] = value
        except (OSError, UnicodeError):
            raise Refused("política: arquivo local inacessível") from None
    for key in POLICY:
        if key in os.environ:
            values[key] = os.environ[key]
    for key in list(POLICY)[:3]:
        value = values[key]
        if not re.fullmatch(r"[0-9]{1,4}", value):
            raise Refused(f"política: {key} deve ser inteiro positivo")
        values[key] = int(value)
        maximum = 100 if "PERCENT" in key else 9999
        if not 1 <= values[key] <= maximum:
            raise Refused(f"política: {key} fora da faixa permitida")
    for key in list(POLICY)[3:]:
        values[key] = values[key].split(":") if values[key] else []
        if any(not p.startswith("/") or "$" in p or "\n" in p
               for p in values[key]):
            raise Refused(f"política: {key} exige paths absolutos literais")
    return values


def existing(path, label):
    try:
        value = Path(path)
        if not value.is_absolute():
            raise Refused(f"{label}: path não absoluto")
        return value.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        raise Refused(f"{label}: path ausente ou inacessível; nada criado") from None


class Storage:
    def __init__(self, limits):
        self.limits = limits
        self.filesystems = set()

    def mount(self, path, label, writable, exact=False):
        flag = "--mountpoint" if exact else "--target"
        data = as_json(output([
            "findmnt", "--json", flag, str(path), "--output", "TARGET,FSTYPE,OPTIONS"
        ], label + ": mount"), label)
        entries = data.get("filesystems", [])
        if len(entries) != 1 or not entries[0].get("target"):
            raise Refused(f"{label}: filesystem não identificado")
        entry = entries[0]
        if exact and Path(entry["target"]).resolve() != path:
            raise Refused(f"{label}: mount esperado ausente")
        # A network/virtual filesystem may have quotas/storage invisible here.
        if entry.get("fstype") not in {"ext4", "xfs", "btrfs", "zfs"}:
            raise Refused(f"{label}: filesystem fora do suporte local")
        if writable and "rw" not in str(entry.get("options", "")).split(","):
            raise Refused(f"{label}: filesystem não comprovado como gravável")
        return entry["target"]

    def numbers(self, path, columns, label):
        raw = output(["df", "--block-size=1", "--output=" + columns,
                      "--", str(path)], label + ": df")
        lines = raw.strip().splitlines()
        if len(lines) != 2 or not re.fullmatch(r"\s*[0-9]+\s+[0-9]+\s*", lines[1]):
            raise Refused(f"{label}: df não mensurável")
        total, available = map(int, lines[1].split())
        if total <= 0 or not 0 <= available <= total:
            raise Refused(f"{label}: contadores inválidos")
        return total, available

    def check(self, source, label, writable=True, exact=False):
        path = existing(source, label)
        info = path.stat()
        # Sockets/devices do not store application data; still require existence.
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            if stat.S_ISSOCK(info.st_mode) or stat.S_ISCHR(info.st_mode):
                return
            raise Refused(f"{label}: tipo de origem não suportado")
        mountpoint = self.mount(path, label, writable, exact)
        filesystem = (info.st_dev, mountpoint)
        if not writable or filesystem in self.filesystems:
            return
        total, available = self.numbers(path, "size,avail", label)
        inodes, free_inodes = self.numbers(path, "itotal,iavail", label)
        if (available < self.limits["HOMELAB_MIN_FREE_GIB"] * 1024 ** 3 or
                available * 100 < total * self.limits["HOMELAB_MIN_FREE_PERCENT"] or
                free_inodes * 100 < inodes * self.limits["HOMELAB_MIN_FREE_INODES_PERCENT"]):
            raise Refused(f"{label}: reserva insuficiente de bytes ou inodes")
        self.filesystems.add(filesystem)
        print(f"Capacidade {label}: {available / 1024 ** 3:.1f} GiB livres; "
              f"{available * 100 / total:.1f}% bytes; "
              f"{free_inodes * 100 / inodes:.1f}% inodes.")


def volume(storage, reference, definition):
    name = definition.get("name")
    if not name or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
        raise Refused("volume: nome local não resolvido")
    if definition.get("driver", "local") != "local" or definition.get("driver_opts"):
        raise Refused("volume: driver/opções exigem inventário específico")
    template = ('{"driver":{{json .Driver}},"mountpoint":{{json .Mountpoint}},'
                '"options":{{if .Options}}true{{else}}false{{end}}}')
    result = command(["docker", "volume", "inspect", "--format", template, name])
    if result.returncode:
        if "no such volume" in result.stderr.lower() and not definition.get("external"):
            # New ordinary local volumes reside under the measured Docker Root Dir.
            return
        raise Refused("volume: ausente/externo/inacessível; nada criado")
    data = as_json(result.stdout, "volume")
    if data.get("driver") != "local" or data.get("options"):
        raise Refused("volume: persistência real requer inventário específico")
    storage.check(data.get("mountpoint", ""), "volume:" + reference)


def inspect_storage(project, limits):
    """Storage metadata only: no dotenv, Compose rendering, build or container action."""
    context = os.environ.get("DOCKER_CONTEXT")
    if os.environ.get("DOCKER_HOST") and not context:
        endpoint = os.environ["DOCKER_HOST"]
    else:
        endpoint = output([
            "docker", "context", "inspect", *([context] if context else []),
            "--format", "{{.Endpoints.docker.Host}}"
        ], "contexto Docker").strip()
    if not endpoint.startswith("unix://") or os.environ.get("BUILDKIT_HOST"):
        raise Refused("somente daemon local e armazenamento verificável são suportados")
    # Freeze this process to the verified endpoint, including Compose's dotenv
    # handling. Never change the user's saved context or parent environment.
    os.environ["DOCKER_HOST"] = endpoint
    os.environ.pop("DOCKER_CONTEXT", None)
    info = as_json(output([
        "docker", "info", "--format",
        '{"root":{{json .DockerRootDir}},"driver":{{json .Driver}},'
        '"driver_status":{{json .DriverStatus}}}'
    ], "Docker Root Dir"), "Docker info")
    storage = Storage(limits)
    for i, mount in enumerate(limits["HOMELAB_REQUIRED_MOUNTS"], 1):
        storage.check(mount, f"mount-obrigatório:{i}", exact=True)
    storage.check("/", "raiz")
    storage.check(project, "checkout")
    storage.check(info.get("root", ""), "Docker Root Dir")
    # Engine's containerd image store may live OUTSIDE Docker Root Dir.
    containerd_store = "io.containerd.snapshotter.v1" in json.dumps(info.get("driver_status"))
    if not containerd_store and info.get("driver") not in {"overlay2", "btrfs", "zfs", "vfs"}:
        raise Refused("driver/image store não comprovado; inventário específico necessário")
    if containerd_store and not limits["HOMELAB_EXTRA_STORAGE_PATHS"]:
        raise Refused("image store containerd: informe seu armazenamento adicional verificado")
    for i, path in enumerate(limits["HOMELAB_EXTRA_STORAGE_PATHS"], 1):
        storage.check(path, f"armazenamento-extra:{i}")
    return storage, endpoint


def preflight(project, compose, services, action):
    storage, endpoint = inspect_storage(project, policy(project))
    model = as_json(output(compose + ["config", "--format", "json",
                                      "--no-env-resolution"] + services,
                           "seleção Compose"), "Compose")
    selected = model.get("services", {})
    if not selected or any(s not in selected for s in services):
        raise Refused("seleção Compose vazia ou serviço não resolvido")
    # Existing volume options/mounts can differ from the declaration.
    checked_volumes = set()
    for name, service in selected.items():
        for i, mount in enumerate(service.get("volumes", []), 1):
            label = f"bind:{name}:{i}"
            if mount.get("type") == "bind":
                storage.check(mount.get("source", ""), label,
                              writable=not mount.get("read_only", False))
            elif mount.get("type") == "volume":
                ref = mount.get("source")
                if not ref:
                    raise Refused("volume anônimo: persistência não catalogada")
                if ref not in checked_volumes:
                    volume(storage, ref, model.get("volumes", {}).get(ref, {}))
                    checked_volumes.add(ref)
            elif mount.get("type") != "tmpfs":
                raise Refused(f"{label}: mount não suportado")
        for kind in ("secrets", "configs"):
            for ref in service.get(kind, []):
                definition = model.get(kind, {}).get(ref["source"], {})
                if "file" in definition:
                    storage.check(definition["file"], kind + ":" + name, writable=False)
        build = service.get("build")
        if build and action in {"check", "up", "build"}:
            storage.check(build.get("context", ""), "build:" + name)
    if action in {"check", "up", "build"} and any(s.get("build") for s in selected.values()):
        # No --bootstrap: never start a BuildKit container to inspect its storage.
        builder = output(["docker", "buildx", "inspect"], "builder local")
        if os.environ.get("BUILDX_BUILDER") or not re.search(r"^Driver:\s+docker\s*$", builder, re.M):
            raise Refused("builder não integrado ao daemon; armazenamento não comprovado")
        nodes = re.findall(r"^Endpoint:\s+(\S+)\s*$", builder, re.M)
        if len(nodes) != 1:
            raise Refused("endpoint do builder não comprovado")
        node = nodes[0]
        node_endpoint = node if node.startswith("unix://") else output([
            "docker", "context", "inspect", node, "--format", "{{.Endpoints.docker.Host}}"
        ], "contexto do builder").strip()
        if node_endpoint != endpoint:
            raise Refused("builder usa outro daemon; armazenamento não comprovado")
    print(f"Preflight aprovado: {len(selected)} serviços, dependências incluídas. "
          "É uma reserva mínima, não uma previsão do tamanho do download/build.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-directory", type=Path,
                        default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--storage-only", action="store_true",
                        help="somente storage; não lê .env nem resolve Compose")
    parser.add_argument("--new-project-only", action="store_true",
                        help="recusa projeto existente e não recria containers")
    parser.add_argument("action", choices=["check", "up", "pull", "build"])
    parser.add_argument("services", nargs="*")
    args = parser.parse_args()
    if any(not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", s) for s in args.services):
        parser.error("informe somente nomes de serviços, sem opções Compose")
    try:
        project = existing(args.project_directory, "projeto")
        if args.new_project_only:
            if args.action not in {"check", "up"} or (project / ".env").exists():
                raise Refused("instalação nova exige check/up sem arquivo .env")
            current = output(["docker", "ps", "--all", "--quiet", "--filter",
                              "label=com.docker.compose.project=homelab-modular-preview"], "projeto novo")
            if current.strip():
                raise Refused("projeto já existe; migração/recriação exige revisão separada")
        if args.storage_only:
            if args.action != "check" or args.services:
                raise Refused("--storage-only exige check sem serviços")
            inspect_storage(project, policy(project, read_env=False))
            print("Storage verificado; binds, serviços e backups não avaliados.")
            return 0
        # Fixed file/env selection matches the menu and web wrapper; ambient
        # COMPOSE_FILE overrides would otherwise validate a different operation.
        if os.environ.get("COMPOSE_FILE"):
            raise Refused("COMPOSE_FILE alternativo exige inventário e integração próprios")
        if any((project / name).exists() for name in (
                "compose.override.yml", "compose.override.yaml",
                "docker-compose.override.yml", "docker-compose.override.yaml")):
            raise Refused("override local exige inventário e integração próprios")
        env_file = project / ".env"
        compose = ["docker", "compose", "--project-directory", str(project),
                   "--env-file", str(env_file) if env_file.exists() else "/dev/null",
                   "-f", str(project / "docker-compose.yml")]
        if args.new_project_only:
            compose += ["--project-name", "homelab-modular-preview"]
        preflight(project, compose, args.services, args.action)
        if args.action != "check":
            operation = compose + [args.action]
            if args.action == "up":
                operation += ["-d"]
                if args.new_project_only:
                    operation += ["--no-recreate"]
            # Explicit process environment wins over .env automatic orphan removal.
            operation_env = dict(os.environ, COMPOSE_REMOVE_ORPHANS="0")
            os.execvpe("docker", operation + args.services, operation_env)
        return 0
    except (Refused, OSError, KeyError, TypeError, ValueError, AttributeError, IndexError):
        # Explicit refusal messages contain only aliases and policy key names.
        error = sys.exc_info()[1]
        reason = str(error) if isinstance(error, Refused) else "metadados incompletos/inacessíveis"
        print("Preflight BLOQUEADO: " + reason + ". Nenhuma operação de crescimento executada.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
