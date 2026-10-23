"""Read public Compose declarations with a fresh synthetic environment."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


class Refused(Exception):
    pass


def run(args, *, env=None, stdin=None):
    try:
        result = subprocess.run(args, input=stdin, env=env, capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise Refused("consulta indisponível; detalhes privados omitidos") from None
    if result.returncode:
        raise Refused("consulta recusada; detalhes privados omitidos")
    return result.stdout


def synthetic_model(text):
    env = {"PATH": os.environ["PATH"], "HOME": "/nonexistent", "LC_ALL": "C",
           "COMPOSE_DISABLE_ENV_FILE": "1", "DOCKER_CONFIG": "/nonexistent"}
    for key in re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", text):
        env[key] = "synthetic-only"
    env.update(DATA_PATH="/synthetic/data", HOMELAB_PATH="/synthetic/repo",
               UPLOAD_LOCATION="/synthetic/photos", PUID="1000", PGID="1000",
               DOCKER_GID="1000", TZ="UTC", SERVER_IP="example.invalid",
               FIDUSWRITER_PORT="8000", FIDUSWRITER_VERSION="4.1.15", IMMICH_VERSION="v2",
               SECURO_FRONTEND_URL="http://example.invalid")
    raw = run(["docker", "compose", "--project-name", "homelab-syntax",
               "--project-directory", "/tmp", "--env-file", "/dev/null", "-f", "-",
               "--profile", "*", "config", "--format", "json", "--no-env-resolution"],
              env=env, stdin=text)
    return json.loads(raw)


def shape(model):
    """No environment values, source paths, commands, labels or auth configuration."""
    result = {}
    for name, service in sorted(model["services"].items()):
        result[name] = {
            "image": service.get("image"), "build": bool(service.get("build")),
            "profiles": sorted(service.get("profiles", [])),
            "dependencies": sorted(service.get("depends_on", {})),
            "ports": [{"target": int(p["target"]), "published": int(p["published"]),
                       "protocol": p.get("protocol", "tcp")}
                      for p in service.get("ports", [])],
            "storage": [{"type": m["type"], "target": m["target"],
                         "read_only": bool(m.get("read_only", False))}
                        for m in service.get("volumes", [])],
            "environment_names": sorted(service.get("environment", {})),
            "gpu": bool(service.get("gpus") or service.get("runtime") == "nvidia" or
                        service.get("deploy", {}).get("resources", {}).get("reservations", {}).get("devices")),
            "healthcheck_declared": bool(service.get("healthcheck")),
            "restart": service.get("restart", "no"),
            "logging": ({"driver": service["logging"]["driver"],
                         "options": {k: service["logging"].get("options", {}).get(k)
                                     for k in ("max-size", "max-file", "compress")}}
                        if service.get("logging") else None),
        }
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
