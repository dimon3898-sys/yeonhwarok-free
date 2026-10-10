"""Additive v024 release gates over the exact published v023 image.

No release is admitted without the reviewed preview receipt and frozen source
pins. All 1,200 existing tests and assets remain mandatory. CPU previews and
authenticated plan approval never initialize a GPU or enqueue a render job.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import http.client
import importlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
if __name__ == '__main__':
    canonical = 'deployment.gcube.terrain_preflight'
    sys.modules[canonical] = sys.modules[__name__]
    setattr(importlib.import_module('deployment.gcube'), 'terrain_preflight', sys.modules[__name__])
MANIFEST = APP / 'deployment/gcube/terrain_release_manifest.json'
PARENT_MANIFEST = APP / 'deployment/gcube/bold_release_manifest.json'
SELECTION_MANIFEST = APP / 'deployment/gcube/selection_release_manifest.json'
INFOGRAPHIC_MANIFEST = APP / 'deployment/gcube/infographic_release_manifest.json'
PARENT_MANIFEST_SHA256 = '2af4e5c8c9c8899d020352aa69eee393f6c9a33ae7cc3a14873a2275fa47da7f'
PARENT_DIGEST = 'sha256:60108bcc6f5c097eafb5003d78050ec97996702eda8458ec85a2adb208551bb6'
TAG_PREFIX = 'gcube-v024-visual-target-'
PROFILE = 'VISUAL_TARGET_MAP_V024'
AUTHORIZED_PARENT_DELTAS = {'web/app.js', 'deployment/mobile_server.py', 'engine/public_infographic_selection.py'}
REQUIRED_NEW_RUNTIME = {
    'deployment/gcube/terrain_preflight.py', 'engine/terrain_infographic.py',
    'web/terrain_infographic_adapter.js', 'web/render_terrain_infographic_earth.html',
    'data/infographic/v024/terrain_profile.json', 'web/infographic/v024/terrain_profile.json',
    'tools/terrain_canvas_preview_v024.mjs', 'tools/terrain_pixel_metrics_v024.mjs',
}
REQUIRED_AUDITED_ASSETS = {
    'world-simulation-shorts-engine/web/terrain_infographic_adapter.js',
    'world-simulation-shorts-engine/web/render_terrain_infographic_earth.html',
}
REQUIRED_PREVIEW_SOURCES = {
    'web/terrain_infographic_adapter.js',
    'data/infographic/v024/terrain_profile.json',
    'web/infographic/v024/terrain_profile.json',
    'tools/terrain_canvas_preview_v024.mjs',
    'tools/terrain_pixel_metrics_v024.mjs',
}
REQUIRED_PREVIEW_CASES = [
    'WIDE', 'SUEZ_REGIONAL', 'SUEZ_EVENT_VIEW',
    'SINGAPORE_REGIONAL', 'SINGAPORE_EVENT_VIEW',
    'SUEZ_DARK_STRESS', 'SUEZ_BRIGHT_STRESS',
]
LEGACY_ENV = {'WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE': 'OFF'}
_real_asset_audit = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def physical_bytes(path):
    """Read immutable parent bytes, independently of scoped receipt views."""
    with Path(path).open('rb') as stream:
        return stream.read()


def record(path, root):
    path = Path(path)
    return dict(path=str(path.relative_to(root)), size=path.stat().st_size, sha256=sha(path))


def verify_records(rows, root):
    from deployment.gcube.bold_preflight import verify_records as verify
    verify(rows, root)


def parent_value():
    raw = physical_bytes(PARENT_MANIFEST)
    assert hashlib.sha256(raw).hexdigest() == PARENT_MANIFEST_SHA256, 'TERRAIN_PARENT_MANIFEST_CHANGED'
    value = json.loads(raw)
    assert value['version'] == 'v023-bold' and value['unique_tests'] == 1200, 'TERRAIN_PARENT_INVALID'
    return value


def notice(title, value):
    # Keep public numeric proofs below GitHub's 4096-character annotation limit.
    body = json.dumps(value, sort_keys=True, separators=(',', ':'))
    assert len(body) <= 3500, 'TERRAIN_PUBLIC_NOTICE_TOO_LARGE'
    print('::notice title=' + title + '::' + body, flush=True)


def admit_parent_sources(deltas):
    previous = parent_value()
    assert {row['path'] for row in deltas} <= AUTHORIZED_PARENT_DELTAS, 'TERRAIN_PARENT_SCOPE_CHANGED'
    assert len({row['path'] for row in deltas}) == len(deltas), 'TERRAIN_PARENT_DELTA_DUPLICATED'
    originals = {row['path']: row for row in previous['parent_deltas']}
    assert set(originals) == AUTHORIZED_PARENT_DELTAS, 'TERRAIN_PARENT_SELECTOR_INVENTORY_CHANGED'
    replacements = {row['path']: row for row in deltas}
    verify_records(sorted([replacements.get(path, row) for path, row in originals.items()], key=lambda row: row['path']), APP)
    verify_records(previous['runtime_records'], APP)
    selection = json.loads(physical_bytes(SELECTION_MANIFEST))
    protected = json.loads(physical_bytes(INFOGRAPHIC_MANIFEST))
    assert sha(SELECTION_MANIFEST) == previous['parent_manifest_sha256'], 'TERRAIN_SELECTION_MANIFEST_CHANGED'
    assert sha(INFOGRAPHIC_MANIFEST) == previous['infographic_manifest_sha256'], 'TERRAIN_GIS_MANIFEST_CHANGED'
    verify_records([row for row in selection['runtime_records'] if row['path'] not in AUTHORIZED_PARENT_DELTAS], APP)
    verify_records(protected['runtime_records'], APP)
    verify_records(protected['frozen_parent_records'], APP)
    assert len(protected['runtime_records']) + len(protected['frozen_parent_records']) == 67, 'TERRAIN_PROTECTED_SOURCE_INVENTORY_CHANGED'
    return previous, selection, protected


def validate_preview_receipt(receipt, runtime_records):
    assert receipt.get('status') == 'APPROVED' and receipt.get('passed') is True, 'TERRAIN_APPROVED_PREVIEW_REQUIRED'
    assert receipt.get('physical_gpu') == 'NOT_RUN', 'TERRAIN_PREVIEW_SCOPE_INVALID'
    paths = receipt.get('source_records')
    assert isinstance(paths, list) and paths, 'TERRAIN_PREVIEW_SOURCE_PINS_MISSING'
    verify_records(paths, APP)
    runtime = {row['path']: row for row in runtime_records}
    assert all(runtime.get(row['path']) == row for row in paths), 'TERRAIN_PREVIEW_SOURCE_NOT_RELEASED'
    checks = receipt.get('mandatory_pixel_checks')
    assert isinstance(checks, list) and checks and checks == sorted(set(checks)), 'TERRAIN_PREVIEW_PIXEL_INVENTORY_MISSING'
    cases = receipt.get('case_names')
    assert cases == REQUIRED_PREVIEW_CASES, 'TERRAIN_PREVIEW_CASE_INVENTORY_MISSING'
    assert {row['path'] for row in paths} >= REQUIRED_PREVIEW_SOURCES, 'TERRAIN_PREVIEW_REQUIRED_SOURCE_UNPINNED'
    return receipt


def verify_sources(*, checkout=False):
    value = json.loads(MANIFEST.read_bytes())
    assert value.get('status') == 'FROZEN' and value.get('version') == 'v024-terrain', 'TERRAIN_MANIFEST_NOT_FROZEN'
    assert value['parent_digest'] == PARENT_DIGEST and value['tag_prefix'] == TAG_PREFIX, 'TERRAIN_PARENT_IMAGE_CHANGED'
    assert value['parent_manifest_sha256'] == PARENT_MANIFEST_SHA256, 'TERRAIN_PARENT_PIN_CHANGED'
    previous, selection, protected = admit_parent_sources(value['parent_deltas'])
    old_core = sorted(previous['inherited_core_ids'] + previous['new_ids'])
    assert len(old_core) == 963 and value['inherited_core_ids'] == old_core, 'TERRAIN_PARENT_CORE_IDS_CHANGED'
    assert value['proxy_ids'] == previous['proxy_ids'] and len(value['proxy_ids']) == 206, 'TERRAIN_PROXY_IDS_CHANGED'
    assert value['diagnostic_ids'] == previous['diagnostic_ids'] and len(value['diagnostic_ids']) == 31, 'TERRAIN_DIAGNOSTIC_IDS_CHANGED'
    added = value['new_ids']
    assert added and added == sorted(set(added)), 'TERRAIN_NEW_TEST_IDS_INVALID'
    assert not set(added) & set(old_core + value['proxy_ids'] + value['diagnostic_ids']), 'TERRAIN_TEST_IDS_OVERLAP'
    assert value['new_ids_sha256'] == hashlib.sha256(('\n'.join(added) + '\n').encode()).hexdigest(), 'TERRAIN_NEW_TEST_IDS_CHANGED'
    assert value['unique_tests'] == 1200 + len(added), 'TERRAIN_TEST_TOTAL_INVALID'
    assert {row['path'] for row in value['runtime_records']} >= REQUIRED_NEW_RUNTIME, 'TERRAIN_REQUIRED_RUNTIME_MISSING'
    protected_names = {row['path'] for row in previous['runtime_records'] + selection['runtime_records']
                       + protected['runtime_records'] + protected['frozen_parent_records']}
    assert not {row['path'] for row in value['runtime_records']} & (AUTHORIZED_PARENT_DELTAS | protected_names), 'TERRAIN_PARENT_RUNTIME_REPLACED'
    verify_records(value['runtime_records'], APP)
    validate_preview_receipt(value['approved_preview'], value['runtime_records'])
    if checkout:
        verify_records(protected['checkout_records'], ROOT)
        verify_records(selection['checkout_records'], ROOT)
        verify_records(previous['checkout_records'], ROOT)
        verify_records(value['checkout_records'], ROOT)
    return value, dict(passed=True, exact_published_parent=PARENT_DIGEST, original_unique_tests=1200,
                      additional_tests=len(added), unique_tests=value['unique_tests'], protected_runtime_files=67,
                      approved_preview=True, manifest_sha256=sha(MANIFEST), physical_gpu='NOT_RUN')


def translated_parent_manifest(value):
    projected = parent_value()
    replacements = {row['path']: row for row in value['parent_deltas']}
    projected['parent_deltas'] = [deepcopy(replacements.get(row['path'], row)) for row in projected['parent_deltas']]
    return projected


def actual_assets(value):
    global _real_asset_audit
    from deployment.gcube import asset_audit
    if _real_asset_audit is None:
        assert asset_audit.audit_assets.__module__ == 'deployment.gcube.asset_audit', 'TERRAIN_REAL_ASSET_AUDITOR_UNAVAILABLE'
        _real_asset_audit = asset_audit.audit_assets
    audit = _real_asset_audit()
    assert audit['passed'], 'TERRAIN_ACTUAL_ASSET_AUDIT_FAILED'
    records = {'world-simulation-shorts-engine/' + row['path']: row for row in value['runtime_records'] + value['parent_deltas']}
    added = [row for row in audit['assets'] if row['path'] in records and row['path'] not in {
        'world-simulation-shorts-engine/' + name for name in AUTHORIZED_PARENT_DELTAS}]
    assert {row['path'] for row in added} >= REQUIRED_AUDITED_ASSETS, 'TERRAIN_ADDED_ASSET_INVENTORY_CHANGED'
    for row in added:
        assert all(row[name] for name in ('referenced', 'exists', 'readable', 'non_zero')), 'TERRAIN_ADDED_ASSET_UNREADABLE'
        assert row['size'] == records[row['path']]['size'] and row['sha256'] == records[row['path']]['sha256'], 'TERRAIN_ADDED_ASSET_CHANGED'
    old = [row for row in audit['assets'] if row['path'] not in {item['path'] for item in added}]
    assert len(old) in (76, 85), 'TERRAIN_PARENT_ASSET_INVENTORY_CHANGED'
    return audit, {row['path'] for row in added}


def child_entrypoint(script):
    value, _ = verify_sources()
    assert hashlib.sha256(script.encode()).hexdigest() in value['parent_cli_script_sha256s'], 'TERRAIN_CHILD_SCRIPT_CHANGED'
    with parent_admission_view():
        exec(compile(script, '<unchanged-v023-cli-regression>', 'exec'), {'__name__': '__main__'})


@contextmanager
def parent_admission_view():
    value, source = verify_sources()
    from deployment.gcube import asset_audit, bold_preflight as bold, selection_preflight as selection
    actual_assets(value)
    real_read, real_run = Path.read_bytes, subprocess.run
    projected = (json.dumps(translated_parent_manifest(value), indent=2) + '\n').encode()

    def read_bytes(path, *args, **kwargs):
        raw = real_read(path, *args, **kwargs)
        if Path(path) == PARENT_MANIFEST and hashlib.sha256(raw).hexdigest() == PARENT_MANIFEST_SHA256:
            # A forged test read is intentionally never replaced by this view.
            return projected
        return raw

    def run(command, *args, **kwargs):
        if (isinstance(command, (list, tuple)) and len(command) == 3 and command[0] == sys.executable
                and command[1] == '-c' and isinstance(command[2], str)
                and hashlib.sha256(command[2].encode()).hexdigest() in value['parent_cli_script_sha256s']):
            command = [command[0], command[1], 'from deployment.gcube.terrain_preflight import child_entrypoint\nchild_entrypoint(' + repr(command[2]) + ')\n']
        return real_run(command, *args, **kwargs)

    def parent_assets():
        audit, added = actual_assets(value)
        result = deepcopy(audit)
        result['assets'] = [row for row in result['assets'] if row['path'] not in added]
        assert len(result['assets']) in (76, 85), 'TERRAIN_PARENT_ASSET_PROJECTION_INVALID'
        return result

    with patch.object(Path, 'read_bytes', read_bytes), patch.object(subprocess, 'run', run), \
         patch.object(asset_audit, 'audit_assets', parent_assets), \
         patch.object(bold, '_real_asset_audit', parent_assets), \
         patch.object(selection, '_actual_asset_audit', parent_assets):
        with bold.parent_admission_view():
            yield source


def freeze(runtime_paths, checkout_paths, approved_preview):
    assert approved_preview, 'TERRAIN_APPROVED_PREVIEW_REQUIRED'
    previous = parent_value()
    deltas = sorted([record(APP / row['path'], APP) for row in previous['parent_deltas']
                     if sha(APP / row['path']) != row['sha256']], key=lambda row: row['path'])
    admit_parent_sources(deltas)
    declared = sorted(set(runtime_paths) | REQUIRED_NEW_RUNTIME)
    assert not set(declared) & {row['path'] for row in previous['runtime_records'] + previous['parent_deltas']}, 'TERRAIN_PARENT_RUNTIME_REPLACED'
    runtime = sorted([record(APP / path, APP) for path in declared], key=lambda row: row['path'])
    preview = json.loads(Path(approved_preview).read_text())
    validate_preview_receipt(preview, runtime)
    from deployment.gcube import selection_preflight as selection
    with selection.environment(**selection.LEGACY_ENV, **LEGACY_ENV, WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE='V022_LEGACY'):
        loader = unittest.TestLoader()
        suite = loader.discover(str(APP / 'tests'))
    ids = selection.identities(suite)
    old_core = sorted(previous['inherited_core_ids'] + previous['new_ids'])
    assert not loader.errors and ids == sorted(set(ids)) and set(old_core) <= set(ids), 'TERRAIN_PARENT_TEST_REMOVED'
    added = sorted(set(ids) - set(old_core))
    assert added, 'TERRAIN_NEW_TESTS_MISSING'
    tests = {'world-simulation-shorts-engine/tests/' + name.split('.', 1)[0] + '.py' for name in added}
    checkout = sorted([record(ROOT / path, ROOT) for path in set(checkout_paths) | tests], key=lambda row: row['path'])
    tree = ast.parse((APP / 'tests/test_selection_release_harness_v022.py').read_text())
    scripts = [node.value.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'script' for target in node.targets)
               and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    assert len(scripts) == 1, 'TERRAIN_PARENT_CLI_SCRIPT_INVENTORY_CHANGED'
    raw_script = scripts[0]
    wrapped = 'from deployment.gcube.bold_preflight import child_entrypoint\nchild_entrypoint(' + repr(raw_script) + ')\n'
    value = dict(version='v024-terrain', status='FROZEN', parent_digest=PARENT_DIGEST, tag_prefix=TAG_PREFIX,
        parent_manifest_sha256=PARENT_MANIFEST_SHA256, parent_deltas=deltas, runtime_records=runtime,
        checkout_records=checkout, inherited_core_ids=old_core, proxy_ids=previous['proxy_ids'],
        diagnostic_ids=previous['diagnostic_ids'], new_ids=added,
        new_ids_sha256=hashlib.sha256(('\n'.join(added) + '\n').encode()).hexdigest(),
        parent_cli_script_sha256s=sorted(hashlib.sha256(script.encode()).hexdigest() for script in (raw_script, wrapped)),
        unique_tests=1200 + len(added), approved_preview=preview, physical_gpu='NOT_RUN')
    MANIFEST.write_text(json.dumps(value, indent=2) + '\n')
    return dict(passed=True, original_tests=1200, additional_tests=len(added), unique_tests=value['unique_tests'],
                manifest_sha256=sha(MANIFEST), tests_executed=0)


def protected_preflight(folder, *, container=True):
    from deployment.gcube import bold_preflight as bold, selection_preflight as selection
    with selection.environment(**LEGACY_ENV), parent_admission_view():
        result = bold.protected_preflight(folder, container=container)
    assert result['passed'] and result['bold_actual_asset_union_count'] == (115 if container else 106), 'TERRAIN_PARENT_PREFLIGHT_FAILED'
    value, _ = verify_sources()
    audit, added_audited = actual_assets(value)
    union = {row['path']: dict(row) for row in result['bold_actual_assets']}
    for row in audit['assets']:
        if row['path'] in added_audited or row['path'] == 'world-simulation-shorts-engine/web/app.js':
            union[row['path']] = {key: row[key] for key in ('path', 'size', 'sha256')}
    for row in value['runtime_records']:
        if row['path'].startswith(('web/infographic/v024/', 'data/infographic/v024/')):
            path = 'world-simulation-shorts-engine/' + row['path']
            union[path] = dict(row, path=path)
    added = sorted(set(union) - {row['path'] for row in result['bold_actual_assets']})
    assert set(added) >= REQUIRED_AUDITED_ASSETS, 'TERRAIN_ASSET_UNION_MISSING'
    assert len(union) == (115 if container else 106) + len(added), 'TERRAIN_ASSET_UNION_INVALID'
    result['terrain_actual_assets'] = sorted(union.values(), key=lambda row: row['path'])
    result['terrain_actual_asset_union_count'] = len(union)
    notice('Terrain actual asset admission', dict(passed=True, preserved_parent_assets=115 if container else 106,
        actual_asset_union=len(union), actual_auditor_assets=len(audit['assets']), added_assets=added,
        current_ui_sha256=sha(APP / 'web/app.js'), referenced_readable_non_zero=True, physical_gpu='NOT_RUN'))
    return result


def regressions(*, focused=False, container=True):
    value, _ = verify_sources()
    from deployment.gcube import selection_preflight as selection
    if container:
        selection.prepare_regression_runtime()
    with selection.environment(**selection.LEGACY_ENV, **LEGACY_ENV, WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE='V022_LEGACY'), parent_admission_view():
        proxy = selection.admit_proxy_inventory(json.loads(physical_bytes(SELECTION_MANIFEST)))
        loader = unittest.TestLoader()
        complete = loader.discover('tests')
        expected = sorted(value['inherited_core_ids'] + value['new_ids'])
        assert not loader.errors and selection.identities(complete) == expected, 'TERRAIN_TEST_INVENTORY_CHANGED'
        if focused:
            chosen = selection.FOCUSED_ORIGINAL_IDS | {
                identity for identity in value['inherited_core_ids']
                if identity.startswith(selection.FOCUSED_ADDITIVE_MODULES) or identity.startswith('test_bold_release_harness_v023.')}
            chosen |= {identity for identity in value['new_ids'] if identity.startswith('test_terrain_release_harness_v024.')}
            def flatten(suite):
                for item in suite:
                    if isinstance(item, unittest.TestSuite):
                        yield from flatten(item)
                    elif item.id() in chosen:
                        yield item
            complete = unittest.TestSuite(flatten(complete))
            expected = sorted(chosen)
        with selection.authorized_ui_asset_view(require_container_assets=container), selection.legacy_codespaces_fixture_view():
            core = selection.execute_suite(complete, expected, 'terrain-focused' if focused else 'terrain-core-and-parent')
        if focused:
            return dict(passed=True, subset_only=True, full_regression_still_required=True,
                        execution_environment='CONTAINER' if container else 'NATIVE', result=core, physical_gpu='NOT_RUN')
        security = selection.execute_suite(proxy, value['proxy_ids'], 'unchanged-proxy-security-gpu-logic')
        before = os.getcwd()
        diagnostic_directory = Path('/tmp/proxy-diag') if container else ROOT / 'deployment/gcube-proxy-diag'
        assert diagnostic_directory.is_dir(), 'TERRAIN_DIAGNOSTIC_SOURCE_DIRECTORY_MISSING'
        sys.path.insert(0, str(diagnostic_directory))
        try:
            os.chdir(diagnostic_directory)
            suite = unittest.TestLoader().loadTestsFromNames(['test_observer', 'test_server_diag'])
            diagnostic = selection.execute_suite(suite, value['diagnostic_ids'], 'unchanged-independent-diagnostic')
        finally:
            os.chdir(before)
            sys.path.remove(str(diagnostic_directory))
    total = sum(row['tests'] for row in (core, security, diagnostic))
    assert total == value['unique_tests'], 'TERRAIN_TEST_EXECUTION_TOTAL_INVALID'
    for group in (core, security, diagnostic):
        notice('Terrain completed regression group', {key: group[key] for key in ('category', 'tests', 'failures', 'errors', 'skipped')})
    notice('Terrain mandatory regression total', dict(passed=True, original_tests=1200,
        new_tests=len(value['new_ids']), tests=total, failures=0, errors=0, skipped=0,
        execution_environment='CONTAINER' if container else 'NATIVE', physical_gpu='NOT_RUN'))
    return dict(passed=True, groups=[core, security, diagnostic], unique_tests=total,
                execution_environment='CONTAINER' if container else 'NATIVE', physical_gpu='NOT_RUN')


def pixel_preflight(folder):
    value, _ = verify_sources()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    from deployment.gcube import selection_preflight as selection
    from engine.terrain_infographic import prepare_terrain_infographic, validate_terrain_infographic
    from engine.qa_planner import generate_deployment_plan
    request = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24, quality='HIGH',
                   pace='FAST_PLUS', direction_profile='REFERENCE_MASTER', qa_mode=False,
                   tts=False, subtitles=False, bgm=True, sfx=True)
    with selection.environment(WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION='v022',
                               WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE='BOLD_INFOGRAPHIC_V023', **LEGACY_ENV):
        plan = prepare_terrain_infographic(generate_deployment_plan(request))
    assert validate_terrain_infographic(plan)['passed'], 'TERRAIN_PIXEL_PLAN_INVALID'
    plan_path = folder / 'actual-terrain-qa-plan.json'
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    result = subprocess.run(['node', 'tools/terrain_canvas_preview_v024.mjs', '--plan', str(plan_path),
                             '--output', str(folder / 'canvas')], cwd=APP, capture_output=True, text=True, timeout=360)
    assert result.returncode == 0, 'TERRAIN_PIXEL_COMMAND_FAILED'
    metrics = json.loads((folder / 'canvas/metrics.json').read_text())
    assert metrics['passed'] is True and metrics.get('GPU', metrics.get('physical_gpu')) == 'NOT_RUN', 'TERRAIN_PIXEL_MEASUREMENT_FAILED'
    assert metrics['resolution'] == [1080, 1920] and metrics['webgl_context_attempts'] == 0, 'TERRAIN_PIXEL_CPU_SCOPE_INVALID'
    executed_sources = {'/terrain.js': 'web/terrain_infographic_adapter.js',
                        '/metrics.mjs': 'tools/terrain_pixel_metrics_v024.mjs',
                        '/profile.json': 'web/infographic/v024/terrain_profile.json',
                        '/data_profile.json': 'data/infographic/v024/terrain_profile.json',
                        '/preview-runner.mjs': 'tools/terrain_canvas_preview_v024.mjs'}
    assert all(metrics['source_sha256s'].get(url) == sha(APP / path) for url, path in executed_sources.items()), 'TERRAIN_EXECUTED_PIXEL_SOURCE_CHANGED'
    ids = sorted(row['id'] for row in metrics['checks'])
    assert ids == sorted(set(ids)) and ids == value['approved_preview']['mandatory_pixel_checks'], 'TERRAIN_PIXEL_CHECK_INVENTORY_CHANGED'
    assert all(row['passed'] is True for row in metrics['checks']), 'TERRAIN_PIXEL_CHECK_FAILED'
    cases = metrics['cases'] + metrics.get('luminance_stress_cases', [])
    assert len(metrics['cases']) == 5 and len(metrics.get('luminance_stress_cases', [])) == 2, 'TERRAIN_PIXEL_REPRESENTATIVE_OR_STRESS_MISSING'
    assert [row['name'] for row in cases] == value['approved_preview']['case_names'], 'TERRAIN_PIXEL_CASE_INVENTORY_CHANGED'
    output = dict(passed=True, actual_pixel_checks=len(ids), representative_frames=len(metrics['cases']),
                  luminance_stress_cases=len(metrics.get('luminance_stress_cases', [])), resolution=metrics['resolution'],
                  approved_preview_source_pins=True, physical_gpu='NOT_RUN', visual_quality_acceptance='NOT_RUN')
    (folder / 'TERRAIN_PIXEL_PREFLIGHT.json').write_text(json.dumps(output, indent=2) + '\n')
    notice('Terrain actual CPU pixel QC', output)
    for case in cases:
        # Preserve complete per-case pixels in artifact files; concise notices
        # retain the numeric audit without exceeding the public excerpt limit.
        notice('Terrain CPU pixel case ' + case['name'], dict(passed=True, name=case['name'],
            measured_checks=sum(row['id'].startswith(case['name'] + '_') for row in metrics['checks']),
            primary_boundary_core_px=case['core']['width_px_median'],
            secondary_boundary_core_px=[row['core']['width_px_median'] for row in case['secondary']
                                        if row['metrics']['interior_samples'] >= 32],
            primary_fill_rgb_contrast=case['primary']['median_rgb_contrast'],
            source_luminance_error_W3C=case['primary']['luminance']['W3C']['mean_absolute_error'],
            boundary_luminance_contrast=case['edgeContrast']['median_luminance_contrast'],
            halo_reach_px=case['halo']['reach_from_native_edge_px_median'],
            outside_polygon_fill_pixels=case['containment']['outside_native_fill_pixels'],
            visual_profile_off_identical=case['off']['identical'], physical_gpu='NOT_RUN'))
    for role, measurements in metrics['high_resolution_pixel_scale']['roles'].items():
        notice('Terrain HIGH downsampled boundary ' + role, dict(role=role, passed=True,
               internal_resolution=[2160, 3840], output_resolution=[1080, 1920],
               actual_core_width_px=measurements['width_px_median'], physical_gpu='NOT_RUN'))
    verify_sources()
    return output


def gateway_smoke(folder):
    """Actual public create/approve/backend mapping and persisted health only."""
    from deployment.gcube.server import BoundedHTTPServer, GcubeApplication, GcubeHandler
    from deployment.gcube import selection_preflight as selection
    from engine.terrain_infographic import validate_terrain_infographic
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='terrain-private-owner-') as private:
        access = Path(private) / 'owner.txt'
        code = secrets.token_urlsafe(32)
        access.write_text(code)
        access.chmod(0o600)
        with selection.environment(WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE=PROFILE):
            app = GcubeApplication(folder / 'runtime', 'http://127.0.0.1:8001', access, disk_floor=0, maximum_duration=180)
            server = BoundedHTTPServer(('127.0.0.1', 0), GcubeHandler, app)
            app.public_port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = 'https://terrain-smoke.service.gcube.ai:24999'
            cookie = None
            def call(method, route, data=None, *, raw=False):
                headers = {'Host': origin[8:], 'X-Forwarded-Proto': 'http', 'X-Forwarded-For': '8.8.8.8, 10.0.0.2', 'X-Envoy-External-Address': '10.0.0.2'}
                if method == 'POST':
                    headers.update(Origin=origin, **{'Content-Type': 'application/json'})
                if cookie:
                    headers['Cookie'] = cookie
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=240)
                connection.request(method, route, json.dumps(data) if data is not None else None, headers)
                response = connection.getresponse()
                status, values, payload = response.status, dict(response.getheaders()), response.read()
                connection.close()
                assert code.encode() not in payload, 'TERRAIN_SECRET_DISCLOSED'
                return status, values, payload if raw else (json.loads(payload) if payload else None)
            created = []
            try:
                assert call('GET', '/api/health')[0] == 200 and call('GET', '/api/projects')[0] == 401
                assert call('POST', '/auth/login', {'password': 'wrong'})[0] == 401
                status, headers, _ = call('POST', '/auth/login', {'password': code})
                assert status == 200 and all(flag in headers['Set-Cookie'] for flag in ('Secure', 'HttpOnly', 'SameSite=Strict'))
                cookie = headers['Set-Cookie'].split(';', 1)[0]
                raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24, qa_mode=False,
                           quality='HIGH', pace='FAST_PLUS', direction_profile='REFERENCE_MASTER', tts=False,
                           subtitles=False, bgm=True, sfx=True)
                cases = [('QA_V024_AUTO', dict(raw)),
                         ('QA_V024_EXPLICIT', dict(raw, infographic_visual_profile=PROFILE)),
                         ('QA_V023', dict(raw, infographic_visual_profile='BOLD_INFOGRAPHIC_V023')),
                         ('QA_V022', dict(raw, infographic_visual_profile='V022_LEGACY'))]
                # Production data comes from the same existing public measured
                # semantic payload used by the integration fixture, never a
                # fabricated fallback story or a direct private planner call.
                from engine.public_infographic_selection import PRODUCTION_PROFILE
                script = json.loads((APP / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
                production = dict(direction_profile=PRODUCTION_PROFILE, script_record=script,
                                  infographic_visual_profile=PROFILE)
                cases.append(('PRODUCTION_V024', production))
                for name, request in cases:
                    status, _, item = call('POST', '/api/projects', request)
                    assert status == 201, 'TERRAIN_PUBLIC_CREATE_FAILED:' + name
                    plan = item['plan']
                    from engine.public_infographic_selection import require_infographic_selection
                    require_infographic_selection(plan)
                    active = 'V024' in name
                    if active:
                        assert validate_terrain_infographic(plan)['passed'], 'TERRAIN_PUBLIC_CONTRACT_MISSING'
                        expected_page = '/static/render_terrain_infographic_earth.html'
                    elif name.endswith('V023'):
                        assert 'terrain_infographic' not in plan['metadata'] and plan['metadata'].get('bold_infographic'), 'TERRAIN_BOLD_COMPATIBILITY_FAILED'
                        expected_page = '/static/render_bold_infographic_earth.html'
                    else:
                        assert 'terrain_infographic' not in plan['metadata'] and 'bold_infographic' not in plan['metadata'], 'TERRAIN_OFF_NOT_LEGACY'
                        expected_page = '/static/render_infographic_earth.html'
                    frames = sum(scene['frame_count'] for scene in plan['scenes'])
                    if name.startswith('QA_'):
                        assert frames == 720, 'TERRAIN_QA_FRAME_GRID_CHANGED'
                    else:
                        from engine import semantic_timeline
                        assert semantic_timeline.validate_production_plan(plan)['passed'], 'TERRAIN_PRODUCTION_TIMELINE_FAILED'
                        assert plan['metadata']['authored_script'] == script, 'TERRAIN_PRODUCTION_SCRIPT_CHANGED'
                        timeline = plan['metadata']['semantic_timeline']
                        assert timeline['passed'] is True and timeline['total_frames'] == frames and frames != 720, 'TERRAIN_PRODUCTION_UNMEASURED'
                        voice = Path(plan['metadata']['semantic_timeline_directory']) / timeline['voice']['file']
                        assert voice.is_file() and voice.stat().st_size > 0, 'TERRAIN_PRODUCTION_VOICE_MISSING'
                    status, _, approved = call('POST', '/api/projects/' + item['project']['id'] + '/approve',
                                              {'version': item['version'], 'plan_hash': plan['plan_hash']})
                    assert status == 200 and approved['plan']['plan_hash'] == plan['plan_hash'], 'TERRAIN_APPROVAL_CHANGED_PLAN'
                    from engine.infographic_backend import InfographicBackend, infographic_command
                    from urllib.parse import urlsplit
                    scene_path = folder / ('selected-' + name + '.json')
                    scene_path.write_text(json.dumps(approved['plan']['scenes'][0], ensure_ascii=False))
                    command = ['node', str(APP / 'tools/render_production_scene.mjs'), '--scene-json', str(scene_path),
                               '--url', 'http://127.0.0.1/static/render_production_earth.html']
                    mapped = infographic_command(command)
                    assert urlsplit(mapped[mapped.index('--url') + 1]).path == expected_page, 'TERRAIN_RENDERER_SELECTION_FAILED'
                    with patch('engine.backends.CPULocalBackend.run', lambda self, values, cwd, progress: values):
                        assert InfographicBackend().run(command, APP, lambda event: None) == mapped, 'TERRAIN_BACKEND_HANDOFF_FAILED'
                    created.append(dict(case=name, approved=True, renderer=expected_page,
                                        frames=sum(scene['frame_count'] for scene in plan['scenes']), render_requested=False))
                value, _ = verify_sources()
                for row in value['runtime_records']:
                    if row['path'].startswith('web/'):
                        status, _, data = call('GET', '/static/' + row['path'][4:], raw=True)
                        assert status == 200 and len(data) == row['size'] and hashlib.sha256(data).hexdigest() == row['sha256'], 'TERRAIN_SERVED_ASSET_CHANGED'
                start = time.monotonic()
                while time.monotonic() - start < 61:
                    assert thread.is_alive() and call('GET', '/api/health')[0] == 200 and call('GET', '/auth/session')[0] == 200
                    time.sleep(min(2, max(.01, 61 - (time.monotonic() - start))))
                output = dict(passed=True, login='PASS', health='PASS', public_profiles=created,
                              persistence_seconds=round(time.monotonic() - start, 3), render_requested=False, physical_gpu='NOT_RUN')
                (folder / 'TERRAIN_GATEWAY_SMOKE.json').write_text(json.dumps(output, indent=2) + '\n')
                notice('Terrain public gateway smoke', output)
                return output
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)
                app.scheduler.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--approved-preview')
    parser.add_argument('--runtime', action='append', default=[])
    parser.add_argument('--checkout-file', action='append', default=[])
    parser.add_argument('--manifest-only', action='store_true')
    parser.add_argument('--checkout', action='store_true')
    parser.add_argument('--protected-only', action='store_true')
    parser.add_argument('--regressions-only', action='store_true')
    parser.add_argument('--focused-only', action='store_true')
    parser.add_argument('--pixels-only', action='store_true')
    parser.add_argument('--smoke-only', action='store_true')
    parser.add_argument('--native', action='store_true',
                        help='Use actual native asset inventory/source paths; never substitutes for mandatory container gates.')
    parser.add_argument('folder', nargs='?', default='/data/terrain-preflight')
    args = parser.parse_args()
    if args.freeze:
        print(json.dumps(freeze(args.runtime, args.checkout_file, args.approved_preview)))
    elif args.manifest_only:
        print(json.dumps(verify_sources(checkout=args.checkout)[1]))
    elif args.protected_only:
        print(json.dumps(protected_preflight(args.folder, container=not args.native)))
    elif args.regressions_only or args.focused_only:
        print(json.dumps(regressions(focused=args.focused_only, container=not args.native)))
    elif args.pixels_only:
        print(json.dumps(pixel_preflight(args.folder)))
    elif args.smoke_only:
        print(json.dumps(gateway_smoke(args.folder)))
    else:
        raise SystemExit('Select one explicit release gate. Preview approval and physical GPU are separate.')
