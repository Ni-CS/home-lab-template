"""Interactive staging of selected modules. No automatic downloads or starts."""

import json
import sys

from . import catalog
from .latex import private_directory, write_private
from .source import ROOT


def interactive(data, site, destination):
    catalog.require(sys.stdin.isatty(), "instalador interativo exige terminal; use plan/render em automação")
    available = [s["id"] for s in catalog.entries(data) if s["availability"] == "renderable" and s["execution"] == "on-demand"]
    print("Módulos opcionais: " + ", ".join(available), file=sys.stderr)
    raw = input("Selecione IDs separados por vírgula (vazio = essenciais): ").strip()
    selected = [s.strip() for s in raw.split(",") if s.strip()]
    catalog.require(set(selected) <= set(available), "selecione somente módulos com template disponível")
    hardware = input("Hardware cpu/gpu [cpu]: ").strip() or "cpu"
    catalog.require(hardware in {"cpu", "gpu"}, "hardware inválido")
    plan = catalog.plan(data, selected, hardware)
    print(json.dumps(plan, ensure_ascii=False, indent=2), file=sys.stderr)
    model = catalog.render(data, selected, hardware, site)
    cards = catalog.homepage(data, selected, hardware, site)
    folder = private_directory(destination)
    folder.mkdir(mode=0o700)
    write_private(folder / "docker-compose.yml", json.dumps(model, indent=2) + "\n")
    write_private(folder / "site.local.json", json.dumps(site, indent=2) + "\n")
    write_private(folder / "selection.json", json.dumps({"services": selected, "hardware": hardware}, indent=2) + "\n")
    dashboard = folder / "homepage"
    dashboard.mkdir(mode=0o700)
    write_private(dashboard / "services.yaml", json.dumps(cards, ensure_ascii=False, indent=2) + "\n")
    for source, target in [("settings.example.yaml", "settings.yaml"), ("custom.css", "custom.css")]:
        write_private(dashboard / target, (ROOT / "templates/homepage" / source).read_text())
    return {"generated": True, "services": plan["services"], "hardware": hardware,
            "started": False, "downloaded": False, "existing_services_changed": False,
            "ready_for_install": False, "required_next": "install --prepared-dir (preflight only); --execute only for a new project"}
