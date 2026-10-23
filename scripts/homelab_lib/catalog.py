"""Strict catalog validation, drift detection and dependency resolution."""

import copy
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .source import ROOT, Refused, digest, shape, synthetic_model

ID = re.compile(r"[a-z][a-z0-9-]{0,62}")
SERVICE_KEYS = {"id", "category", "execution", "availability", "dependencies", "integrations",
                "hardware", "observed", "template", "backup", "post_install", "growth_bytes", "navigation"}


def unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise Refused("JSON contém chave duplicada")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object)


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def load(path=None):
    data = read_json(path or ROOT / "catalog/services.json")
    validate(data)
    modules = module_services()
    if modules:
        combined = dict(data, services=data["services"] + modules)
        combined["source_shape_sha256"] = digest({s["id"]: s["observed"] for s in combined["services"]})
        validate(combined)
    return data


def module_services():
    """New modules stay separate from the 44-service historical evidence."""
    path = ROOT / "catalog/modules.json"
    if not path.exists():
        return []
    data = read_json(path)
    require(set(data) == {"schema_version", "services"} and data["schema_version"] == 1
            and isinstance(data["services"], list) and [s.get("id") for s in data["services"]] == ["portal"],
            "extensões do catálogo inválidas")
    return data["services"]


def entries(data):
    return data["services"] + [s for s in module_services() if s["id"] not in {s["id"] for s in data["services"]}]


def validate(data):
    require(set(data) == {"schema_version", "source_shape_sha256", "services", "future_modules"}
            and data["schema_version"] == 1, "versão/contrato do catálogo inválido")
    services = data["services"]
    require(isinstance(services, list) and bool(services), "catálogo vazio")
    by_id = {}
    for service in services:
        require(isinstance(service, dict) and set(service) == SERVICE_KEYS, "campos de serviço inválidos")
        name = service["id"]
        require(isinstance(name, str) and ID.fullmatch(name) and name not in by_id, "ID inválido/duplicado")
        by_id[name] = service
        require(service["execution"] in {"always-on", "on-demand"}, "modo de execução inválido")
        require(service["availability"] in {"renderable", "inventory-only"}, "disponibilidade inválida")
        require(isinstance(service["category"], str) and ID.fullmatch(service["category"]), "categoria inválida")
        for key in ("dependencies", "integrations", "post_install"):
            require(isinstance(service[key], list) and all(isinstance(s, str) for s in service[key])
                    and len(service[key]) == len(set(service[key])), "lista inválida")
        hw = service["hardware"]
        require(set(hw) == {"gpu", "variants", "minimum_ram_mib"} and
                hw["gpu"] in {"none", "optional", "required"} and
                hw["variants"] == ({"none": ["cpu"], "optional": ["cpu", "gpu"], "required": ["gpu"]}[hw["gpu"]]),
                "variantes CPU/GPU inválidas")
        require(hw["minimum_ram_mib"] is None or type(hw["minimum_ram_mib"]) is int and hw["minimum_ram_mib"] > 0,
                "RAM mínima inválida")
        require(service["growth_bytes"] is None or type(service["growth_bytes"]) is int and service["growth_bytes"] >= 0,
                "orçamento inválido")
        observed = service["observed"]
        require(set(observed) == {"image", "build", "profiles", "dependencies", "ports", "storage",
                                  "environment_names", "gpu", "healthcheck_declared", "restart", "logging"}, "evidência inválida")
        require(service["dependencies"] == observed["dependencies"], "dependências divergem da evidência")
        for port in observed["ports"]:
            require(set(port) == {"target", "published", "protocol"} and
                    all(type(port[k]) is int and 1 <= port[k] <= 65535 for k in ("target", "published"))
                    and port["protocol"] in {"tcp", "udp"}, "porta inválida")
        navigation = service["navigation"]
        require(navigation is None or set(navigation) == {"port", "scheme", "path"} and
                navigation["scheme"] in {"http", "https"} and navigation["path"].startswith("/") and
                navigation["port"] in [p["published"] for p in observed["ports"]], "navegação inválida")
        for mount in observed["storage"]:
            require(set(mount) == {"type", "target", "read_only"} and mount["type"] in {"bind", "volume", "tmpfs"}
                    and isinstance(mount["target"], str) and mount["target"].startswith("/")
                    and type(mount["read_only"]) is bool, "persistência inválida")
        require(isinstance(service["backup"], str) and bool(service["post_install"]), "backup/checks ausentes")
        template = service["template"]
        require((service["availability"] == "renderable") == (template is not None), "template/disponibilidade divergente")
        if template is not None:
            require(template == f"templates/modular/{name}.json", "template fora da allowlist")
        require(name not in {"olivetin", "actual-budget"} and not name.startswith("securo-") or
                service["execution"] == "on-demand", "admin/finanças não podem integrar o default")
    for service in services:
        require(all(n in by_id and n != service["id"] for n in service["dependencies"] + service["integrations"]),
                "referência de serviço inválida")
    resolve(data, list(by_id), include_defaults=False, check_hardware=False)
    require(digest({s["id"]: s["observed"] for s in services}) == data["source_shape_sha256"],
            "fingerprint da evidência divergente")
    require(isinstance(data["future_modules"], list), "módulos futuros inválidos")
    for module in data["future_modules"]:
        require(set(module) == {"id", "status", "category", "gpu"} and module["status"] in {"planned", "toolkit-ready"}
                and module["id"] not in by_id and ID.fullmatch(module["id"]), "módulo futuro inválido")
    return by_id


