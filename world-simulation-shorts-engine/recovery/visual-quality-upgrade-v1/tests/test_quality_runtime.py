"""Focused read-only quality harness checks reusing exact-source server validation."""
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quality_server_under_test', ROOT / 'serve_quality.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class QualityRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='quality-http-test-', dir='/workspace')
        self.dir = Path(self.temp.name)
        self.file = self.dir / 'original.mjs'
        self.file.write_bytes(b'export const original=true;\n')
        self.exact = {route: {'path': str(self.file), 'bytes': self.file.stat().st_size,
                             'sha256': hashlib.sha256(self.file.read_bytes()).hexdigest()}
                      for route in server.BASELINE}
        self.config = {'runtimeConfig': {'testOnlySoftwareProbe': False, 'quality': {'profile': 'F'},
                                        'bootstrap': {'scenePlan': {'z': 1, 'a': {'y': 2, 'b': 3}}}}}
        self.http = None

    def tearDown(self):
        if self.http:
            self.http.shutdown()
            self.http.server_close()
            self.thread.join(5)
        self.temp.cleanup()

    def start(self):
        self.http = server.make_server(self.config, self.exact)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def get(self, path, *, host=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        conn.request('GET', path, headers={'Host': host or f'127.0.0.1:{self.http.server_port}'})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_importmap_exact_material_selection_before_unchanged_boot(self):
        self.start()
        status, headers, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertLess(body.index(b'type="importmap"'), body.index(b'type="module"'))
        self.assertIn(b'"/astra/astra_material.mjs":"/quality/quality_material.mjs"', body)
        self.assertIn(b'"/modules/territory_control_gpu_adapter_v1.mjs":"/quality/quality_territory.mjs"', body)
        self.assertIn(server.IMPORT_MAP_SHA, headers['Content-Security-Policy'])

    def test_baseline_bypasses_keep_original_module_bytes(self):
        self.start()
        for route in server.BASELINE:
            self.assertEqual(self.get(route + '?baseline')[2], self.file.read_bytes())
            self.assertEqual(self.get(route + '?arbitrary=1')[0], 400)

    def test_runtime_transport_preserves_nested_canonical_property_order(self):
        self.start()
        received = json.loads(self.get('/runtime-config.json')[2])['bootstrap']['scenePlan']
        self.assertEqual(list(received), ['z', 'a'])
        self.assertEqual(list(received['a']), ['y', 'b'])

    def test_loopback_host_and_no_render_api_or_directory_mount(self):
        self.start()
        self.assertEqual(self.http.server_address[0], '127.0.0.1')
        self.assertEqual(self.get('/', host='untrusted.example')[0], 403)
        for path in ['/render', '/start', '/quality/', '/.git/config', '/etc/passwd']:
            self.assertEqual(self.get(path)[0], 404)

    def test_mutated_bound_file_fails_closed(self):
        self.start()
        self.file.write_bytes(b'mutated')
        self.assertEqual(self.get(next(iter(self.exact)))[0], 409)

    def test_software_probe_bootstrap_explicit_and_production_default_strict(self):
        self.start()
        self.assertIn(b'bootQualityRuntime()', self.get('/quality/bootstrap.mjs')[2])
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(5)
        self.http = None
        self.config['runtimeConfig']['testOnlySoftwareProbe'] = True
        self.start()
        self.assertIn(b'bootQualityRuntime({testOnlySoftwareProbe:true})', self.get('/quality/bootstrap.mjs')[2])


if __name__ == '__main__':
    unittest.main()
