"""Explicit bounded location-placement opt-in; no source or role suppression."""
from copy import deepcopy
import hashlib
import json
import math


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_location_policy(plan, policy=None):
    layout = plan.get('layout') if isinstance(plan, dict) else None
    if not isinstance(layout, dict):
        raise ValueError('LOCATION_PLACEMENT_LAYOUT_REQUIRED')
    if policy is None:
        policy = layout.get('locationPlacement')
    if policy is None:
        return None
    if (not isinstance(policy, dict)
            or set(policy) != {'schema', 'mode', 'maxGap', 'step'}
            or policy.get('schema') != 'WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1'
            or policy.get('mode') != 'BOUNDED_GAP_SEARCH'):
        raise ValueError('LOCATION_PLACEMENT_POLICY_INVALID')
    canonical_size = layout.get('canonical')
    if (not isinstance(canonical_size, list) or len(canonical_size) != 2
            or any(not _number(v) or v <= 0 for v in canonical_size)):
        raise ValueError('LOCATION_PLACEMENT_CANONICAL_REQUIRED')
    base_gap = layout.get('measured', {}).get('location', {}).get('gap')
    if not _number(base_gap) or base_gap < 0:
        raise ValueError('LOCATION_PLACEMENT_BASE_GAP_INVALID')
    max_gap, step = policy['maxGap'], policy['step']
    if (not _number(max_gap) or not base_gap <= max_gap <= .2 * min(canonical_size)
            or type(step) is not int or not 4 <= step <= 32):
        raise ValueError('LOCATION_PLACEMENT_POLICY_BOUNDS_INVALID')
    if plan.get('scale', {}).get('information', {}).get('location') is False:
        raise ValueError('LOCATION_PLACEMENT_ACTIVE_LOCATION_REQUIRED')
    return deepcopy(policy)


def apply_location_policy(native_plan, policy):
    qualified = validate_location_policy(native_plan, policy)
    if qualified is None:
        raise ValueError('LOCATION_PLACEMENT_EXPLICIT_POLICY_REQUIRED')
    before = deepcopy(native_plan)
    after = deepcopy(native_plan)
    previous = after['layout'].get('locationPlacement')
    if previous is not None and previous != qualified:
        raise ValueError('LOCATION_PLACEMENT_EXISTING_POLICY_CONFLICT')
    after['layout']['locationPlacement'] = qualified
    receipt = {
        'schema': 'WORLD_ENGINE_LAYOUT_ACTIVATION_RECEIPT_V1',
        'beforeNativePlanSHA256': hashlib.sha256(canonical(before)).hexdigest(),
        'afterNativePlanSHA256': hashlib.sha256(canonical(after)).hexdigest(),
        'onlyAddedPath': 'layout.locationPlacement',
        'activeLocationPreserved': True,
        'sourceGeometryChanged': False,
        'cameraChanged': False,
        'fontOrClearanceChanged': False,
        'policy': qualified,
    }
    return after, receipt
