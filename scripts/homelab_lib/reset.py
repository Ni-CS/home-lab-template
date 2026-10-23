"""One-group private manifests, process metadata checks and supervised review.

No container action, file-content read, copying or deletion executor exists here.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

from .catalog import require, unique_object
from .source import ROOT, Refused, digest

GROUPS = {"comfyui-full", "fooocus-models", "arr-media", "finance-securo", "finance-actual"}
PRESERVED = {"immich_server", "immich_machine_learning", "immich_postgres", "immich_redis",
             "immich-server", "immich-machine-learning", "immich-postgres", "immich-redis",
             "kavita", "romm", "romm-db", "docmost", "docmost-db", "docmost-redis", "filebrowser",
             "navidrome", "picard", "metube", "lidarr", "qbittorrent", "prowlarr", "jellyfin",
             "homepage", "npm", "adguard", "uptime-kuma", "fiduswriter"}


def planner():
    spec = importlib.util.spec_from_file_location("homelab_reset_inventory", ROOT / "scripts/cleanup-plan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def process_usage(roots, proc=Path("/proc"), budget_seconds=5):
    """Read symlink metadata only. Never cmdline/environ; never publish PIDs/paths."""
    roots = [Path(r) for r in roots]
    if not roots:
        return {"inspected_processes": 0, "matching_processes": 0, "coverage": "incomplete",
                "absence_of_open_handles_proven": False}
    matched, inspected, incomplete = 0, 0, False
    deadline = time.monotonic() + budget_seconds
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        used = False
        try:
            references = [entry / "cwd", entry / "exe"]
            references.extend((entry / "fd").iterdir())
            for ref in references:
                raw = os.readlink(ref).removesuffix(" (deleted)")
                path = Path(raw)
                if path.is_absolute() and any(path == root or root in path.parents for root in roots):
                    used = True
            inspected += 1
        except FileNotFoundError:
            # Exiting processes invalidate a complete instantaneous activity proof.
            incomplete = True
        except (OSError, ValueError):
            incomplete = True
        matched += int(used)
        if time.monotonic() >= deadline:
            incomplete = True
            break
    return {"inspected_processes": inspected, "matching_processes": matched,
            "coverage": "incomplete" if incomplete else "observed",
            "absence_of_open_handles_proven": False}


def metadata_records(module, path):
    path = module.canonical(path)
    device = path.stat().st_dev
    records = []

    def failed(_error):
        raise Refused("árvore sem metadados completos")

    for base, _dirs, names, fd in os.fwalk(path, follow_symlinks=False, onerror=failed):
        for name in [".", *names]:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            require(info.st_dev == device and not stat.S_ISLNK(info.st_mode) and
                    (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)), "inode/mount não seguro")
            relative = str((Path(base) / name).relative_to(path))
            records.append({"relative": relative, "device": info.st_dev, "inode": info.st_ino,
                            "size": info.st_size, "blocks": info.st_blocks,
                            "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns,
                            "links": info.st_nlink, "regular": stat.S_ISREG(info.st_mode)})
    return sorted(records, key=lambda r: r["relative"])


def contexts(args):
    return {"data_root": args.data_root, "comfy_root": args.comfy_root,
            "project_directory": args.project_directory or str(ROOT)}


def mount_identity(path):
    try:
        result = subprocess.run(["findmnt", "--json", "--target", str(path), "--output", "UUID,FSTYPE,TARGET"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            value = json.loads(result.stdout)["filesystems"]
            if len(value) == 1:
                return value[0]
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        pass
    return None


def capacity(context):
    result = {}
    for alias, path in (("root", "/"), ("data", context["data_root"])):
        if path:
            try:
                info = os.statvfs(path)
                result[alias] = {"total_bytes": info.f_blocks * info.f_frsize,
                                 "available_bytes": info.f_bavail * info.f_frsize,
                                 "total_inodes": info.f_files, "available_inodes": info.f_favail}
            except OSError:
                result[alias] = None
    return result


def capture(group, context):
    require(group in GROUPS, "grupo fora da allowlist")
    module = planner()
    args = argparse.Namespace(**context)
    mounts = module.mount_table()
    module.LOCAL_TARGETS.clear()
    inventory = None
    docker_known = False
    try:
        inventory = module.docker_inventory()
        docker_known = True
    except (module.Blocked, OSError, ValueError, TypeError, KeyError):
        pass
    try:
        if group in module.FINANCE:
            if inventory is None:
                public = {"group": group, "status": "BLOQUEADO", "blockers": ["docker_inventory_unknown"]}
            else:
                public = module.finance_group(group, args, inventory, mounts)
        else:
            public = module.filesystem_group(group, args, mounts)
    except (module.Blocked, OSError, ValueError, KeyError, TypeError):
        public = {"group": group, "status": "BLOQUEADO", "blockers": ["target_inventory_incomplete"]}
    roots, issues = [], []
    for alias, target in module.LOCAL_TARGETS.items():
        try:
            records = metadata_records(module, target)
            roots.append({"alias": alias, "canonical_path": str(target),
                          "mount_identity": mount_identity(target),
                          "preserve": alias == "music-incoming-preserve", "records": records})
        except (OSError, module.Blocked, Refused):
            issues.append("private_manifest_metadata_incomplete")
    # Protected Fooocus outputs are metadata-only and never become deletion targets.
    if group == "fooocus-models" and context["data_root"]:
        outputs = Path(context["data_root"]) / "fooocus/outputs"
        try:
            records = metadata_records(module, outputs)
            roots.append({"alias": "fooocus-outputs-preserve", "canonical_path": str(module.canonical(outputs)),
                          "mount_identity": mount_identity(outputs), "preserve": True, "records": records})
        except (OSError, module.Blocked, Refused):
            issues.append("fooocus_outputs_metadata_unknown")
    usage = process_usage([r["canonical_path"] for r in roots if not r["preserve"]])
    if usage["matching_processes"]:
        issues.append("active_process_uses_target")
    issues.append("process_jobs_external_references_require_local_review")
    if not docker_known:
        issues.append("docker_inventory_unknown")
    protected = ({c["name"].lstrip("/"): c["state"] for c in inventory[1]
                  if c["name"].lstrip("/") in PRESERVED} if inventory else None)
    # Count link references across exact targets; unknown external links block review.
    counts = {}
    for root in roots:
        for record in root["records"]:
            if record["regular"]:
                key = (record["device"], record["inode"])
                counts[key] = counts.get(key, 0) + 1
    if any(r["links"] > counts.get((r["device"], r["inode"]), 0)
           for root in roots for r in root["records"] if r["regular"]):
        issues.append("hardlinks_outside_observed_roots")
    # Audio paths only exist in this PRIVATE manifest. No audio is moved or hashed.
    rescue = []
    if group == "arr-media":
        for root in roots:
            if root["preserve"]:
                continue
            for record in root["records"]:
                if record["regular"] and Path(record["relative"]).suffix.lower() in module.AUDIO:
                    rescue.append({"source_alias": root["alias"], "relative": record["relative"],
                                   "size": record["size"], "destination_alias": "music-incoming-preserve",
                                   "overwrite_allowed": False, "content_integrity_verified": False})
        if rescue:
            issues.append("music_rescue_required_before_arr")
        issues.append("personal_and_archive_classification_and_active_downloads_unknown")
    record = {"schema_version": 1, "group": group, "context": context,
              "created_unix": time.time(), "roots": roots, "public_inventory": public,
              "process_usage": usage, "protected_container_states": protected,
              "docker_associations": inventory[1] if inventory else None,
              "capacity": capacity(context),
              "music_rescue": rescue, "blockers": sorted(set(issues + public.get("blockers", []))),
              "execution_authorized": False}
    record["fingerprint"] = fingerprint(record)
    return record


def fingerprint(record):
    # Metadata digest, not a content checksum or proof of deletion authorization.
    return digest({"group": record["group"], "roots": record["roots"], "context": record["context"],
                   "docker_associations": record["docker_associations"]})


def public_summary(record):
    return {"group": record["group"], "fingerprint": record["fingerprint"],
            "target_roots": sum(not r["preserve"] for r in record["roots"]),
            "preserved_roots": sum(r["preserve"] for r in record["roots"]),
            "music_files_requiring_rescue": len(record["music_rescue"]),
            "process_usage": record["process_usage"], "blockers": record["blockers"],
            "capacity": record["capacity"],
            "blocked": True, "execution_authorized": False, "private_paths_printed": False}


def private_destination(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and ROOT not in path.parents and path != ROOT
            and path.name.startswith("homelab-reset-") and path.suffix == ".json",
            "manifesto privado deve ficar fora do repositório")
    for parent in path.parents:
        require(not parent.is_symlink(), "symlink no manifesto privado")
    return path


def save(path, record):
    path = private_destination(path)
    # Exclusive creation, initially 0600; no chmod, overwrite or directory creation.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)


def read_manifest(path, group):
    path = private_destination(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o077 and info.st_size <= 64 * 1024 ** 2,
                "manifesto privado exige arquivo regular 0600 e tamanho limitado")
        record = json.load(stream, object_pairs_hook=unique_object)
    require(record["schema_version"] == 1 and record["group"] == group and
            record["execution_authorized"] is False and record["fingerprint"] == fingerprint(record),
            "manifesto/grupo/fingerprint divergentes")
    return record


def expected_targets(group, context):
    data = Path(context["data_root"]) if context["data_root"] else None
    if group == "comfyui-full":
        app = Path(context["comfy_root"] or Path.home() / "AI/ComfyUI")
        require(app.is_absolute() and app.name == "ComfyUI" and ".." not in app.parts, "raiz ComfyUI inválida")
        return [app, app.parent / "comfy-env"]
    if group in {"arr-media", "fooocus-models"}:
        require(data is not None and data.is_absolute() and data != Path("/") and ".." not in data.parts,
                "raiz de dados inválida")
        return ([data / "media" / n for n in ("downloads", "filmes", "series")] if group == "arr-media"
                else [data / "fooocus/models"])
    return [Path(context["project_directory"]) / "configs" /
            ("securo" if group == "finance-securo" else "actual-budget")]


def postcheck(previous, current):
    module = planner()
    empty = []
    for path in expected_targets(previous["group"], previous["context"]):
        try:
            path.lstat()
        except FileNotFoundError:
            # Parent symlinks still invalidate an apparently absent target.
            empty.append(not any(p.is_symlink() for p in path.parents))
            continue
        try:
            _public, _entries = module.scan(path, module.mount_table())
            empty.append(_public["files"] == 0 and _public["symlinks"] == 0)
        except (OSError, module.Blocked):
            empty.append(False)
    protected_files = []
    for root in previous["roots"]:
        if root["preserve"]:
            try:
                protected_files.append(root["records"] == metadata_records(module, root["canonical_path"]))
            except (OSError, module.Blocked, Refused):
                protected_files.append(False)
    before, after = previous["protected_container_states"], current["protected_container_states"]
    return {"targets_absent_or_empty": all(empty), "preserved_files_metadata_unchanged":
            all(protected_files) if protected_files else None,
            "preserved_containers_unchanged": None if before is None or after is None else before == after,
            "functional_checks": "unknown; authorized UI checks required", "capacity_before": previous["capacity"],
            "capacity_after": current["capacity"], "target_reset_verified": False}


def dispatch(args):
    if args.action == "prepare":
        record = capture(args.group, contexts(args))
        save(args.manifest, record)
        return public_summary(record)
    previous = read_manifest(args.manifest, args.group)
    current = capture(args.group, previous["context"])
    unchanged = previous["fingerprint"] == current["fingerprint"]
    result = public_summary(current)
    result["manifest_unchanged"] = unchanged
    if args.action == "review":
        require(unchanged, "manifesto ficou obsoleto; preparar outro e revisar alvos")
        require(sys.stdin.isatty() and sys.stdout.isatty(), "revisão exige terminal humano local")
        challenge = f"REVISAR {args.group} {current['fingerprint'][:12]}"
        print("Revisão por grupo, sem autorização de exclusão. Digite: " + challenge, file=sys.stderr)
        require(input().strip() == challenge, "confirmação específica divergente")
        result["operator_reviewed"] = True
    if args.action == "postcheck":
        result.update(postcheck(previous, current))
    return result
