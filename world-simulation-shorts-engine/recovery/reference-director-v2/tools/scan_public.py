"""Reuse the preserved bounded scanner against this new namespace only."""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
SOURCE = REPO / 'world-simulation-shorts-engine/recovery/reference-director-v1/tools/scan_public.py'


def scan(output):
    if not re.fullmatch(r'[A-Z0-9_]+\.json', output):
        raise RuntimeError('R2_SAFE_SCAN_REPORT_NAME_REQUIRED')
    spec = importlib.util.spec_from_file_location('_rd2_preserved_public_scanner', SOURCE)
    reused = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reused)
    reused.ROOT = HERE
    result = reused.scan()
    result.update(schema='WORLD_ENGINE_REFERENCE_DIRECTOR_PUBLIC_SECRET_PATTERN_SCAN_V2',
        originalScannerSource=SOURCE.relative_to(REPO).as_posix(),
        namespace=HERE.relative_to(REPO).as_posix(),
        scope='Explicit credential patterns in the new namespace only; not proof that every possible secret format is detectable',
        paidGpuOrApiUsed=False)
    with (HERE / 'reports' / output).open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'fileSnapshot'}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='SECRET_SCAN.json')
    args = parser.parse_args()
    raise SystemExit(scan(args.output))
