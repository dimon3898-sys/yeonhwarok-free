#!/usr/bin/env python3
"""Additive loopback harness using the immutable ASTRA safe server implementation.

Only exact source bytes are served. No network-facing job or render API exists.
The original server is loaded into an independent module instance; no old file
or prior module's process-global configuration is changed.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
_original = ROOT.parent / 'astra-gpu-activation-v1/serve_astra.py'
spec = importlib.util.spec_from_file_location('_long_video_preserved_astra_loopback', _original)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
IMPORTS = {'imports': {
    '/modules/reference_terrain_material_v4.mjs': '/reference/reference_source_material.mjs',
    '/astra/astra_material.mjs': '/reference/reference_source_material.mjs',
    '/quality/quality_material.mjs': '/reference/reference_source_material.mjs',
}}
IMPORT_MAP = json.dumps(IMPORTS, separators=(',', ':'))
IMPORT_MAP_SHA = base64.b64encode(hashlib.sha256(IMPORT_MAP.encode()).digest()).decode()
INDEX = ('<!doctype html><html><head><meta charset="utf-8"><link rel="icon" href="data:,">'
         '<meta name="viewport" content="width=device-width"><style>html,body{margin:0;background:#000}canvas{display:block}</style>'
         '<script type="importmap">' + IMPORT_MAP + '</script>'
         '<script type="module" src="/astra/bootstrap.mjs"></script></head><body></body></html>').encode()
BOOTSTRAP = b"import {bootLongRuntime} from '/universal/long_adapter.mjs';window.longVideoBoot=bootLongRuntime();\n"
SOFTWARE_BOOTSTRAP = b"import {bootLongRuntime} from '/universal/long_adapter.mjs';window.longVideoBoot=bootLongRuntime({testOnlySoftwareProbe:true});\n"
BASELINE = frozenset(IMPORTS['imports'])
original_route_path = base.route_path


def route_path(value):
    parsed = urlsplit(value)
    if parsed.query and not (parsed.path in BASELINE and parsed.query == 'baseline'):
        raise ValueError('UNEXPECTED_QUERY')
    return original_route_path(parsed._replace(query='').geturl())


# Reuse original host check, SHA-safe sources, CSP, GET/HEAD-only methods and
# bounded config validator. These settings live in this isolated module only.
base.route_path = route_path
base.INDEX, base.IMPORT_MAP_SHA = INDEX, IMPORT_MAP_SHA
base.BOOTSTRAP, base.SOFTWARE_BOOTSTRAP = BOOTSTRAP, SOFTWARE_BOOTSTRAP
make_server, load_config = base.make_server, base.load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--expected-config-sha256', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be in 0..65535')
    config, exact = load_config(args.config, args.expected_config_sha256)
    universal = config.get('runtimeConfig', {}).get('universalVideo', {})
    if universal.get('schema') != 'WORLD_ENGINE_UNIVERSAL_RUNTIME_V2':
        raise ValueError('EXPLICIT_UNIVERSAL_RUNTIME_REQUIRED')
    with make_server(config, exact, port=args.port) as server:
        print(json.dumps({'event': 'READY', 'url': f'http://127.0.0.1:{server.server_port}', 'closureFiles': len(exact)}), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'status': 'BLOCKED', 'errorCode': 'LONG_LOOPBACK_CONFIGURATION_FAILED'}))
        raise SystemExit(2)
