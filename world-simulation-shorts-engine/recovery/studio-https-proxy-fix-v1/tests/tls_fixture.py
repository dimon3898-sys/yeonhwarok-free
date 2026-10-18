#!/usr/bin/env python3
"""TEST ONLY: reuse the frozen TLS fixture with one synthetic proxy hop.

The browser connects over real loopback TLS. Before application dispatch, the
fixture models a TLS-terminating proxy whose inner HTTP hop overwrites only
X-Forwarded-Proto. The exact external Host and X-Forwarded-Host are retained.
This is controlled fixture evidence, not an observation of gCube headers.
The inherited fixture creates a private one-time owner code and explicitly
denies every render operation; no external service or GPU is contacted.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
PARENT = (Path('/opt/world-engine-studio-https-bootstrap')
          if HERE.is_relative_to('/opt') else HERE.parent / 'studio-https-bootstrap-v1')
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(HERE))

from proxy_server import Application as ProxyApplication
import https_server as frozen_https_server


class SyntheticInnerHopApplication(ProxyApplication):
    def handler(self):
        base = super().handler()

        class Handler(base):
            def _dispatch(self):
                # These are fixture-controlled server-side transport headers,
                # not values learned from a client URL or a public endpoint.
                # Discard existing values so the synthetic hop is unambiguous.
                for name in ('X-Forwarded-Proto', 'X-Forwarded-Host'):
                    if name in self.headers:
                        del self.headers[name]
                self.headers['X-Forwarded-Proto'] = 'http'
                self.headers['X-Forwarded-Host'] = self.headers['Host']
                return super()._dispatch()

        return Handler


def main(argv=None):
    spec = importlib.util.spec_from_file_location(
        '_proxy_frozen_tls_fixture', PARENT / 'tests/tls_fixture.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    # The frozen fixture imports Application inside main. Rebind only this
    # process-local test dependency; no frozen source or runtime is modified.
    previous = frozen_https_server.Application
    frozen_https_server.Application = SyntheticInnerHopApplication
    try:
        return fixture.main(argv)
    finally:
        frozen_https_server.Application = previous


if __name__ == '__main__':
    raise SystemExit(main())
