"""Private Overleaf CE Toolkit configuration; never downloads or starts anything."""

import ipaddress
import os
from pathlib import Path
import re
import secrets
import shlex

from .catalog import require, valid_url
from .source import ROOT


def private_directory(destination):
    path = Path(destination)
    require(path.is_absolute() and ".." not in path.parts and not path.exists() and
            not path.is_symlink() and ROOT not in path.parents, "exige destino privado absoluto novo fora do repo")
    require(not any(p.is_symlink() for p in path.parents), "symlink no destino privado")
    return path


def write_private(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(content)


def scaffold(destination, site, version, port=3007):
    require(re.fullmatch(r"6\.[0-9]+\.[0-9]+", version) is not None, "selecione explicitamente uma versão CE 6.x.y revisada")
    require(type(port) is int and 1024 <= port <= 65535, "porta LaTeX inválida")
    parsed = valid_url(site["base_url"])
    try:
        require(not ipaddress.ip_address(parsed.hostname).is_global, "LaTeX exige endereço privado")
    except ValueError:
        require(parsed.hostname.endswith((".ts.net", ".local", ".invalid")), "use DNS privado/tailnet ou IP local para LaTeX")
    folder = private_directory(destination)
    state = Path(site["state_dir"]) / "latex"
    rc = {"PROJECT_NAME": "homelab-latex", "SERVER_PRO": "false", "SIBLING_CONTAINERS_ENABLED": "false",
          "OVERLEAF_IMAGE_NAME": "sharelatex/sharelatex", "OVERLEAF_LISTEN_IP": "127.0.0.1", "OVERLEAF_PORT": str(port),
          "OVERLEAF_DATA_PATH": str(state / "overleaf"), "MONGO_ENABLED": "true", "MONGO_IMAGE": "mongo",
          "MONGO_VERSION": "8.0", "MONGO_DATA_PATH": str(state / "mongo"), "REDIS_ENABLED": "true",
          "REDIS_IMAGE": "redis:7.4", "REDIS_DATA_PATH": str(state / "redis"), "REDIS_AOF_PERSISTENCE": "true",
          "NGINX_ENABLED": "false", "GIT_BRIDGE_ENABLED": "false"}
    variables = {"OVERLEAF_APP_NAME": "HomeLab LaTeX", "OVERLEAF_SITE_URL": site["urls"].get("latex-overleaf", site["base_url"]),
                 "ENABLED_LINKED_FILE_TYPES": "project_file,project_output_file", "ENABLE_CONVERSIONS": "true",
                 "OVERLEAF_INVITE_TOKEN_SECRET": secrets.token_urlsafe(48)}
    # Validate the LaTeX URL too; it may override the general dashboard URL.
    override = valid_url(variables["OVERLEAF_SITE_URL"])
    require(override.hostname == parsed.hostname or override.hostname.endswith((".ts.net", ".local", ".invalid")),
            "URL LaTeX fora da rede privada declarada")
    folder.mkdir(mode=0o700)
    write_private(folder / "overleaf.rc", "\n".join(k + "=" + shlex.quote(v) for k, v in rc.items()) + "\n")
    write_private(folder / "variables.env", "\n".join(k + "=" + shlex.quote(v) for k, v in variables.items()) + "\n")
    write_private(folder / "version", version + "\n")
    return {"provider": "overleaf-ce-toolkit", "config_files_created": 3, "port": port,
            "listen": "loopback", "socket_mounted": False, "secret_values_printed": False,
            "runtime_verified": False, "started": False, "network_changed": False}
