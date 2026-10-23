"""Metadata Git audit and explicit, hash-checked public export; never git add/push."""

import hashlib
import json
from pathlib import Path

from .catalog import load, read_json, require
from .source import ROOT, Refused, run, synthetic_model


def audit():
    tracked = run(["git", "-C", str(ROOT), "ls-files", "-z"]).split("\0")
    tracked = [name for name in tracked if name]
    refs = {}
    for ref in ("HEAD", "origin/main"):
        try:
            text = run(["git", "-C", str(ROOT), "show", ref + ":docker-compose.yml"])
            refs[ref] = {"services": len(synthetic_model(text)["services"]), "source": "local-git-ref"}
        except Refused:
            refs[ref] = {"services": None, "source": "unavailable-local-ref"}
    status = run(["git", "-C", str(ROOT), "status", "--porcelain=v1", "--untracked-files=no"])
    return {"mode": "read-only", "tracked_files": len(tracked),
            "tracked_private_configs_requiring_review": sum(n.startswith("configs/") for n in tracked),
            "tracked_dirty_files": len(status.splitlines()), "refs": refs,
            "catalog_services": len(load()["services"]), "fetched_remote": False,
            "git_modified": False, "public_export_replaces_installed_compose": False}


def safe_relative(value):
    path = Path(value)
    require(not path.is_absolute() and path.parts and ".." not in path.parts and
            not any(p in {".git", "configs", ".env"} for p in path.parts), "path fora da allowlist pública")
    return path


def export(destination, manifest_path=None):
    manifest = read_json(manifest_path or ROOT / "catalog/public-files.json")
    require(set(manifest) == {"schema_version", "files"} and manifest["schema_version"] == 1,
            "manifesto público inválido")
    destination = Path(destination)
    require(destination.is_absolute() and not destination.exists() and not destination.is_symlink(),
            "export exige destino absoluto novo, sem overwrite")
    require(ROOT != destination and ROOT not in destination.parents, "export público deve ficar fora da árvore local")
    for parent in destination.parents:
        require(not parent.is_symlink(), "symlink no destino de export")
    checked, names = [], set()
    for item in manifest["files"]:
        require(set(item) == {"source", "destination", "sha256"}, "entrada de allowlist inválida")
        source, target = safe_relative(item["source"]), safe_relative(item["destination"])
        require(str(target) not in names, "destino público duplicado")
        names.add(str(target))
        require(source.parts[0] in {"catalog", "templates", "scripts", "tests", "docs", "apps", "examples"}
                or str(source) in {"README.md", "AGENTS.md", ".gitignore", ".dockerignore"}, "origem pública inválida")
        require(not any(".local." in part for part in source.parts), "configuração privada fora do baseline")
        absolute = ROOT / source
        require(not any(p.is_symlink() for p in [absolute, *absolute.parents] if p != ROOT.parent),
                "symlink em origem pública")
        content = absolute.read_bytes()
        require(hashlib.sha256(content).hexdigest() == item["sha256"], "arquivo público mudou; revisar allowlist antes de exportar")
        checked.append((target, content, item["sha256"]))
    # Validate everything before creating the new bundle. Never touch current files.
    destination.mkdir(mode=0o700)
    for target, content, _hash in checked:
        path = destination / target
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
    record = {"schema_version": 1, "files": [{"path": str(p), "sha256": h} for p, _c, h in checked],
              "scope": "44-service-inventory-and-partial-portable-templates", "runtime_verified": False}
    with (destination / "PUBLIC-MANIFEST.json").open("x") as stream:
        json.dump(record, stream, indent=2)
    # Re-export remains usable after template README/ignore files move to the root.
    public_manifest = destination / "catalog/public-files.json"
    public_manifest.parent.mkdir(parents=True, exist_ok=True)
    with public_manifest.open("x") as stream:
        json.dump({"schema_version": 1, "files": [
            {"source": str(p), "destination": str(p), "sha256": h} for p, _c, h in checked]}, stream, indent=2)
    return {"exported_files": len(checked), "git_modified": False, "private_config_paths_copied": False, "approved_files_hash_matched": True,
            "installed_compose_copied": False, "destination_printed": False}
