"""Gated natural-language/data jobs through the preserved authenticated Studio.

The old runner supplies the real mobile HTTP client, explicit consent/claim,
disconnect/reconnect check, serial polling and exclusive public-copy behavior.
Only the new compiler/capture dispatch and versioned gate contract are selected.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


service = load('_up2_runner_studio_service', HERE / 'studio_adapter.py')
existing = load('_up2_preserved_mobile_runner', HERE.parent / 'universal-data-pipeline-v1/run_studio_demos.py')
existing.HERE, existing.REPO, existing.service = HERE, REPO, service


def require_gates(file, expected):
    file = Path(file)
    if file.is_symlink() or not file.is_file():
        raise RuntimeError('UP2_A_E_GATE_FILE_REQUIRED')
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError('UP2_A_E_GATE_HASH_MISMATCH')
    data = json.loads(raw)
    protection = data.get('protection', {})
    if (data.get('schema') != 'WORLD_ENGINE_UP2_GATES_V1'
            or data.get('baselineCommit') != 'b0d013832ee38571f9d3dfe685ce63f7083ba90f'
            or protection.get('originalFiles') != 307 or protection.get('status') != 'PASS'
            or any(data.get('phase' + name, {}).get('status') != 'PASS' for name in 'ABCDE')
            or any(data.get(name) is not False for name in ('paidGpuExecuted', 'paidApiUsed', 'deploymentExecuted'))
            or data.get('historicalProduction') != 'BLOCKED'):
        raise RuntimeError('UP2_A_E_REQUIRED_GATES_NOT_PASSED')
    return data


def prepare_studio_request(file, output):
    file = Path(file)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 8 * 1024**2:
        raise RuntimeError('UP2_SAFE_INPUT_FILE_REQUIRED')
    raw = file.read_bytes()
    value = json.loads(raw)
    if value.get('schema') == 'WORLD_ENGINE_PRESENTATION_PROMPT_V2':
        # The complete timeline is explicitly selected. No successful Scene is
        # silently chosen in place of an unavailable scene or missing fact.
        value = {'schema': service.REQUEST_SCHEMA, 'prompt': value, 'sceneId': service.TIMELINE_ID}
    elif value.get('schema') != service.REQUEST_SCHEMA:
        raise RuntimeError('UP2_PRESENTATION_PROMPT_REQUIRED')
    with Path(output).open('xb') as target:
        target.write(service.canonical(value))
    Path(output).chmod(0o600)
    return {'originalInputSHA256': hashlib.sha256(raw).hexdigest(),
        'originalInputBytes': len(raw), 'sceneSelection': value['sceneId']}


def run(args):
    require_gates(args.gate_file, args.expected_gate_sha256)
    private = args.private_root
    if (not private.is_absolute() or private.is_relative_to(REPO)
            or any(p.is_symlink() for p in (private, *private.parents))
            or len(args.request) != len(args.name) or len(args.request) < 3
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.attempt)
            or len(set(args.name)) != len(args.name)):
        raise RuntimeError('UP2_FRESH_PRIVATE_ROOT_AND_THREE_DISTINCT_PROMPTS_REQUIRED')
    # Exclusive roots and report names preserve previous successes and failures.
    private.mkdir(mode=0o700, exist_ok=False)
    requests = private / 'inputs'
    requests.mkdir(mode=0o700)
    results = []
    for index, (file, name) in enumerate(zip(args.request, args.name)):
        wrapper = requests / (str(index) + '.json')
        provenance = prepare_studio_request(file, wrapper)
        result = existing.run_one(private / ('case-' + str(index + 1)), wrapper, name,
            evidence_registry=args.evidence_registry, registry_pin=args.expected_registry_sha256, attempt=args.attempt)
        results.append({**result, **provenance})
    report = {'schema': 'WORLD_ENGINE_PRESENTATION_REAL_STUDIO_DEMOS_V2', 'jobs': results,
        'gateSHA256': args.expected_gate_sha256, 'softwareOnly': True,
        'nvidiaVerified': False, 'paidExecuted': False, 'deploymentExecuted': False,
        'qualityStatus': 'QUALITY_REVIEW_REQUIRED', 'historicalG3': 'BLOCKED',
        'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE'}
    with (HERE / 'reports' / ('STUDIO_DEMOS_' + args.attempt + '.json')).open('x') as target:
        json.dump(report, target, indent=2); target.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--attempt', default='attempt-01')
    parser.add_argument('--gate-file', type=Path, required=True)
    parser.add_argument('--expected-gate-sha256', required=True)
    parser.add_argument('--request', type=Path, action='append', required=True)
    parser.add_argument('--name', action='append', required=True)
    parser.add_argument('--evidence-registry', type=Path)
    parser.add_argument('--expected-registry-sha256')
    print(json.dumps(run(parser.parse_args()), indent=2))
