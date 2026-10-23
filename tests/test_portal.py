"""Essential portal boundaries, module rendering and fresh-install integration."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from homelab_lib import catalog, wizard, install
from homelab_lib.source import synthetic_model
spec = importlib.util.spec_from_file_location('portal_manage', ROOT / 'apps/portal/manage.py')
portal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portal)


class PortalTests(unittest.TestCase):
    def test_build_contains_only_public_assets_and_catalog_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = portal.build(Path(tmp) / 'public')
            self.assertEqual({p.name for p in out.iterdir()}, portal.ASSETS)
            services = json.loads((out / 'services.json').read_text())
            self.assertEqual(len(services), 11)
            self.assertNotIn('securo', (out / 'services.json').read_text())
            self.assertNotIn('100.', (out / 'services.json').read_text())
            self.assertEqual(next(s for s in services if s['id'] == 'npm')['navigation']['port'], 81)
            with self.assertRaises(ValueError):portal.build(out)

    def test_config_rejects_secret_keys_and_unsafe_urls(self):
        config = json.loads((ROOT / 'apps/portal/config.example.json').read_text())
        services = portal.public_services()
        for change in [{'token':'do-not-serialize'}, {'base_url':'http://user:password@example.invalid'},
                       {'base_url':'http://localhost'}, {'base_url':'https://example.invalid/?token=x'},
                       {'services':{'olivetin':{'enabled':True}}}]:
            with self.assertRaises(ValueError):portal.validate_config(dict(config, **change), services)
        config['base_url'] = 'http://server.example.invalid'
        self.assertEqual(portal.validate_config(config, services), config)

    def test_module_preserves_original_44_11_and_is_explicit_opt_in(self):
        data = catalog.load()
        site = catalog.site_config(ROOT / 'templates/modular/site.example.json')
        self.assertEqual(len(data['services']), 44)
        self.assertEqual(sum(s['availability']=='renderable' for s in data['services']), 11)
        self.assertNotIn('portal', catalog.render(data, [], 'cpu', site)['services'])
        model = catalog.render(data, ['portal'], 'cpu', site)
        app = model['services']['portal']
        self.assertEqual(app['ports'], ['127.0.0.1:3100:8080'])
        self.assertTrue(app['read_only'])
        self.assertEqual(app['cap_drop'], ['ALL'])
        self.assertNotIn('docker.sock', json.dumps(model))
        self.assertEqual(app['profiles'], ['portal'])
        self.assertEqual(app['depends_on'] if 'depends_on' in app else {}, {})
        # Real Compose parser; synthetic environment, no daemon or actual .env.
        self.assertIn('portal', synthetic_model(json.dumps(model))['services'])

    def test_wizard_and_install_portal_with_mocked_daemon_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site = catalog.site_config(ROOT / 'templates/modular/site.example.json')
            site.update(data_dir=str(root/'data'),state_dir=str(root/'state'))
            (root/'data').mkdir(); (root/'state').mkdir()
            with patch.object(sys.stdin,'isatty',return_value=True), patch('builtins.input',side_effect=['portal','cpu']), contextlib.redirect_stderr(io.StringIO()):
                wizard.interactive(catalog.load(),site,str(root/'prepared'))
            with patch.object(install,'run',return_value='') as cmd, patch.object(install.host,'check',return_value={'blocked':False}):
                result = install.execute(root/'prepared',True,5)
            self.assertTrue(result['started'])  # Mock only, never a real daemon operation.
            config_path = root/'state/portal/portal.json'
            portal.validate_config(json.loads(config_path.read_text()),portal.public_services())
            self.assertTrue(any('--new-project-only' in c.args[0] for c in cmd.call_args_list))

    @unittest.skipUnless((ROOT/'docker-compose.yml').exists(), 'personal Compose is intentionally not exported')
    def test_reset_services_not_enabled_by_legacy_default_profiles(self):
        model = synthetic_model((ROOT/'docker-compose.yml').read_text())
        retired = {'ollama','open-webui','fooocus','sonarr','radarr','bazarr','jellyseerr','flaresolverr','actual-budget'}
        retired.update(n for n in model['services'] if n.startswith('securo-'))
        for name in retired:
            profiles = model['services'][name]['profiles']
            self.assertTrue(profiles and all(p.startswith('reinstall-') for p in profiles), name)
        for name in ['qbittorrent','prowlarr']:
            self.assertIn('music', model['services'][name]['profiles'])


if __name__ == '__main__':unittest.main()
