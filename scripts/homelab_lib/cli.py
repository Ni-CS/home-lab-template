"""CLI for deterministic previews. No installation/deletion executor is exposed."""

import argparse
import json
import sys

from . import catalog
from .source import Refused


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "Argumentos inválidos; use --help. Nenhuma operação realizada.\n")


def main(argv=None):
    parser = Parser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validar catálogo e opcionalmente drift do Compose local")
    validate.add_argument("--check-local", action="store_true")
    sub.add_parser("list", help="listar disponibilidade real dos módulos")
    wizard = sub.add_parser("wizard", help="seleção interativa e geração privada, sem iniciar serviços")
    wizard.add_argument("--site", required=True)
    wizard.add_argument("--output-dir", required=True)
    install = sub.add_parser("install", help="preflight; --execute somente projeto novo e confirmado")
    install.add_argument("--prepared-dir", required=True)
    install.add_argument("--execute", action="store_true")
    install.add_argument("--budget-gib", type=int)
    latex = sub.add_parser("latex-scaffold", help="configuração privada do Overleaf CE Toolkit")
    latex.add_argument("--site", required=True)
    latex.add_argument("--destination", required=True)
    latex.add_argument("--version", required=True)
    latex.add_argument("--port", type=int, default=3007)
    for name in ("plan", "render", "homepage", "doctor"):
        command = sub.add_parser(name)
        command.add_argument("--select", nargs="*", default=[])
        command.add_argument("--hardware", choices=["cpu", "gpu"], default="cpu")
        if name != "plan":
            command.add_argument("--site", required=True)
    baseline = sub.add_parser("baseline", help="consolidação pública sem alterar Git")
    baseline.add_argument("action", choices=["check", "export"])
    baseline.add_argument("--destination")
    reset = sub.add_parser("reset", help="manifestos/revisão por grupo; sem executor")
    reset.add_argument("action", choices=["prepare", "verify", "review", "postcheck"])
    reset.add_argument("--group", required=True, choices=["comfyui-full", "fooocus-models", "arr-media", "finance-securo", "finance-actual"])
    reset.add_argument("--manifest", required=True)
    reset.add_argument("--data-root")
    reset.add_argument("--comfy-root")
    reset.add_argument("--project-directory")
    sub.add_parser("apply", help="recusado: não existe executor de instalação/reset")
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            raise Refused("executor não implementado; preview não autoriza operação")
        if args.command == "baseline":
            from . import baseline as module
            if args.action == "check":
                result = module.audit()
            else:
                catalog.require(args.destination, "export exige --destination")
                result = module.export(args.destination)
        elif args.command == "reset":
            from . import reset as module
            result = module.dispatch(args)
        elif args.command == "wizard":
            from .wizard import interactive
            result = interactive(catalog.load(), catalog.site_config(args.site), args.output_dir)
        elif args.command == "install":
            from .install import execute
            result = execute(args.prepared_dir, args.execute, args.budget_gib)
        elif args.command == "latex-scaffold":
            from .latex import scaffold
            result = scaffold(args.destination, catalog.site_config(args.site), args.version, args.port)
        else:
            data = catalog.load()
            if args.command == "validate":
                result = catalog.check_local(data) if args.check_local else {
                    "valid": True, "services": len(data["services"]),
                    "renderable": sum(s["availability"] == "renderable" for s in data["services"]),
                    "new_modules": [s["id"] for s in catalog.module_services()],
                    "runtime_verified": False}
                if args.check_local and not result["matches_local_compose"]:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 2
            elif args.command == "list":
                result = [{k: s[k] for k in ("id", "category", "execution", "availability", "hardware")}
                          for s in catalog.entries(data)]
            elif args.command == "plan":
                result = catalog.plan(data, args.select, args.hardware)
            elif args.command == "doctor":
                from .host import check
                result = check(data, args.select, args.hardware, catalog.site_config(args.site))
            else:
                site = catalog.site_config(args.site)
                func = catalog.render if args.command == "render" else catalog.homepage
                result = func(data, args.select, args.hardware, site)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if isinstance(result, dict) and (result.get("blocked") or result.get("state") == "incomplete") else 0
    except (Refused, OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        error = sys.exc_info()[1]
        print(json.dumps({"blocked": True, "reason": str(error) if isinstance(error, Refused)
                          else "metadados/configuração inválidos ou inacessíveis; detalhes omitidos",
                          "execution_authorized": False}, ensure_ascii=False), file=sys.stderr)
        return 2