def resolve(data, selected, hardware="cpu", *, include_defaults=True, check_hardware=True):
    by_id = {s["id"]: s for s in entries(data)}
    selected = set(selected)
    require(selected <= by_id.keys(), "seleção contém módulo desconhecido ou ainda planejado")
    if include_defaults:
        selected.update(s["id"] for s in entries(data) if s["execution"] == "always-on")
    done, active, ordered = set(), set(), []

    def visit(name):
        if name in done:
            return
        require(name not in active, "ciclo de dependências")
        active.add(name)
        service = by_id[name]
        if check_hardware:
            require(hardware in service["hardware"]["variants"] or service["hardware"]["gpu"] == "none",
                    "seleção requer variante GPU não selecionada")
        for dependency in service["dependencies"]:
            visit(dependency)
        active.remove(name)
        done.add(name)
        ordered.append(name)

    for name in sorted(selected):
        visit(name)
    ports = set()
    for name in ordered:
        for port in by_id[name]["observed"]["ports"]:
            key = (port["published"], port["protocol"])
            require(key not in ports, "conflito de portas na seleção")
            ports.add(key)
    return ordered


def check_local(data):
    actual = shape(synthetic_model((ROOT / "docker-compose.yml").read_text()))
    expected = {s["id"]: s["observed"] for s in data["services"]}
    changed = sorted(n for n in actual.keys() | expected.keys() if actual.get(n) != expected.get(n))
    return {"matches_local_compose": not changed, "changed_services": changed,
            "local_services": len(actual), "catalog_services": len(expected), "runtime_verified": False}


def plan(data, selected, hardware):
    external = {m["id"] for m in data["future_modules"] if m["status"] == "toolkit-ready"}
    requested_external = sorted(set(selected) & external)
    ordered = resolve(data, [n for n in selected if n not in external], hardware)
    by_id = {s["id"]: s for s in entries(data)}
    return {"mode": "plan-only", "target": "new-installation-preview", "execution_authorized": False,
            "hardware": hardware, "hardware_detected": False, "runtime_verified": False,
            "external_toolkit_modules": requested_external,
            "services": ordered, "defaults": [n for n in ordered if by_id[n]["execution"] == "always-on"],
            "inventory_only": [n for n in ordered if by_id[n]["availability"] != "renderable"],
            "optional_integrations": {n: by_id[n]["integrations"] for n in ordered if by_id[n]["integrations"]},
            "growth_bytes": None, "blockers_for_install": ["host_capacity_paths_ports_backup_not_verified",
                                                           "explicit_new_project_install_budget_required"]}


def valid_url(value):
    require(isinstance(value, str) and not any(ord(c) < 32 for c in value), "URL inválida")
    parsed = urlsplit(value)
    require(parsed.scheme in {"http", "https"} and bool(parsed.hostname) and
            not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
            "URL inválida ou contém credencial")
    return parsed


