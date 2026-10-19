#!/usr/bin/env python3
"""One read-only snapshot of workload 5373; no login, jobs, GPU draw or mutations."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'studio-auth-recovery-v2'))
import rest_evidence as previous

DIGEST = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
STATE_ROOT = '/var/lib/world-engine-private/engine/studio-no-backup-80s-v1'
TAG = 'studio-proxy-v1-4589328-39085567166-1'


def origin(value):
    if not isinstance(value, str): return None
    try:
        p = urlsplit(value)
        if (p.scheme != 'https' or not p.hostname or not re.fullmatch(r'[a-f0-9]{6,64}\.service\.gcube\.ai', p.hostname)
                or p.username or p.password or p.path not in ('', '/') or p.query or p.fragment
                or p.port is None or not 1 <= p.port <= 65535): return None
        return 'https://' + p.hostname + ':' + str(p.port)
    except ValueError: return None


def configuration(container):
    selected = {}
    keys = {'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST', 'WORLD_ENGINE_STUDIO_STATE_ROOT',
            'WORLD_ENGINE_RENDER_MODE', 'WORLD_ENGINE_STARTUP_MODE'}
    rows = container.get('containerEnvs')
    valid = isinstance(rows, list)
    seen = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or len(row) != 1: valid = False; continue
        key = next(iter(row))
        if not isinstance(key, str) or key in seen: valid = False; continue
        seen.add(key)
        if key in keys: selected[key] = row[key]
    image = container.get('containerImage')
    return {'environmentShapeVerified': valid,
        'configuredDigestMatchesExpected': valid and selected.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') == DIGEST,
        'stateRootMatchesPreparedPrivateRoot': valid and selected.get('WORLD_ENGINE_STUDIO_STATE_ROOT') == STATE_ROOT,
        'gpuRequiredConfigured': valid and selected.get('WORLD_ENGINE_RENDER_MODE') == 'gpu-required',
        'normalModeConfigured': valid and selected.get('WORLD_ENGINE_STARTUP_MODE') == 'normal',
        'configuredImageMatchesExpected': image in {TAG, 'dimon3898-sys/world-simulation-shorts-engine:' + TAG,
            'ghcr.io/dimon3898-sys/world-simulation-shorts-engine:' + TAG,
            'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@' + DIGEST}}


def gpu_summary(documents):
    records = []
    def visit(value, depth=0):
        if depth > 8 or len(records) >= 500: return
        if isinstance(value, list):
            for item in value[:500]: visit(item, depth + 1)
        elif isinstance(value, dict):
            if value.get('schema') == 'RTX_GPU_ADMISSION_V1': records.append(value)
            for key in ('logs', 'records', 'events', 'diagnostics', 'data', 'message', 'log'):
                if key in value: visit(value[key], depth + 1)
        elif isinstance(value, str):
            nested, oversized = previous.log_documents(value)
            if not oversized:
                for item in nested: visit(item, depth + 1)
    for document in documents: visit(document)
    admitted = [r for r in records if r.get('status') == 'GPU_VERIFIED'
        and r.get('gpuRenderingVerified') is True and r.get('testOnly') is False
        and r.get('model') == 'RTX 5090' and r.get('renderMode') == 'gpu-required'
        and r.get('gpuProfile') in {'egl', 'vulkan'}
        and r.get('verificationScope') == 'STARTUP_NATIVE_GPU_PIXEL_DRAW']
    last = admitted[-1] if admitted else {}
    return {'startupRtx5090NativeDrawEvidenceFound': bool(admitted),
        'gpuProfile': last.get('gpuProfile'), 'model': 'RTX 5090' if admitted else None,
        'observedAt': previous.collector.safe_time(last.get('observedAt')),
        'blockedAdmissionAlsoPresent': any(r.get('status') == 'BLOCKED' for r in records),
        'evidenceScope': 'EXISTING_POD_STARTUP_LOG_ONLY', 'currentGpuProbeRerun': False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def health_read(public_origin):
    with build_opener(NoRedirect()).open(public_origin + '/healthz', timeout=15) as response:
        body = response.read(20481)
        if response.status != 200 or len(body) > 20480: return {'status': 'INVALID_RESPONSE'}
        data = json.loads(body)
        return {'status': 'SUCCEEDED', 'studioServiceVerified': isinstance(data, dict) and (
            data.get('service') == 'WORLD_ENGINE_STUDIO_HTTPS_BOOTSTRAP' and data.get('serviceAlive') is True
            or data.get('service') == 'WORLD_ENGINE_STUDIO_MVP' and data.get('authenticationRequired') is True),
            'studioMode': previous.collector.closed_value(data.get('mode'), {'CONFIGURED', 'SETUP'}) if isinstance(data, dict) else None,
            'gpuProofExposedByStudioHealth': False}


def collect(environ=None, *, factory=previous.official_api, reader=health_read):
    environ = os.environ if environ is None else environ
    result = {'schema': 'WORLD_ENGINE_STUDIO_JOB_INPUT_READONLY_V1', 'workload': 5373,
        'observedAt': datetime.now(timezone.utc).isoformat(), 'status': 'BLOCKED',
        'paidOperations': 0, 'stateChanges': 0, 'renderStarted': False, 'jobCreated': False, 'renderInvoked': False,
        'jobInventoryAccessible': False, 'jobAbsenceConfirmed': False, 'gpu': gpu_summary([]), 'operations': []}
    token = environ.get('GCUBE_ACCESS_TOKEN')
    if not isinstance(token, str) or not token:
        result['blockingReason'] = 'APPROVED_REPOSITORY_SECRET_REQUIRED'; return result
    operation = 'OFFICIAL_CLIENT_INITIALIZATION'
    with tempfile.TemporaryFile(mode='w+') as private_output:
        os.fchmod(private_output.fileno(), 0o600)
        with redirect_stdout(private_output), redirect_stderr(private_output):
            try:
                api = factory(token)
                operation = 'WORKLOAD_DESCRIBE'
                workload = api.describe('5373'); raw = getattr(workload, 'raw', {})
                if not isinstance(raw, dict) or str(raw.get('ser')) != '5373':
                    result['blockingReason'] = 'WORKLOAD_ID_NOT_VERIFIED'; return result
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['workloadState'] = previous.collector.closed_value(raw.get('state'), previous.RAW_STATES, 'UNKNOWN')
                containers = raw.get('containerArray')
                container = containers[0] if isinstance(containers, list) and len(containers) == 1 and isinstance(containers[0], dict) else {}
                result['configuration'] = configuration(container)
                origins = {item for item in (origin(container.get('serviceUrl')), origin(getattr(workload, 'svc_url', None))) if item}
                public = next(iter(origins)) if len(origins) == 1 else None
                result['publicOrigin'] = public
                operation = 'WORKLOAD_PODS'; pods = api.pods('5373')
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['podCount'] = len(pods) if isinstance(pods, list) else None
                result['podStates'] = [previous.collector.closed_value(p.get('status'), previous.POD_STATES, 'UNKNOWN') for p in pods if isinstance(p, dict)] if isinstance(pods, list) else []
                if isinstance(pods, list) and len(pods) == 1 and isinstance(pods[0], dict):
                    name = pods[0].get('name')
                    if isinstance(name, str) and previous.POD_NAME.fullmatch(name) and '..' not in name:
                        operation = 'EXISTING_POD_LOGS'
                        try:
                            documents, oversized = previous.log_documents(api.logs('5373', name))
                            result['gpu'] = gpu_summary(documents)
                            result['logSizeLimitExceeded'] = oversized
                            result['firstReceivedFailure'] = previous.collector.first_error(documents)
                            result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                        except (Exception, SystemExit) as error:
                            result['operations'].append({'operation': operation, **previous.safe_exception(error)})
                            result['logsUnavailable'] = True
                if public:
                    operation = 'PUBLIC_STUDIO_HEALTH_GET'; result['health'] = reader(public)
                    result['operations'].append({'operation': operation, 'status': result['health']['status']})
                result['status'] = 'READ_ONLY_SNAPSHOT_COLLECTED'
            except (Exception, SystemExit) as error:
                safe = previous.safe_exception(error)
                result['operations'].append({'operation': operation, **safe})
                result['blockingReason'] = safe['error_category']
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream: json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')
