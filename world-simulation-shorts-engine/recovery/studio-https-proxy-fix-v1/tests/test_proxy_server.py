"""Four focused, inherited HTTP security cases with a synthetic inner HTTP hop.

These exercise actual HTTP handlers and frozen owner/CSRF implementation. The
injected controller and failed GPU admission can never produce a video.
"""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
PARENT = (Path('/opt/world-engine-studio-https-bootstrap')
          if HERE.is_relative_to('/opt') else HERE.parent / 'studio-https-bootstrap-v1')
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(HERE))


def _module(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


frozen_cases = _module('_proxy_frozen_http_cases', PARENT / 'tests/test_https_server.py')
fixture = _module('_proxy_synthetic_tls_helper', HERE / 'tests/tls_fixture.py')


class ProxyHTTPBoundaryTests(unittest.TestCase):
    # Reuse helpers and exactly four affected security scenarios, without
    # discovering or rerunning the entire old Studio/engine suite.
    request = frozen_cases.ServerTests.request
    register = frozen_cases.ServerTests.register
    login = frozen_cases.ServerTests.login
    start = frozen_cases.ServerTests.start
    tearDown = frozen_cases.ServerTests.tearDown

    def setUp(self):
        with patch.object(frozen_cases, 'Application', fixture.SyntheticInnerHopApplication):
            frozen_cases.ServerTests.setUp(self)

    def test_inner_http_hop_preserves_registration_auth_csrf_and_host_origin_rejection(self):
        frozen_cases.ServerTests.test_registration_then_original_auth_csrf_host_origin(self)

    def test_initial_setup_cannot_construct_controller_or_start_rendering(self):
        frozen_cases.ServerTests.test_setup_does_not_construct_controller_and_public_start_blocked(self)

    def test_bad_digest_keeps_web_alive_without_constructing_controller(self):
        frozen_cases.ServerTests.test_bad_digest_web_alive_but_controller_never_created(self)

    def test_registered_setup_still_requires_existing_owner_authentication(self):
        frozen_cases.ServerTests.test_registered_setup_page_requires_existing_authentication(self)


if __name__ == '__main__':
    unittest.main()
