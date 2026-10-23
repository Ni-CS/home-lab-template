#!/usr/bin/env python3
"""Offline portal build and read-only preview. No package manager or Docker API."""
import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit

APP = Path(__file__).resolve().parent
ROOT = APP.parent.parent
ASSETS = {'index.html', 'styles.css', 'base.css', 'app.js', 'model.js', 'mark.svg', 'services.json', 'art.js', 'grain.svg', 'display.ttf', 'OFL.txt'}
ICONS = {'aperture', 'music', 'play', 'folder', 'book', 'notebook', 'activity', 'chart', 'grid', 'shield', 'network'}


def read_json(path):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def url(value, base=False):
    if not isinstance(value, str):
        raise ValueError('invalid URL')
    if not value:
        return
    p = urlsplit(value)
    if (p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password or p.query or p.fragment
            or any(ord(c) <= 32 or c == '\\' for c in value)
            or p.hostname in {'localhost', '127.0.0.1', '::1', '0.0.0.0', '::'}):
        raise ValueError('invalid URL')
    # Force parsing of invalid/out-of-range ports, including URLs with no base override.
    port = p.port
    if base and (port is not None or p.path not in {'', '/'}):
        raise ValueError('base URL must contain only scheme and hostname')


def validate_config(config, services):
    if (not isinstance(config, dict) or set(config) != {'schema_version', 'title', 'base_url', 'services'}
            or config['schema_version'] != 1 or not isinstance(config['title'], str)
            or not 1 <= len(config['title'].strip()) <= 40 or not isinstance(config['services'], dict)):
        raise ValueError('invalid config')
    url(config['base_url'], base=True)
    ids = {s['id'] for s in services}
    for name, entry in config['services'].items():
        if (name not in ids or not isinstance(entry, dict)
                or not set(entry) <= {'title', 'url', 'order', 'icon', 'favorite', 'enabled'}):
            raise ValueError('invalid service preference')
        if 'url' in entry:
            url(entry['url'])
        if 'title' in entry and (not isinstance(entry['title'], str) or not 1 <= len(entry['title'].strip()) <= 60):
            raise ValueError('invalid title')
        if 'icon' in entry and entry['icon'] not in ICONS:
            raise ValueError('invalid icon')
        if 'order' in entry and (type(entry['order']) is not int or not 0 <= entry['order'] <= 1000):
            raise ValueError('invalid order')
        for key in ['favorite', 'enabled']:
            if key in entry and type(entry[key]) is not bool:
                raise ValueError('invalid preference')
    return config


def public_services():
    catalog = read_json(ROOT / 'catalog/services.json')
    ui = read_json(ROOT / 'catalog/portal-ui.json')
    by_id = {s['id']: s for s in catalog['services']}
    result = []
    for name, metadata in ui['services'].items():
        service = by_id[name]
        result.append({'id': name, **metadata, 'navigation': service['navigation']})
    return result


def build(destination):
    destination = Path(destination).absolute()
    if destination.exists() or any(p.is_symlink() for p in [destination, *destination.parents]):
        raise ValueError('build requires a new directory without symlinks')
    # An explicit asset allowlist prevents local config or source files entering the web root.
    content = {name: (APP / 'web' / name).read_bytes() for name in ASSETS - {'services.json'}}
    content['services.json'] = (json.dumps(public_services(), ensure_ascii=False, indent=2) + '\n').encode()
    destination.mkdir(parents=True)
    for name, data in content.items():
        (destination / name).write_bytes(data)
    return destination


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, directory, config=None, **kwargs):
        self.directory, self.config = Path(directory), config
        super().__init__(*args, **kwargs)

    def log_message(self, *_args):
        pass  # Do not persist hostnames, URLs, IPs, request headers or preferences.

    def respond(self, status, body, mime='application/json; charset=utf-8', head=False):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        path = urlsplit(self.path).path
        if path == '/healthz':
            # Portal health only, never evidence of health of linked services.
            return self.respond(200, b'{"portal":"ready","services":"unknown"}', head=head)
        if path == '/api/config':
            try:
                services = read_json(self.directory / 'services.json')
                value = read_json(self.config or APP / 'config.example.json')
                body = json.dumps(validate_config(value, services), ensure_ascii=False).encode()
            except (OSError, ValueError, KeyError, TypeError):
                return self.respond(503, b'{"error":"configuration_unavailable"}', head=head)
            return self.respond(200, body, head=head)
        name = 'index.html' if path == '/' else path.removeprefix('/')
        if name not in ASSETS or (self.directory / name).is_symlink():
            return self.respond(404, b'{"error":"not_found"}', head=head)
        try:
            body = (self.directory / name).read_bytes()
        except OSError:
            return self.respond(404, b'{"error":"not_found"}', head=head)
        mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        return self.respond(200, body, mime + ('; charset=utf-8' if mime.startswith('text/') or name.endswith(('.js', '.json')) else ''), head=head)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    b.add_argument('--output-dir', required=True)
    s = sub.add_parser('serve')
    s.add_argument('--directory', required=True)
    s.add_argument('--config')
    s.add_argument('--bind', default='127.0.0.1')
    s.add_argument('--port', type=int, default=3100)
    args = parser.parse_args()
    try:
        if args.command == 'build':
            build(args.output_dir)
            print(f'Portal built: {len(ASSETS)} public assets; no local config copied.')
        else:
            ip = ipaddress.ip_address(args.bind)
            if ip.version != 4 or ip.is_global or ip.is_multicast:
                raise ValueError('private bind required')
            directory = Path(args.directory).resolve(strict=True)
            if not all((directory / n).is_file() for n in ASSETS):
                raise ValueError('build missing')
            if args.config:
                validate_config(read_json(args.config), read_json(directory / 'services.json'))
            server = ThreadingHTTPServer((args.bind, args.port), partial(Handler, directory=directory, config=args.config))
            print(f'Portal preview ready on port {server.server_port}. No service health inferred.', flush=True)
            server.serve_forever()
    except (OSError, ValueError, KeyError, TypeError):
        print('Portal blocked: invalid build/configuration, unavailable path or occupied port. Details omitted.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
