# HomeLab modular review baseline

Functional planning tools and a 44-service declaration catalog. Eleven modules
have Compose preview templates. This bundle is not a full migration or a copy of
the installed Compose; runtime and application behavior remain unverified.

```bash
python3 scripts/homelab.py validate
python3 scripts/homelab.py list
python3 scripts/homelab.py plan --select open-webui --hardware cpu
python3 scripts/homelab.py render --select open-webui --hardware cpu --site templates/modular/site.example.json
python3 scripts/homelab.py homepage --select navidrome --site templates/modular/site.example.json
```

Render prints JSON accepted as Compose/YAML. Use wizard to prepare a private
installation; install without --execute only checks it. No menu starts downloads.
Use an explicit local site configuration; secret values are not part of that
file. WEBUI_SECRET_KEY must be supplied separately before any future deployment.
No personal configs, data, old shell installers or installed Compose are copied.
Default preview: AdGuard, NPM, Homepage, Uptime Kuma. Bind defaults to loopback;
LAN/tailnet access needs local policy and host validation. Existing routes stay
untouched. Optional services require explicit profiles even in a rendered file.

See [CLI and validation](docs/operations/modular-cli.md) and
[reset status](docs/operations/modular-cli.md#reset-concluído). Only a fresh-project installer is available, behind metadata checks, a reviewed
budget and explicit --execute. No update/delete executor is included.

## Personal portal

An opt-in CPU portal adds search, favorites and private configurable links.
The original 44-service inventory and eleven templates remain separate from the
new portal module. See [preview, Docker and private access](apps/portal/README.md).
Homepage is retained as fallback. No installed routes or containers are changed.

The legacy docker-compose.yml inherited from main remains historical. It does
not represent the local 44-service deployment; use the CLI-generated previews
for new installations and review existing deployments separately.
