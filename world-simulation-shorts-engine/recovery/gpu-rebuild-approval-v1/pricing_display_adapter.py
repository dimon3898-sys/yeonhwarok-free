#!/usr/bin/env python3
"""Read-only price display adapter; reuse frozen preflight GET/security path.

Official gcube-cli0.4.2 displays productName before gpuName+gpuExt.
This adapter never touches a workload, SSH, billing ledger or render path.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / 'gpu-rebuild-preflight-v1/pricing_readonly.py'
FROZEN_SHA = '9b5370362e9815b47a073fa831ed5a3bf186db2ddba4b08390d692312c75a18c'


def load_frozen():
    if hashlib.sha256(FROZEN.read_bytes()).hexdigest() != FROZEN_SHA:
        raise RuntimeError('FROZEN_PRICE_HELPER_CHANGED')
    spec = importlib.util.spec_from_file_location('_frozen_preflight_get', FROZEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def price_rows(rows, frozen):
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('PRICE_ARRAY_INVALID')
    found = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        product = frozen.safe_label(row.get('productName'))
        internal = ' '.join(frozen.safe_label(row.get(k)) or '' for k in ('gpuName', 'gpuExt'))
        matches = [label for label in (product, internal) if label and
                   '4080' in re.sub('[^A-Z0-9]', '', label.upper()) and
                   'SUPER' in re.sub('[^A-Z0-9]', '', label.upper())]
        if not matches:
            continue
        normalized = {**row, 'gpuName': matches[0], 'gpuExt': None}
        # Explicit numeric strings are real values, not SDK missing-value defaults.
        for key in ('price', 'usagePrice', 'gpu', 'vram', 'cpu', 'memory', 'disk'):
            value = normalized.get(key)
            if isinstance(value, str) and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
                normalized[key] = float(value)
        item = frozen.sanitize_rows([normalized])[0]
        item.update(displayModel=matches[0], providerGpuName=frozen.safe_label(row.get('gpuName')),
                    providerGpuExt=frozen.safe_label(row.get('gpuExt')),
                    tier=frozen.safe_label(row.get('productCode')),
                    availability=row.get('availability') if type(row.get('availability')) is bool else None,
                    matchedUsing='productName' if matches[0] == product else 'gpuName+gpuExt')
        found.append(item)
    return found


def collect():
    frozen = load_frozen()
    original_sanitizer = frozen.sanitize_rows
    # The frozen collect function calls the module-global sanitizer. Retain the
    # original for row conversion and adapt identity matching without new I/O.
    converter = type('FrozenPriceConverter', (), {
        'safe_label': staticmethod(frozen.safe_label),
        'sanitize_rows': staticmethod(original_sanitizer)})
    frozen.sanitize_rows = lambda rows: price_rows(rows, converter)
    frozen.ENDPOINT += '?serviceCode=gcube'
    value = frozen.collect()
    value.update(schema='WORLD_ENGINE_GPU_REBUILD_DISPLAY_PRICING_V2',
                 frozenHelperSHA256=FROZEN_SHA,
                 matching='official CLI productName display, with internal model fallback',
                 serviceCode='gcube', catalogueIsPaidExecutionApproval=False)
    return value


def main():
    target = Path(sys.argv[1]); target.parent.mkdir(parents=True, exist_ok=True)
    value = collect()
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': value['status'], 'paidOperations': 0, 'workloadMutations': 0}))


if __name__ == '__main__':
    main()
