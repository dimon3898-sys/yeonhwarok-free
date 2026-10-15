"""Focused CPU-only loopback source selection/security checks; no GPU claim."""
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('astra_server_under_test', ROOT / 'serve_astra.py')
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)


class RuntimeServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='astra-runtime-test-', dir='/workspace')
        self.dir = Path(self.temp.name)
        self.file = self.dir / 'source.mjs'
        self.file.write_bytes(b'export const source="UNCHANGED_BYTES";\n')
        self.record = {'url': '/modules/reference_terrain_material_v4.mjs', 'path': str(self.file),
                       'bytes': self.file.stat().st_size, 'sha256': hashlib.sha256(self.file.read_bytes()).hexdigest()}
        self.config = {'schema': 'ASTRA_RUNTIME_SERVER_CONFIG_V1', 'bundleRoot': str(self.dir),
                       'bindings': [self.record], 'runtimeConfig': {'schema': 'ASTRA_RUNTIME_HTTP_V1', 'testOnlySoftwareProbe': False}}
        self.config_file = self.dir / 'server.json'
        self.http = None

    def tearDown(self):
        if self.http:
            self.http.shutdown()
            self.http.server_close()
            self.thread.join(5)
        self.temp.cleanup()

    def load(self):
        raw = json.dumps(self.config).encode()
        self.config_file.write_bytes(raw)
        return server_module.load_config(self.config_file, hashlib.sha256(raw).hexdigest())

    def start(self):
        config, exact = self.load()
        self.http = server_module.make_server(config, exact)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def get(self, path, *, host=None, method='GET'):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        conn.request(method, path, headers={'Host': host or f'127.0.0.1:{self.http.server_port}'})
        result = conn.getresponse()
        status, headers, body = result.status, dict(result.getheaders()), result.read()
        conn.close()
        return status, headers, body

    def test_loopback_only_and_importmap_installed_before_bootstrap(self):
        self.start()
        self.assertEqual(self.http.server_address[0], '127.0.0.1')
        status, headers, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertLess(body.index(b'type="importmap"'), body.index(b'src="/astra/bootstrap.mjs"'))
        self.assertIn(server_module.IMPORT_MAP.encode(), body)
        self.assertIn("'sha256-" + server_module.IMPORT_MAP_SHA + "'", headers['Content-Security-Policy'])
        self.assertNotIn("script-src 'unsafe-inline'", headers['Content-Security-Policy'])

    def test_baseline_query_serves_exact_original_bytes(self):
        self.start()
        self.assertEqual(self.get(self.record['url'] + '?baseline')[2], self.file.read_bytes())
        self.assertEqual(self.get(self.record['url'] + '?anything')[0], 400)

    def test_no_repository_browse_or_public_render_api(self):
        self.start()
        for path in ['/render', '/start', '/diagnostics', '/.git/config', '/astra-data/', '/static/not-listed.png']:
            self.assertEqual(self.get(path)[0], 404)
        self.assertEqual(self.get('/render', method='POST')[0], 501)

    def test_host_rebinding_forbidden(self):
        self.start()
        self.assertEqual(self.get('/', host='attacker.example')[0], 403)

    def test_encoded_traversal_forbidden(self):
        self.start()
        for path in ['/modules/%2e%2e/source.mjs', '/modules/%5csecret', '/modules/%00secret']:
            self.assertEqual(self.get(path)[0], 400)

    def test_source_change_after_start_fails_closed(self):
        self.start()
        self.file.write_bytes(b'changed')
        self.assertEqual(self.get(self.record['url'])[0], 409)

    def test_symlink_source_rejected(self):
        linked = self.dir / 'symlink.mjs'
        linked.symlink_to(self.file)
        self.record['path'] = str(linked)
        with self.assertRaisesRegex(ValueError, 'SYMLINK'):
            self.load()

    def test_config_sha_required_and_checked(self):
        self.config_file.write_bytes(b'{}')
        for expected in ['missing', '0' * 64]:
            with self.assertRaisesRegex(ValueError, 'CONFIG_SHA'):
                server_module.load_config(self.config_file, expected)

    def test_artifact_hash_mismatch_rejected_before_bind(self):
        self.record['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'BOUND_SOURCE'):
            self.load()

    def test_duplicate_route_rejected(self):
        self.config['bindings'].append(dict(self.record))
        with self.assertRaisesRegex(ValueError, 'UNIQUE_EXACT'):
            self.load()

    def test_sources_cannot_escape_repo_and_bundle_roots(self):
        self.record['path'] = '/etc/hosts'
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_ALLOWED_ROOT'):
            self.load()

    def test_production_bootstrap_never_selects_test_context(self):
        self.start()
        body = self.get('/astra/bootstrap.mjs')[2]
        self.assertIn(b'bootAstraRuntime()', body)
        self.assertNotIn(b'testOnlySoftwareProbe:true', body)

    def test_explicit_software_harness_is_separately_labelled(self):
        self.config['runtimeConfig']['testOnlySoftwareProbe'] = True
        self.start()
        self.assertIn(b'testOnlySoftwareProbe:true', self.get('/astra/bootstrap.mjs')[2])

    def test_saved_scene_control_intent_order_survives_http_and_original_compiler(self):
        scene_file = ROOT.parent / 'moving-frontier-glow-fix-v1' / 'fixtures' / 'SCENE_PLAN.json'
        scene = json.loads(scene_file.read_text())
        self.config['runtimeConfig']['bootstrap'] = {'scenePlan': scene}
        self.start()
        status, _, body = self.get('/runtime-config.json')
        self.assertEqual(status, 200)
        received = json.loads(body)['bootstrap']['scenePlan']

        def same_order(expected, actual):
            if isinstance(expected, dict):
                self.assertEqual(list(actual), list(expected))
                for key in expected:
                    same_order(expected[key], actual[key])
            elif isinstance(expected, list):
                self.assertEqual(len(actual), len(expected))
                for a, b in zip(expected, actual):
                    same_order(a, b)
            else:
                self.assertEqual(actual, expected)

        same_order(scene, received)
        module = server_module.ENGINE / 'web/map_infographic_v1/territory_control_adapter_v1.mjs'
        script = ("import {readFileSync} from 'node:fs';"
                  "const {compileTerritoryControlPlan}=await import(" + json.dumps(module.as_uri()) + ");"
                  "const scene=JSON.parse(readFileSync(0,'utf8'));"
                  "const plan=compileTerritoryControlPlan(scene.controlIntent);"
                  "if(plan.totalFrames!==150||plan.fps!==30)throw Error('SCENE_TIMING_CHANGED');")
        result = subprocess.run(['node', '--input-type=module', '-e', script],
                                input=json.dumps(received).encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


if __name__ == '__main__':
    unittest.main()
