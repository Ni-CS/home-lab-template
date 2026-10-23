"""Install only a fresh project through the shared guard; no updates or deletion."""

import json
import os
from pathlib import Path
import sys

from . import catalog, host
from .latex import write_private
from .source import ROOT, run


def prepared(path):
    path = Path(path)
    catalog.require(path.is_absolute() and ROOT not in path.parents and ".." not in path.parts and
                    path.is_dir() and not any(p.is_symlink() for p in [path, *path.parents]),
                    "instalação preparada exige diretório privado fora do repo")
    catalog.require(not (path / ".env").exists() and not (path / ".env").is_symlink(), "não carregar .env de uma instalação preparada")
    site = catalog.site_config(path / "site.local.json")
    selection = catalog.read_json(path / "selection.json")
    catalog.require(set(selection) == {"services", "hardware"} and selection["hardware"] in {"cpu", "gpu"},
                    "seleção preparada inválida")
    data = catalog.load()
    model = catalog.render(data, selection["services"], selection["hardware"], site)
    catalog.require(catalog.read_json(path / "docker-compose.yml") == model, "Compose preparado foi alterado; gerar novamente")
    return path, data, site, selection, model


def writable_sources(model, site):
    sources = set()
    for service in model["services"].values():
        for mount in service.get("volumes", []):
            parts = mount.split(":")
            source = Path(parts[0])
            catalog.require(source.is_absolute() and ".." not in source.parts and
                            not any(p.is_symlink() for p in [source, *source.parents]), "bind inválido ou symlink")
            if len(parts) == 3 and parts[2] == "ro":
                if source == Path(site["state_dir"]) / "portal" and mount.endswith(":/config:ro"):
                    catalog.require(not source.exists() or source.is_dir() and not any(source.iterdir()),
                                    "configuração de portal existente; preservar e revisar separadamente")
                    sources.add(source)
                    continue
                catalog.require(source.is_dir(), "biblioteca somente leitura ausente")
                continue
            roots = [Path(site["state_dir"]), Path(site["data_dir"])]
            catalog.require(any(root in source.parents for root in roots), "bind gravável fora das raízes configuradas")
            if source.exists():
                catalog.require(source.is_dir() and not any(source.iterdir()),
                                "persistência existente não está vazia; migração exige aprovação separada")
            sources.add(source)
    return sorted(sources)


def execute(path, apply=False, budget_gib=None):
    path, data, site, selection, model = prepared(path)
    catalog.require(not run(["docker", "ps", "--all", "--quiet", "--filter",
                             "label=com.docker.compose.project=homelab-modular-preview"]).strip(),
                    "projeto já instalado; não atualizar ou interromper serviços")
    diagnostic = host.check(data, selection["services"], selection["hardware"], site)
    catalog.require(not diagnostic["blocked"], "pré-verificações de host não aprovadas")
    sources = writable_sources(model, site)
    env = dict(os.environ)
    env["HOMELAB_REQUIRED_MOUNTS"] = ":".join(site["required_mounts"])
    env["HOMELAB_EXTRA_STORAGE_PATHS"] = ":".join(site["extra_storage_paths"])
    env["COMPOSE_REMOVE_ORPHANS"] = "0"
    if apply:
        catalog.require(type(budget_gib) is int and 1 <= budget_gib <= 9979,
                        "execução exige orçamento explícito --budget-gib após revisão do download/extração")
    reserve = 20 + (budget_gib or 0)
    for key, floor in [("HOMELAB_MIN_FREE_GIB", reserve), ("HOMELAB_MIN_FREE_PERCENT", 10),
                       ("HOMELAB_MIN_FREE_INODES_PERCENT", 5)]:
        env[key] = str(max(floor, int(env.get(key, floor))))
    guard_base = [sys.executable, str(ROOT / "scripts/compose-guard.py"), "--project-directory", str(path)]
    # Check root, daemon store, containerd and required mounts BEFORE creating paths.
    run(guard_base + ["--storage-only", "check"], env=env)
    if not apply:
        return {"mode": "install-preflight", "new_project": True, "started": False,
                "writable_directories_to_create": len(sources), "growth_authorized": False,
                "remaining": "shared guard checks Docker/containerd and all binds before up"}
    # Only new/empty declared directories; never copy from existing app data.
    for source in sources:
        source.mkdir(parents=True, exist_ok=True)
    if "portal" in model["services"]:
        # Only sanitized URLs; no secrets, databases, authentication or Docker socket.
        import importlib.util
        spec = importlib.util.spec_from_file_location("portal_manage", ROOT / "apps/portal/manage.py")
        portal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(portal)
        visible = {s["id"] for s in portal.public_services()}
        config = {"schema_version": 1, "title": "HomeLab", "base_url": site["base_url"],
                  "services": {n: {"url": u} for n, u in site["urls"].items() if n in visible}}
        portal.validate_config(config, portal.public_services())
        config_path = Path(site["state_dir"]) / "portal/portal.json"
        write_private(config_path, json.dumps(config, indent=2) + "\n")
        # Non-root container reads exactly this non-secret preferences file.
        config_path.chmod(0o644)
    dashboard = Path(site["state_dir"]) / "homepage"
    cards = catalog.homepage(data, selection["services"], selection["hardware"], site)
    write_private(dashboard / "services.yaml", json.dumps(cards, ensure_ascii=False, indent=2) + "\n")
    for source, target in [("settings.example.yaml", "settings.yaml"), ("custom.css", "custom.css")]:
        write_private(dashboard / target, (ROOT / "templates/homepage" / source).read_text())
    # Fixed private artifact is JSON/Compose, has no .env and is validated above.
    guard = guard_base + ["--new-project-only", "up", *model["services"]]
    run(guard, env=env)
    return {"mode": "new-project-installed", "started": True, "services": sorted(model["services"]),
            "existing_services_recreated": False, "functional_checks": "required; startup is not health"}
