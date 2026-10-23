"""Opt-in metadata doctor. No mkdir, socket bind, secrets or Docker mutations."""

import json
import os
from pathlib import Path

from .catalog import require, resolve
from .source import Refused, run


def path_check(path, exact=False):
    path = Path(path)
    for part in [*path.parents, path]:
        require(not part.is_symlink(), "symlink em path configurado")
    require(path.is_dir(), "diretório necessário ausente; nada criado")
    require(os.access(path, os.R_OK | os.W_OK | os.X_OK), "acesso necessário ao diretório não comprovado")
    resolved = path.resolve(strict=True)
    entry = json.loads(run(["findmnt", "--json", "--target", str(resolved),
                            "--output", "TARGET,FSTYPE,OPTIONS"]))["filesystems"]
    require(len(entry) == 1 and entry[0]["fstype"] in {"ext4", "xfs", "btrfs", "zfs"}
            and "rw" in entry[0]["options"].split(","), "filesystem local/RW não comprovado")
    if exact:
        require(Path(entry[0]["target"]).resolve() == resolved, "mount obrigatório ausente")
    usage = os.statvfs(resolved)
    total, free = usage.f_blocks * usage.f_frsize, usage.f_bavail * usage.f_frsize
    require(total > 0 and usage.f_files > 0 and free >= 20 * 1024 ** 3 and free * 100 >= total * 10
            and usage.f_favail * 100 >= usage.f_files * 5, "reserva de bytes/inodes insuficiente ou desconhecida")
    return {"exists": True, "filesystem": entry[0]["fstype"], "total_bytes": total,
            "available_bytes": free, "available_inodes": usage.f_favail}


def listening_ports():
    result = set()
    for line in run(["ss", "-H", "-lntu"]).splitlines():
        fields = line.split()
        require(len(fields) >= 5 and fields[0] in {"tcp", "udp"}, "tabela de portas desconhecida")
        port = fields[4].rsplit(":", 1)[-1]
        require(port.isdigit(), "porta do host não mensurável")
        result.add((int(port), fields[0]))
    return result


def check(data, selected, hardware, site):
    ordered = resolve(data, selected, hardware)
    report = {"mode": "read-only-doctor", "blocked": False, "execution_authorized": False, "ready_for_install": False,
              "storage": {}, "issues": [], "gpu_detected": None}
    for alias, path, exact in [("data", site["data_dir"], False), ("state", site["state_dir"], False),
                               *[(f"required-mount-{i}", p, True) for i, p in enumerate(site["required_mounts"], 1)]]:
        try:
            report["storage"][alias] = path_check(path, exact)
        except (Refused, OSError, ValueError, KeyError):
            report["storage"][alias] = None
            report["issues"].append(alias + ": metadata/mount/capacity unverified")
    try:
        busy = listening_ports()
        by_id = {s["id"]: s for s in data["services"]}
        conflicts = [{"service": n, "port": p["published"], "protocol": p["protocol"]}
                     for n in ordered for p in by_id[n]["observed"]["ports"]
                     if (p["published"], p["protocol"]) in busy]
        report["port_conflicts"] = conflicts
        if conflicts:
            report["issues"].append("ports already in use; existing installation preserved")
    except (Refused, ValueError, KeyError):
        report["port_conflicts"] = None
        report["issues"].append("host port inventory unknown")
    if hardware == "gpu":
        try:
            rows = run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]).splitlines()
            require(bool(rows) and all(line.strip().isdigit() for line in rows), "GPU não comprovada")
            report["gpu_detected"] = True
        except Refused:
            report["gpu_detected"] = False
            report["issues"].append("NVIDIA runtime/VRAM not proven")
    report["blocked"] = bool(report["issues"])
    report["not_verified"] = ["Docker storage and containerd", "application behavior and backups",
                              "LAN/tailnet routes", "total installation budget"]
    return report
