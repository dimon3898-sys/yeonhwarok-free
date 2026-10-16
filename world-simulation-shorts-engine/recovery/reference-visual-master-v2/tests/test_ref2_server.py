"""Focused reference harness/source-authentication checks; original helpers stay immutable."""
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reference_server_under_test', ROOT / 'serve_ref2.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class ReferenceServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='reference-http-test-', dir='/workspace')
        self.directory = Path(self.temp.name)
        self.file = self.directory / 'original.mjs'
        self.file.write_bytes(b'export const original=true;\n')
        self.record = {'path': str(self.file), 'bytes': self.file.stat().st_size,
                       'sha256': hashlib.sha256(self.file.read_bytes()).hexdigest()}
        self.exact = {route: dict(self.record) for route in server.BASELINE}
        self.exact['/reference/ref2_adapter.mjs'] = dict(self.record)
        saved = ROOT.parents[1] / 'recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'
        self.scene = json.loads(saved.read_text())
        self.config = {'schema': 'ASTRA_RUNTIME_SERVER_CONFIG_V1', 'bundleRoot': str(self.directory),
                       'bindings': [{'url': route, **record} for route, record in self.exact.items()],
                       'runtimeConfig': {'testOnlySoftwareProbe': False, 'referenceV2': {'variant': 'F'},
                                         'bootstrap': {'scenePlan': self.scene}}}
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

    def request(self, route, *, host=None, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        connection.request(method, route, headers={'Host': host or f'127.0.0.1:{self.http.server_port}'})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_six_direct_import_edges_select_new_factories_before_original_boot(self):
        self.start()
        status, headers, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertLess(body.index(b'type="importmap"'), body.index(b'type="module"'))
        imports = json.loads(server.IMPORT_MAP)['imports']
        self.assertEqual(len(imports), 6)
        for source in ('/modules/reference_terrain_material_v4.mjs', '/astra/astra_material.mjs', '/quality/quality_material.mjs'):
            self.assertEqual(imports[source], '/reference/reference_source_material.mjs')
        for source in ('/modules/territory_control_gpu_adapter_v1.mjs', '/quality/quality_territory.mjs'):
            self.assertEqual(imports[source], '/reference/gain_territory.mjs')
        self.assertEqual(imports['/modules/reference_control_frontier_light_v3.mjs'], '/reference/frontier_ref2.mjs')
        self.assertIn(server.IMPORT_MAP_SHA, headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-eval', headers['Content-Security-Policy'])

    def test_baseline_query_bypass_returns_original_exact_bytes_without_response_rewriting(self):
        self.start()
        self.assertEqual(len(server.BASELINE), 6)
        for route in server.BASELINE:
            self.assertEqual(self.request(route + '?baseline')[2], self.file.read_bytes())
            self.assertEqual(self.request(route + '?unknown')[0], 400)
        self.assertEqual(self.request('/reference/ref2_adapter.mjs?baseline')[0], 400)

    def test_actual_saved_scene_and_control_intent_canonical_property_order_survive_transport(self):
        self.start()
        received = json.loads(self.request('/runtime-config.json')[2])['bootstrap']['scenePlan']
        self.assertEqual(list(received), list(self.scene))
        self.assertEqual(list(received['controlIntent']), list(self.scene['controlIntent']))
        self.assertEqual(json.dumps(received, separators=(',', ':')), json.dumps(self.scene, separators=(',', ':')))

    def test_loopback_only_host_readonly_and_exact_allowlist_without_render_api(self):
        self.start()
        self.assertEqual(self.http.server_address[0], '127.0.0.1')
        self.assertEqual(self.request('/', host='untrusted.example')[0], 403)
        for route in ('/start', '/render', '/reference/', '/.git/config', '/etc/passwd'):
            self.assertEqual(self.request(route)[0], 404)
        for route in ('/%2e%2e/etc/passwd', '/reference/../ref2_adapter.mjs', '/reference\\outside', '/reference/%00'):
            self.assertEqual(self.request(route)[0], 400)
        self.assertEqual(self.request('/render', method='POST')[0], 501)
        status, headers, body = self.request('/reference/ref2_adapter.mjs', method='HEAD')
        self.assertEqual(status, 200)
        self.assertEqual(body, b'')
        self.assertEqual(int(headers['Content-Length']), self.file.stat().st_size)

    def test_changed_or_symlinked_source_fails_closed_instead_of_serving_unbound_code(self):
        self.start()
        self.file.write_bytes(b'mutated')
        self.assertEqual(self.request('/reference/ref2_adapter.mjs')[0], 409)
        self.file.unlink()
        self.file.symlink_to(ROOT / 'ref2_adapter.mjs')
        self.assertEqual(self.request('/reference/ref2_adapter.mjs')[0], 409)

    def test_original_config_validator_binds_config_sha_source_bytes_and_safe_roots(self):
        file = self.directory / 'CONFIG.json'
        raw = json.dumps(self.config).encode()
        file.write_bytes(raw)
        config, exact = server.parent.load_config(file, hashlib.sha256(raw).hexdigest())
        self.assertEqual(config, self.config)
        self.assertEqual({route: {key: value for key, value in record.items() if key != 'url'}
                          for route, record in exact.items()}, self.exact)
        with self.assertRaisesRegex(ValueError, 'CONFIG_SHA_MISMATCH'):
            server.parent.load_config(file, '0' * 64)
        self.file.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'BOUND_SOURCE_MISMATCH'):
            server.parent.load_config(file, hashlib.sha256(raw).hexdigest())

    def test_software_bootstrap_requires_explicit_config_while_production_has_no_override(self):
        self.start()
        original = self.request('/reference/bootstrap.mjs')[2]
        self.assertIn(b'bootReferenceRuntime()', original)
        self.assertNotIn(b'testOnlySoftwareProbe:true', original)
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(5)
        self.http = None
        self.config['runtimeConfig']['testOnlySoftwareProbe'] = True
        self.start()
        probe = self.request('/reference/bootstrap.mjs')[2]
        self.assertIn(b'bootReferenceRuntime({testOnlySoftwareProbe:true})', probe)
        self.assertIn(b'window.astraBoot=window.referenceV2Boot', probe)


if __name__ == '__main__':
    unittest.main()