def site_config(path):
    data = read_json(path)
    require(set(data) == {"schema_version", "data_dir", "state_dir", "bind_address", "base_url", "urls", "required_mounts", "extra_storage_paths"}
            and data["schema_version"] == 1, "contrato da configuração local inválido")
    for key in ("data_dir", "state_dir"):
        value = Path(data[key])
        require(value.is_absolute() and value != Path("/") and ".." not in value.parts
                and not any(c in str(value) for c in "@$:") and
                not any(ord(c) < 32 for c in str(value)), "path local inválido")
    require(not (Path(data["data_dir"]) == Path(data["state_dir"]) or
                 Path(data["data_dir"]) in Path(data["state_dir"]).parents or
                 Path(data["state_dir"]) in Path(data["data_dir"]).parents), "raízes de dados/estado sobrepostas")
    bind = ipaddress.ip_address(data["bind_address"])
    require(bind.version == 4 and not bind.is_global and not bind.is_multicast, "bind deve ser IPv4 local explícito")
    valid_url(data["base_url"])
    require(isinstance(data["required_mounts"], list) and all(isinstance(p, str) and Path(p).is_absolute()
            and Path(p) != Path("/") and ".." not in Path(p).parts for p in data["required_mounts"]),
            "mounts obrigatórios inválidos")
    require(isinstance(data["extra_storage_paths"], list) and all(isinstance(p, str) and Path(p).is_absolute()
            and Path(p) != Path("/") and ".." not in Path(p).parts and ":" not in p
            for p in data["extra_storage_paths"]), "armazenamento adicional inválido")
    require(isinstance(data["urls"], dict), "URLs locais inválidas")
    for key, value in data["urls"].items():
        require(ID.fullmatch(key), "ID de URL inválido")
        valid_url(value)
    return data


def render(data, selected, hardware, site):
    ordered = resolve(data, selected, hardware)
    by_id = {s["id"]: s for s in entries(data)}
    result = {"name": "homelab-modular-preview", "services": {}}
    parsed = valid_url(site["base_url"])
    host_literal = "[" + parsed.hostname + "]" if ":" in parsed.hostname else parsed.hostname
    replacements = {"@ROOT@": str(ROOT), "@STATE@": site["state_dir"], "@DATA@": site["data_dir"],
                    "@BIND@": site["bind_address"], "@HOST@": parsed.netloc,
                    "@HOMEPAGE_HOSTS@": ",".join(sorted({parsed.netloc, host_literal, host_literal + ":3001"}))}

    def replace(value):
        if isinstance(value, str):
            for key, text in replacements.items():
                value = value.replace(key, text)
            return value
        if isinstance(value, list):
            return [replace(v) for v in value]
        if isinstance(value, dict):
            return {k: replace(v) for k, v in value.items()}
        return value

    for name in ordered:
        service = by_id[name]
        require(service["availability"] == "renderable", "seleção contém módulo sem template implementado")
        definition = read_json(ROOT / service["template"])
        require(set(definition) == {"cpu", "gpu"}, "contrato do template inválido")
        variant = hardware if service["hardware"]["gpu"] != "none" else "cpu"
        require(definition[variant] is not None, "template da variante ausente")
        model = replace(copy.deepcopy(definition[variant]))
        fields = {"image", "restart", "logging", "volumes", "ports", "environment", "depends_on", "deploy"}
        if name == "portal":
            fields.update({"build", "read_only", "user", "cap_drop", "security_opt"})
            require(model.get("build") == {"context": str(ROOT), "dockerfile": "apps/portal/Dockerfile"}
                    and model.get("read_only") is True and model.get("user") == "65532:65532"
                    and model.get("cap_drop") == ["ALL"]
                    and model.get("security_opt") == ["no-new-privileges:true"]
                    and model.get("ports") == ["127.0.0.1:3100:8080"], "isolamento do portal divergente")
        require(set(model) <= fields,
                "template contém campo não revisado")
        require(set(model.get("depends_on", {})) == set(service["dependencies"]), "dependências do template divergentes")
        require(not model.get("privileged") and not any("docker.sock" in str(m) for m in model.get("volumes", [])),
                "template inclui privilégio/socket não autorizado")
        if service["execution"] == "on-demand":
            model["profiles"] = [service["category"]]
            model["restart"] = "no"
        else:
            model.pop("profiles", None)
        result["services"][name] = model
    if hardware == "cpu":
        require(not re.search(r'nvidia|cuda|"gpus"', json.dumps(result), re.I), "resíduo GPU na variante CPU")
    return result


def homepage(data, selected, hardware, site):
    ordered = resolve(data, selected, hardware)
    by_id = {s["id"]: s for s in entries(data)}
    require(site["urls"].keys() <= by_id.keys() | {m["id"] for m in data["future_modules"]}, "URL refere módulo desconhecido")
    host = valid_url(site["base_url"]).hostname
    require(host not in {"localhost", "127.0.0.1", "::1"}, "dashboard remota não aceita base localhost")
    groups = {}
    for name in ordered:
        if by_id[name]["availability"] != "renderable":
            continue
        nav = by_id[name]["navigation"]
        if nav is None:
            continue
        host_literal = "[" + host + "]" if ":" in host else host
        url = site["urls"].get(name, f"{nav['scheme']}://{host_literal}:{nav['port']}{nav['path']}")
        groups.setdefault(by_id[name]["category"], []).append({name: {
            "href": url, "description": "Declarado; estado operacional desconhecido"}})
    return [{category: cards} for category, cards in groups.items()]
