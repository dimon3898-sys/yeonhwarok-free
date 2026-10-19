#!/usr/bin/env python3
"""Read existing workload settings and one catalogue; never change policy or run work."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'studio-auth-recovery-v2'))
import rest_evidence as previous

DIGEST = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
PREFIX = 'WORLD_ENGINE_STUDIO_'
KEYS = {'validUntil', 'maxWallSeconds', 'maxRetries', 'maxCostAmount', 'currency', 'gpuHourlyRate'}


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10**12 else None


def amount(value):
    if type(value) not in (int, float, str) or not re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,8})?', str(value)):
        raise ValueError()
    if Decimal(str(value)) <= 0:
        raise ValueError()
    return value


def unique(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError()
        output[key] = value
    return output


def policy(raw, now):
    try:
        if not isinstance(raw, str) or len(raw) > 65536:
            raise ValueError()
        value = json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (not isinstance(value, dict) or set(value) - {'schema'} != KEYS
                or value.get('schema', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1') != 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1'
                or type(value['maxWallSeconds']) is not int or not 1 <= value['maxWallSeconds'] <= 86400
                or type(value['maxRetries']) is not int or not 0 <= value['maxRetries'] <= 2
                or value['currency'] not in {'KRW', 'USD'} or previous.collector.safe_time(value['validUntil']) is None):
            raise ValueError()
        rate, cap = amount(value['gpuHourlyRate']), amount(value['maxCostAmount'])
        expiry = datetime.fromisoformat(value['validUntil'].replace('Z', '+00:00'))
        return {'status': 'TYPED_ENVIRONMENT_POLICY_READ', 'policy': {key: value[key] for key in sorted(KEYS)},
            'expired': expiry <= now, 'validityRemainingSeconds': max(0, int((expiry - now).total_seconds())),
            'configuredTimeFitsCostCap': Decimal(str(rate)) * value['maxWallSeconds'] / 3600 <= Decimal(str(cap)),
            'fourHoursFitsCostCap': Decimal(str(rate)) * 4 <= Decimal(str(cap)),
            'privatePolicyFileRead': False, 'effectiveStudioPolicyEqualityVerified': False}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {'status': 'MISSING_OR_INVALID_POLICY', 'privatePolicyFileRead': False}


def configuration(container, now):
    rows, values, seen = container.get('containerEnvs'), {}, set()
    valid = isinstance(rows, list)
    wanted = {PREFIX + 'OPERATOR_POLICY_JSON', PREFIX + 'STATE_ROOT', 'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or len(row) != 1:
            valid = False; continue
        key = next(iter(row))
        if not isinstance(key, str) or key in seen:
            valid = False; continue
        seen.add(key)
        if key in wanted:
            values[key] = row[key]
    result = {'environmentShapeVerified': valid, 'privatePolicyFileRead': False}
    if not valid:
        return result
    result['operatorPolicy'] = policy(values.get(PREFIX + 'OPERATOR_POLICY_JSON'), now)
    result['configuredDigestMatchesExpected'] = values.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') == DIGEST
    root = values.get(PREFIX + 'STATE_ROOT')
    result['stateRoot'] = root if isinstance(root, str) and re.fullmatch(
        r'/var/lib/world-engine-private/engine/[A-Za-z0-9_-]{1,96}', root) else None
    result['stateRootConfigured'] = PREFIX + 'STATE_ROOT' in values
    return result


def pricing_summary(spec, raw, indexed, matcher):
    _, item = matcher(spec, indexed)
    result = {'specModelIsRtx5090': spec.get('gpu') == 'RTX5090' or spec.get('gpu') == 'RTX 5090',
        'vramGiB': number(spec.get('vram')), 'gpuSpecPrice': number(spec.get('price')),
        'gpuSpecMaxPrice': number(spec.get('maxPrice')), 'workloadMaxPrice': number(raw.get('maxPrice')),
        'catalogueMatched': item is not None, 'actualBilledHourlyRateVerified': False,
        'fourHourOwnerApprovalExists': False}
    if item is not None:
        result['catalogue'] = {'price': number(item.price), 'usagePrice': number(item.usage_price),
            'currency': item.currency_unit if item.currency_unit in {'KRW', 'USD'} else None,
            'product': 'RTX 5090' if item.product_name == 'RTX 5090' else None,
            'tier': previous.collector.closed_value(item.product_code, {'tier1', 'tier2', 'tier3'}),
            'availableNow': item.availability is True}
    return result


def collect(environ=None, *, factory=previous.official_api, matcher=None, now=None):
    environ = os.environ if environ is None else environ
    now = datetime.now(timezone.utc) if now is None else now
    result = {'schema': 'WORLD_ENGINE_STUDIO_POLICY_240M_READONLY_V1', 'workload': 5373,
        'observedAt': now.isoformat(), 'status': 'BLOCKED', 'operations': [], 'paidOperations': 0,
        'stateChanges': 0, 'jobCreated': False, 'renderInvoked': False, 'gpuProbeRun': False,
        'rawResponsesPublished': False, 'credentialValuesPublished': False}
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
                raw = getattr(api.describe('5373'), 'raw', {})
                if not isinstance(raw, dict) or str(raw.get('ser')) != '5373':
                    result['blockingReason'] = 'WORKLOAD_ID_NOT_VERIFIED'; return result
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['workloadState'] = previous.collector.closed_value(raw.get('state'), previous.RAW_STATES)
                containers, specs = raw.get('containerArray'), raw.get('gpuSpecArray')
                if isinstance(containers, list) and len(containers) == 1 and isinstance(containers[0], dict):
                    result['configuration'] = configuration(containers[0], now)
                operation = 'CURRENT_GPU_PRICING_CATALOGUE_GET'
                indexed = api.get_indexed_gpu_pricings(service_code='gcube')
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                if isinstance(specs, list) and len(specs) == 1 and isinstance(specs[0], dict):
                    if matcher is None:
                        from gcube_cli.api.workload import match_gpu_pricing
                        matcher = match_gpu_pricing
                    result['gpuPricing'] = pricing_summary(specs[0], raw, indexed, matcher)
                result['status'] = 'READ_ONLY_SETTINGS_AND_CATALOGUE_COLLECTED'
            except (Exception, SystemExit) as error:
                safe = previous.safe_exception(error)
                result['operations'].append({'operation': operation, **safe})
                result['blockingReason'] = safe['error_category']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')
