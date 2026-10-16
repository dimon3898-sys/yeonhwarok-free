"""Focused loopback tests; old server safety functions are actually reused."""
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('isolated_long_test_server', ROOT / 'serve_long.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class LongLoopbackTests(unittest.TestCase):
    def test_only_source_factory_aliases_and_bound_queries(self):
        self.assertEqual(set(server.IMPORTS['imports']), {
            '/modules/reference_terrain_material_v4.mjs', '/astra/astra_material.mjs', '/quality/quality_material.mjs'})
        self.assertEqual(server.route_path('/quality/quality_material.mjs?baseline'), '/quality/quality_material.mjs')
        for route in ['/universal/long_adapter.mjs?baseline', '/a?access_token=private', '/a/../b', '/%2e%2e/private', 'https://other/']:
            with self.assertRaises(ValueError):
                server.route_path(route)
        self.assertIn(b'bootLongRuntime()', server.BOOTSTRAP)
        self.assertNotIn(b'bootReferenceRuntime', server.BOOTSTRAP)

    def test_actual_safe_loopback_get_csp_sha_and_no_post(self):
        record = ROOT / 'long_adapter.mjs'
        # Any own regular module can stand in as an HTTP-bound TEST source.
        if not record.is_file():
            record = ROOT / 'long_runtime.mjs'
        raw = record.read_bytes()
        config = {'runtimeConfig': {'universalVideo': {'schema': 'WORLD_ENGINE_UNIVERSAL_RUNTIME_V2'}}}
        exact = {'/universal/test.mjs': {'path': str(record), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}}
        http_server = server.make_server(config, exact)
        worker = threading.Thread(target=http_server.serve_forever, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection('127.0.0.1', http_server.server_port, timeout=2)
        try:
            connection.request('GET', '/astra/bootstrap.mjs')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), server.BOOTSTRAP)
            self.assertIn(server.IMPORT_MAP_SHA, response.getheader('Content-Security-Policy'))
            connection.request('GET', '/universal/test.mjs')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), raw)
            connection.request('POST', '/universal/render', body='{}')
            response = connection.getresponse()
            self.assertEqual(response.status, 501)
            response.read()
            connection.request('GET', '/', headers={'Host': 'evil.invalid'})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
        finally:
            connection.close()
            http_server.shutdown()
            http_server.server_close()
            worker.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
