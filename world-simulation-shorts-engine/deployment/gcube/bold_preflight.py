"""Additive v023 release admission over the exact published v022 runtime.

The source manifest pins all previous runtime and test identities. The only
parent deltas are the public visual selector's three files. Canvas pixels are
CPU preview evidence; physical GPU rendering and visual acceptance are NOT_RUN.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import http.client
import io
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
MANIFEST = APP / 'deployment/gcube/bold_release_manifest.json'
PARENT_MANIFEST = APP / 'deployment/gcube/selection_release_manifest.json'
INFOGRAPHIC_MANIFEST = APP / 'deployment/gcube/infographic_release_manifest.json'
PARENT_DIGEST = 'sha256:8c0d8b01fe7008ed58546247b31c7c8ef0bc2e368995c8c390d15a8e5bff0aa1'
TAG_PREFIX = 'gcube-v023-bold-infographic-'
AUTHORIZED_PARENT_DELTAS = {'web/app.js', 'deployment/mobile_server.py',
                            'engine/public_infographic_selection.py'}
LEGACY_VISUAL = 'V022_LEGACY'
BOLD_VISUAL = 'BOLD_INFOGRAPHIC_V023'
REQUIRED_NEW_RUNTIME = {
    'deployment/gcube/bold_preflight.py', 'engine/bold_infographic.py',
    'web/bold_infographic_adapter.js', 'web/render_bold_infographic_earth.html',
    'data/infographic/v023/bold_profile.json', 'web/infographic/v023/bold_profile.json',
    'tools/bold_canvas_preview_v023.mjs', 'tools/bold_pixel_metrics_v023.mjs',
    'tools/test_bold_pixel_canvas_v023.mjs', 'tools/test_bold_renderer_v023.mjs',
}
NEW_AUDITED_ASSETS = {
    'world-simulation-shorts-engine/web/bold_infographic_adapter.js',
    'world-simulation-shorts-engine/web/render_bold_infographic_earth.html',
}
_real_asset_audit = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path, root):
    path = Path(path)
    return dict(path=str(path.relative_to(root)), size=path.stat().st_size, sha256=sha(path))


def verify_records(rows, root):
    assert isinstance(rows, list), 'BOLD_SOURCE_RECORDS_INVALID'
    names = [row['path'] for row in rows]
    assert names == sorted(set(names)), 'BOLD_SOURCE_INVENTORY_INVALID'
    for row in rows:
        relative = Path(row['path'])
        assert not relative.is_absolute() and '..' not in relative.parts, 'BOLD_SOURCE_PATH_INVALID'
        file = root / relative
        assert file.is_file() and os.access(file, os.R_OK), 'BOLD_SOURCE_MISSING:' + row['path']
        assert file.stat().st_size == row['size'] and sha(file) == row['sha256'], 'BOLD_SOURCE_CHANGED:' + row['path']


def parent_value():
    return json.loads(PARENT_MANIFEST.read_bytes())


def verify_sources(*, checkout=False):
    value = json.loads(MANIFEST.read_bytes())
    assert value['version'] == 'v023-bold' and value['status'] == 'FROZEN', 'BOLD_MANIFEST_INVALID'
    assert value['parent_digest'] == PARENT_DIGEST and value['tag_prefix'] == TAG_PREFIX, 'BOLD_PARENT_INVALID'
    assert sha(PARENT_MANIFEST) == value['parent_manifest_sha256'], 'BOLD_PARENT_MANIFEST_CHANGED'
    assert sha(INFOGRAPHIC_MANIFEST) == value['infographic_manifest_sha256'], 'BOLD_GIS_MANIFEST_CHANGED'
    previous = parent_value()
    assert previous['unique_tests'] == 1125, 'BOLD_PARENT_TEST_COUNT_CHANGED'
    inherited_core = sorted(previous['inherited_core_ids'] + previous['new_ids'])
    assert len(inherited_core) == 888 and value['inherited_core_ids'] == inherited_core, 'BOLD_PARENT_CORE_IDS_CHANGED'
    assert value['proxy_ids'] == previous['proxy_ids'] and len(value['proxy_ids']) == 206, 'BOLD_PROXY_IDS_CHANGED'
    assert value['diagnostic_ids'] == previous['diagnostic_ids'] and len(value['diagnostic_ids']) == 31, 'BOLD_DIAGNOSTIC_IDS_CHANGED'
    assert value['new_ids'] == sorted(set(value['new_ids'])) and value['new_ids'], 'BOLD_ADDITIVE_IDS_INVALID'
    all_parent = inherited_core + value['proxy_ids'] + value['diagnostic_ids']
    assert not set(value['new_ids']) & set(all_parent), 'BOLD_TEST_IDS_OVERLAP'
    digest = hashlib.sha256(('\n'.join(value['new_ids']) + '\n').encode()).hexdigest()
    assert digest == value['new_ids_sha256'], 'BOLD_ADDITIVE_IDS_CHANGED'
    assert value['unique_tests'] == 1125 + len(value['new_ids']), 'BOLD_TEST_TOTAL_INVALID'
    assert {row['path'] for row in value['parent_deltas']} <= AUTHORIZED_PARENT_DELTAS, 'BOLD_PARENT_SCOPE_CHANGED'
    originals = {row['path']: row for row in previous['runtime_records']}
    delta_names = {row['path'] for row in value['parent_deltas']}
    assert all(name in originals for name in delta_names), 'BOLD_UNKNOWN_PARENT_DELTA'
    verify_records(value['parent_deltas'], APP)
    verify_records([row for row in previous['runtime_records'] if row['path'] not in delta_names], APP)
    protected = json.loads(INFOGRAPHIC_MANIFEST.read_bytes())
    verify_records(protected['runtime_records'], APP)
    verify_records(protected['frozen_parent_records'], APP)
    assert len(protected['runtime_records']) + len(protected['frozen_parent_records']) == 67, 'BOLD_PROTECTED_SOURCE_INVENTORY_CHANGED'
    runtime_names = {row['path'] for row in value['runtime_records']}
    assert runtime_names >= REQUIRED_NEW_RUNTIME, 'BOLD_REQUIRED_RUNTIME_MISSING'
    assert not runtime_names & AUTHORIZED_PARENT_DELTAS, 'BOLD_PARENT_DELTA_DUPLICATED'
    verify_records(value['runtime_records'], APP)
    if checkout:
        verify_records(previous['checkout_records'], ROOT)
        # The parent manifest admits all original proxy/core test source bytes.
        from deployment.gcube.infographic_preflight import verify_source_manifest
        verify_source_manifest(require_checkout=True)
        verify_records(value['checkout_records'], ROOT)
    return value, dict(passed=True, exact_published_parent=PARENT_DIGEST,
        protected_runtime_files=67, original_unique_tests=1125,
        additional_tests=len(value['new_ids']), parent_deltas=value['parent_deltas'],
        manifest_sha256=sha(MANIFEST), physical_gpu='NOT_RUN')


def translated_parent_manifest(value):
    """Receipt view authorizes exact selector bytes, never a new source path."""
    projected = parent_value()
    replacements = {row['path']: row for row in value['parent_deltas']}
    projected['runtime_records'] = [deepcopy(replacements.get(row['path'], row))
                                    for row in projected['runtime_records']]
    return projected


def child_entrypoint(script):
    # The immutable CLI/canonical-cache test starts a fresh Python interpreter.
    # It needs the same release-scoped selector admission as its parent process.
    value, _ = verify_sources()
    assert hashlib.sha256(script.encode()).hexdigest() == value['parent_cli_script_sha256'], 'BOLD_CHILD_SCRIPT_CHANGED'
    with parent_admission_view():
        exec(compile(script, '<unchanged-v022-cli-regression>', 'exec'), {'__name__': '__main__'})


def actual_assets(value):
    global _real_asset_audit
    from deployment.gcube import asset_audit
    if _real_asset_audit is None:
        assert asset_audit.audit_assets.__module__ == 'deployment.gcube.asset_audit', 'BOLD_REAL_ASSET_AUDITOR_UNAVAILABLE'
        _real_asset_audit = asset_audit.audit_assets
    audit = _real_asset_audit()
    assert audit['passed'], 'BOLD_ACTUAL_ASSET_AUDIT_FAILED'
    expected = {'world-simulation-shorts-engine/' + row['path']: row for row in value['runtime_records']}
    added = [row for row in audit['assets'] if row['path'] in NEW_AUDITED_ASSETS]
    assert {row['path'] for row in added} == NEW_AUDITED_ASSETS, 'BOLD_ADDED_ASSET_INVENTORY_CHANGED'
    for row in added:
        pinned = expected[row['path']]
        assert all(row[name] for name in ('referenced', 'exists', 'readable', 'non_zero')), 'BOLD_ADDED_ASSET_UNREADABLE'
        assert row['size'] == pinned['size'] and row['sha256'] == pinned['sha256'], 'BOLD_ADDED_ASSET_CHANGED'
    return audit


@contextmanager
def parent_admission_view():
    """Execute old admission checks with a sealed, three-file selector receipt.

    All manifest/test/source files remain unchanged on disk. Extra geometry,
    renderer, asset, path, SHA, or test changes are rejected before this view.
    The original auditors still hash current bytes and reject further tampering.
    """
    value, source = verify_sources()
    from deployment.gcube import asset_audit, selection_preflight as selection
    initial_assets = actual_assets(value)
    source['actual_auditor_asset_count'] = len(initial_assets['assets'])
    source['fully_audited_added_assets'] = sorted(NEW_AUDITED_ASSETS)
    raw_read = Path.read_text
    real_run = subprocess.run
    rendered = json.dumps(translated_parent_manifest(value), indent=2) + '\n'

    def read_text(path, *args, **kwargs):
        if Path(path) == PARENT_MANIFEST:
            # Revalidate the sealed bytes for each admission, not just entry.
            verify_records(value['parent_deltas'], APP)
            assert sha(PARENT_MANIFEST) == value['parent_manifest_sha256'], 'BOLD_PARENT_MANIFEST_CHANGED'
            return rendered
        return raw_read(path, *args, **kwargs)

    def run(command, *args, **kwargs):
        if (isinstance(command, (list, tuple)) and len(command) == 3
                and command[0] == sys.executable and command[1] == '-c'
                and isinstance(command[2], str)
                and hashlib.sha256(command[2].encode()).hexdigest() == value['parent_cli_script_sha256']):
            wrapped = ('from deployment.gcube.bold_preflight import child_entrypoint\n'
                       'child_entrypoint(' + repr(command[2]) + ')\n')
            command = [command[0], command[1], wrapped]
        return real_run(command, *args, **kwargs)

    def parent_assets():
        audit = actual_assets(value)
        projected = deepcopy(audit)
        projected['assets'] = [row for row in projected['assets'] if row['path'] not in NEW_AUDITED_ASSETS]
        assert len(projected['assets']) in (74, 83), 'BOLD_PARENT_ASSET_INVENTORY_CHANGED'
        return projected

    with patch.object(Path, 'read_text', read_text), patch.object(subprocess, 'run', run), \
         patch.object(asset_audit, 'audit_assets', parent_assets), \
         patch.object(selection, '_actual_asset_audit', parent_assets):
        yield source


def freeze(runtime_paths, checkout_paths):
    previous = parent_value()
    protected = json.loads(INFOGRAPHIC_MANIFEST.read_bytes())
    verify_records(protected['runtime_records'], APP)
    verify_records(protected['frozen_parent_records'], APP)
    deltas = sorted([record(APP / row['path'], APP) for row in previous['runtime_records']
                     if sha(APP / row['path']) != row['sha256']], key=lambda row: row['path'])
    assert {row['path'] for row in deltas} <= AUTHORIZED_PARENT_DELTAS, 'BOLD_UNAUTHORIZED_PARENT_DELTA'
    inherited = sorted(previous['inherited_core_ids'] + previous['new_ids'])
    from deployment.gcube import selection_preflight as selection
    with selection.environment(**selection.LEGACY_ENV, WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE=LEGACY_VISUAL):
        loader = unittest.TestLoader()
        suite = loader.discover(str(APP / 'tests'))
    ids = selection.identities(suite)
    assert not loader.errors and ids == sorted(set(ids)), 'BOLD_TEST_DISCOVERY_FAILED'
    assert set(inherited) <= set(ids), 'BOLD_PARENT_TEST_REMOVED'
    added = sorted(set(ids) - set(inherited))
    assert added, 'BOLD_NEW_TESTS_MISSING'
    declared = sorted(set(runtime_paths) | {'deployment/gcube/bold_preflight.py'})
    assert not set(declared) & {row['path'] for row in protected['runtime_records'] + protected['frozen_parent_records']}, 'BOLD_PROTECTED_RUNTIME_REPLACED'
    runtime = sorted([record(APP / name, APP) for name in declared], key=lambda row: row['path'])
    tests = {'world-simulation-shorts-engine/tests/' + name.split('.', 1)[0] + '.py' for name in added}
    checkout = sorted([record(ROOT / name, ROOT) for name in set(checkout_paths) | tests], key=lambda row: row['path'])
    tree = ast.parse((APP / 'tests/test_selection_release_harness_v022.py').read_text())
    scripts = [node.value.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'script' for target in node.targets)
               and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    assert len(scripts) == 1, 'BOLD_PARENT_CLI_SCRIPT_INVENTORY_CHANGED'
    value = dict(version='v023-bold', status='FROZEN', parent_digest=PARENT_DIGEST,
        tag_prefix=TAG_PREFIX, parent_manifest_sha256=sha(PARENT_MANIFEST),
        infographic_manifest_sha256=sha(INFOGRAPHIC_MANIFEST), parent_deltas=deltas,
        runtime_records=runtime, checkout_records=checkout, inherited_core_ids=inherited,
        proxy_ids=previous['proxy_ids'], diagnostic_ids=previous['diagnostic_ids'], new_ids=added,
        new_ids_sha256=hashlib.sha256(('\n'.join(added) + '\n').encode()).hexdigest(),
        parent_cli_script_sha256=hashlib.sha256(scripts[0].encode()).hexdigest(),
        unique_tests=1125 + len(added), physical_gpu='NOT_RUN')
    MANIFEST.write_text(json.dumps(value, indent=2) + '\n')
    return dict(passed=True, manifest_sha256=sha(MANIFEST), original_tests=1125,
                additional_tests=len(added), unique_tests=value['unique_tests'], tests_executed=0)


def protected_preflight(folder, *, container=True):
    from deployment.gcube import selection_preflight as selection
    with selection.environment(WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE=LEGACY_VISUAL), parent_admission_view():
        result = selection.protected_preflight(folder, require_container_assets=container)
    assert result['passed'], 'BOLD_PARENT_PREFLIGHT_FAILED'
    expected = 111 if container else 102
    assert result['registered_asset_union_count'] == expected, 'BOLD_PARENT_ASSET_UNION_CHANGED'
    value, _ = verify_sources()
    actual = actual_assets(value)
    union = {row['path']: dict(row) for row in result['assets']}
    for row in actual['assets']:
        if row['path'] in NEW_AUDITED_ASSETS or row['path'] == 'world-simulation-shorts-engine/web/app.js':
            union[row['path']] = {key: row[key] for key in ('path', 'size', 'sha256')}
    for row in value['runtime_records']:
        if row['path'].startswith(('web/infographic/v023/', 'data/infographic/v023/')):
            name = 'world-simulation-shorts-engine/' + row['path']
            union[name] = dict(row, path=name)
    assert len(union) == expected + 4, 'BOLD_CURRENT_ASSET_UNION_CHANGED'
    result['bold_actual_assets'] = sorted(union.values(), key=lambda row: row['path'])
    result['bold_actual_asset_union_count'] = len(union)
    result['bold_added_assets'] = sorted(set(union) - {row['path'] for row in result['assets']})
    print('::notice title=Bold actual asset admission::' + json.dumps(dict(
        passed=True, preserved_parent_assets=expected, actual_asset_union=len(union),
        actual_auditor_assets=len(actual['assets']), added_assets=result['bold_added_assets'],
        current_ui_sha256=sha(APP / 'web/app.js'), referenced_readable_non_zero=True,
        physical_gpu='NOT_RUN')), flush=True)
    return result


def regressions(*, focused=False):
    value, _ = verify_sources()
    from deployment.gcube import selection_preflight as selection
    selection.prepare_regression_runtime()
    with selection.environment(**selection.LEGACY_ENV, WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE=LEGACY_VISUAL), parent_admission_view():
        # Frozen old test files are supplied read-only from the admitted source
        # checkout; preserve both the original 1061 and the selector's 64 tests.
        frozen = json.loads(INFOGRAPHIC_MANIFEST.read_bytes())
        prefix = 'world-simulation-shorts-engine/tests/'
        tests = [row for row in frozen['checkout_records'] + parent_value()['checkout_records']
                 if row['path'].startswith(prefix)]
        unique = {row['path']: row for row in tests}
        verify_records(sorted(unique.values(), key=lambda row: row['path']), ROOT)
        proxy = selection.admit_proxy_inventory(parent_value())
        loader = unittest.TestLoader()
        complete = loader.discover('tests')
        expected = sorted(value['inherited_core_ids'] + value['new_ids'])
        assert not loader.errors and selection.identities(complete) == expected, 'BOLD_TEST_INVENTORY_CHANGED'
        if focused:
            # Fail fast on release harness/admission defects. All new runtime,
            # browser and pixel tests execute in the mandatory full union below;
            # repeating their long public Production fixtures here adds no gate.
            chosen = {identity for identity in value['new_ids']
                      if identity.startswith('test_bold_release_harness_v023.')} | selection.FOCUSED_ORIGINAL_IDS | {
                identity for identity in value['inherited_core_ids']
                if identity.startswith(selection.FOCUSED_ADDITIVE_MODULES)}
            assert len(chosen) == 52, 'BOLD_FOCUSED_RELEASE_INVENTORY_CHANGED'
            def flatten(suite):
                for item in suite:
                    if isinstance(item, unittest.TestSuite):
                        yield from flatten(item)
                    elif item.id() in chosen:
                        yield item
            complete = unittest.TestSuite(flatten(complete))
            expected = sorted(chosen)
        with selection.authorized_ui_asset_view(require_container_assets=True), selection.legacy_codespaces_fixture_view():
            core = selection.execute_suite(complete, expected, 'bold-focused' if focused else 'bold-core-and-parent')
        if focused:
            return dict(passed=True, subset_only=True, full_regression_still_required=True, result=core, physical_gpu='NOT_RUN')
        security = selection.execute_suite(proxy, value['proxy_ids'], 'unchanged-proxy-security-gpu-logic')
        before = os.getcwd()
        sys.path.insert(0, '/tmp/proxy-diag')
        try:
            os.chdir('/tmp/proxy-diag')
            suite = unittest.TestLoader().loadTestsFromNames(['test_observer', 'test_server_diag'])
            diagnostic = selection.execute_suite(suite, value['diagnostic_ids'], 'unchanged-independent-diagnostic')
        finally:
            os.chdir(before)
            sys.path.remove('/tmp/proxy-diag')
    assert sum(row['tests'] for row in (core, security, diagnostic)) == value['unique_tests'], 'BOLD_TEST_EXECUTION_TOTAL_INVALID'
    return dict(passed=True, groups=[core, security, diagnostic], unique_tests=value['unique_tests'], physical_gpu='NOT_RUN')


def call_node(command, *, timeout=180):
    result = subprocess.run(command, cwd=APP, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        print('::error title=Bold native preflight::' + json.dumps(dict(returncode=result.returncode,
              command_category='CPU_CANVAS_OR_PLAN_VALIDATION', stdout_lines=len(result.stdout.splitlines()),
              stderr_lines=len(result.stderr.splitlines()), physical_gpu='NOT_RUN')), flush=True)
        raise AssertionError('BOLD_NATIVE_PREFLIGHT_FAILED')
    return json.loads(result.stdout.splitlines()[-1])


def pixel_receipt(metrics):
    expected = ['WIDE', 'SUEZ_REGIONAL', 'SUEZ_EVENT_VIEW', 'SINGAPORE_REGIONAL']
    stress_names = ['SUEZ_DARK_STRESS', 'SUEZ_BRIGHT_STRESS']
    assert [row['name'] for row in metrics['cases']] == expected, 'BOLD_PIXEL_REPRESENTATIVE_CAPTURE_FAILED'
    stress = metrics.get('luminance_stress_cases', [])
    assert [row['name'] for row in stress] == stress_names, 'BOLD_PIXEL_LUMINANCE_CAPTURE_MISSING'
    checks = metrics['checks']
    assert len(checks) >= 54 and len({row['id'] for row in checks}) == len(checks), 'BOLD_PIXEL_CHECK_INVENTORY_INVALID'
    assert all(row['passed'] is True for row in checks), 'BOLD_PIXEL_MEASUREMENT_FAILED'
    assert metrics['resolution'] == [1080, 1920] and metrics['webgl_context_attempts'] == 0, 'BOLD_PIXEL_CPU_SCOPE_INVALID'
    rows = []
    for case in metrics['cases'] + stress:
        relevant = [row for row in checks if row['id'].startswith(case['name'] + '_')]
        assert relevant and all(row['passed'] is True for row in relevant), 'BOLD_PIXEL_CASE_UNCHECKED'
        rows.append(dict(name=case['name'], passed=True, measured_checks=len(relevant),
            primary_boundary_core_px=case['primaryBoundary']['width_px_median'],
            secondary_boundary_core_px=[row['boundary']['width_px_median'] for row in case['secondary']
                                        if row['metrics']['interior_samples'] >= 32],
            primary_fill_rgb_contrast=case['primary']['median_rgb_contrast'],
            secondary_fill_rgb_contrast=[row['metrics']['median_rgb_contrast'] for row in case['secondary']
                                        if row['metrics']['interior_samples'] >= 32],
            terrain_edge_retention=case['primary']['terrain_edge_retention'],
            terrain_edge_correlation=case['primary']['terrain_edge_correlation'],
            outside_polygon_fill_pixels=case['containment']['outside_native_fill_pixels'],
            visual_profile_off_identical=case['off']['identical'],
            stress_only=case['name'] in stress_names,
            cpu_preview_luminance_scale=case.get('preview_only_luminance_stress', 1)))
    return rows


def pixel_preflight(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    from engine.bold_infographic import prepare_bold_infographic, validate_bold_infographic
    # The existing QA planner's actual final geography/camera is reused.
    request = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
        quality='HIGH', pace='FAST_PLUS', direction_profile='REFERENCE_MASTER',
        qa_mode=False, tts=False, subtitles=False, bgm=True, sfx=True)
    from engine.qa_planner import generate_deployment_plan
    from deployment.gcube import selection_preflight as selection
    with selection.environment(WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION='v022', WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE=LEGACY_VISUAL):
        plan = prepare_bold_infographic(generate_deployment_plan(request))
    assert validate_bold_infographic(plan)['passed'], 'BOLD_PIXEL_PLAN_INVALID'
    source = folder / 'actual-bold-qa-plan.json'
    source.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    detector = call_node(['node', 'tools/test_bold_pixel_canvas_v023.mjs'])
    assert detector['passed'] and detector['GPU'] == 'NOT_RUN', 'BOLD_PIXEL_DETECTOR_FAILED'
    measured = call_node(['node', 'tools/bold_canvas_preview_v023.mjs', '--plan', str(source), '--output', str(folder / 'canvas')], timeout=300)
    metrics = json.loads((folder / 'canvas/metrics.json').read_text())
    assert measured['passed'] and metrics['passed'] and metrics['GPU'] == 'NOT_RUN', 'BOLD_PIXEL_MEASUREMENT_FAILED'
    pixels = pixel_receipt(metrics)
    result = dict(passed=True, detector_checks=len(detector['checks']), representative_frames=4,
        actual_pixel_checks=len(metrics['checks']), resolution=metrics['resolution'],
        source_sha256s=metrics['source_sha256s'], luminance_stress_cases=2, measured_pixels=pixels,
        high_downsampled_core_px={row['id']: row['measurement']['width_px_median']
                                 for row in metrics['checks'] if row['id'].startswith('HIGH_2160_TO_1080_')},
        physical_gpu='NOT_RUN', production_frame_render='NOT_RUN', visual_quality_acceptance='NOT_RUN')
    (folder / 'BOLD_PIXEL_PREFLIGHT.json').write_text(json.dumps(result, indent=2) + '\n')
    print('::notice title=Bold CPU Canvas pixel QC::' + json.dumps(result), flush=True)
    return result


def gateway_smoke(folder):
    """Real authenticated public create/approve/static backend mapping; no job."""
    from deployment.gcube.server import BoundedHTTPServer, GcubeApplication, GcubeHandler
    from engine.bold_infographic import validate_bold_infographic
    from deployment.gcube import selection_preflight as selection
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bold-private-owner-') as private:
        access = Path(private) / 'owner.txt'
        code = secrets.token_urlsafe(32)
        access.write_text(code)
        access.chmod(0o600)
        app = GcubeApplication(folder / 'runtime', 'http://127.0.0.1:8001', access,
                               disk_floor=0, maximum_duration=180)
        server = BoundedHTTPServer(('127.0.0.1', 0), GcubeHandler, app)
        app.public_port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = 'https://bold-smoke.service.gcube.ai:24999'
        cookie = None

        def call(method, route, data=None, *, raw=False):
            headers = {'Host': origin[8:], 'X-Forwarded-Proto': 'http',
                'X-Forwarded-For': '8.8.8.8, 10.0.0.2', 'X-Envoy-External-Address': '10.0.0.2'}
            if method == 'POST':
                headers.update(Origin=origin, **{'Content-Type': 'application/json'})
            if cookie:
                headers['Cookie'] = cookie
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=180)
            connection.request(method, route, json.dumps(data) if data is not None else None, headers)
            response = connection.getresponse()
            status, values, payload = response.status, dict(response.getheaders()), response.read()
            connection.close()
            assert code.encode() not in payload, 'BOLD_SECRET_DISCLOSED'
            return status, values, payload if raw else (json.loads(payload) if payload else None)

        try:
            assert call('GET', '/api/health')[0] == 200
            assert call('GET', '/api/projects')[0] == 401
            assert call('POST', '/auth/login', {'password': 'wrong'})[0] == 401
            status, headers, _ = call('POST', '/auth/login', {'password': code})
            assert status == 200 and all(flag in headers['Set-Cookie'] for flag in ('Secure', 'HttpOnly', 'SameSite=Strict'))
            cookie = headers['Set-Cookie'].split(';', 1)[0]
            raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                qa_mode=False, quality='HIGH', pace='FAST_PLUS', direction_profile='REFERENCE_MASTER',
                tts=False, subtitles=False, bgm=True, sfx=True)
            created = []
            plans = []
            for visual in (BOLD_VISUAL, LEGACY_VISUAL):
                status, _, item = call('POST', '/api/projects', dict(raw, infographic_visual_profile=visual))
                assert status == 201, 'BOLD_PUBLIC_CREATE_FAILED'
                plan = item['plan']
                assert plan['metadata']['infographic']['version'] == 'v022', 'BOLD_PARENT_CONTRACT_CHANGED'
                assert sum(scene['frame_count'] for scene in plan['scenes']) == 720, 'BOLD_PUBLIC_FRAME_GRID_CHANGED'
                if visual == BOLD_VISUAL:
                    assert validate_bold_infographic(plan)['passed'] and plan['metadata'].get('bold_infographic'), 'BOLD_PUBLIC_PROFILE_MISSING'
                else:
                    assert 'bold_infographic' not in plan['metadata'] and all('bold_infographic' not in scene for scene in plan['scenes']), 'BOLD_OFF_NOT_LEGACY'
                project = item['project']['id']
                status, _, approved = call('POST', '/api/projects/' + project + '/approve',
                    {'version': item['version'], 'plan_hash': plan['plan_hash']})
                assert status == 200 and approved['plan']['plan_hash'] == plan['plan_hash'], 'BOLD_APPROVAL_CHANGED_PLAN'
                expected_page = '/static/render_bold_infographic_earth.html' if visual == BOLD_VISUAL else '/static/render_infographic_earth.html'
                from engine.infographic_backend import InfographicBackend, infographic_command
                from urllib.parse import urlsplit
                scene_file = folder / ('selected-' + visual + '.json')
                scene_file.write_text(json.dumps(approved['plan']['scenes'][0], ensure_ascii=False))
                command = ['node', str(APP / 'tools/render_production_scene.mjs'), '--scene-json', str(scene_file),
                           '--url', 'http://127.0.0.1/static/render_production_earth.html']
                mapped = infographic_command(command)
                index = mapped.index('--url') + 1
                assert urlsplit(mapped[index]).path == expected_page, 'BOLD_RENDERER_SELECTION_FAILED'
                retained = list(mapped)
                retained[index] = command[command.index('--url') + 1]
                assert retained == command, 'BOLD_RENDER_COMMAND_ARGS_CHANGED'
                # Sentinel prevents subprocess/GPU execution, while exercising
                # the actual backend class and URL mapping used by production.
                with patch('engine.backends.CPULocalBackend.run', lambda self, values, cwd, progress: values):
                    assert InfographicBackend().run(command, APP, lambda event: None) == mapped, 'BOLD_BACKEND_HANDOFF_FAILED'
                plans.append(plan)
                created.append(dict(visual_profile=visual, approved=True, renderer=expected_page, frames=720, render_requested=False))
            from engine.infographic_contract import parent
            for before, after in zip(plans[1]['scenes'], plans[0]['scenes']):
                assert parent._camera_snapshot(before) == parent._camera_snapshot(after), 'BOLD_CAMERA_CHANGED'
                assert parent._quality_snapshot(before) == parent._quality_snapshot(after), 'BOLD_BASE_QUALITY_CHANGED'
                assert parent._source_snapshot(before) == parent._source_snapshot(after), 'BOLD_BASE_SOURCE_CHANGED'
            value, _ = verify_sources()
            served = []
            for row in value['runtime_records']:
                if row['path'].startswith('web/'):
                    status, _, payload = call('GET', '/static/' + row['path'][4:], raw=True)
                    assert status == 200 and len(payload) == row['size'] and hashlib.sha256(payload).hexdigest() == row['sha256'], 'BOLD_SERVED_ASSET_CHANGED'
                    served.append(row['path'])
            start = time.monotonic()
            while time.monotonic() - start < 61:
                assert thread.is_alive() and call('GET', '/api/health')[0] == 200
                assert call('GET', '/auth/session')[0] == 200
                time.sleep(min(2, max(.01, 61 - (time.monotonic() - start))))
            result = dict(passed=True, login='PASS', health='PASS', secure_cookie='PASS',
                public_profiles=created, served_assets=served, camera='UNCHANGED', base_quality='UNCHANGED',
                persistence_seconds=round(time.monotonic() - start, 3), render_requested=False, physical_gpu='NOT_RUN')
            (folder / 'BOLD_GATEWAY_SMOKE.json').write_text(json.dumps(result, indent=2) + '\n')
            print('::notice title=Bold public gateway smoke::' + json.dumps(result), flush=True)
            return result
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            app.scheduler.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--runtime', action='append', default=[])
    parser.add_argument('--checkout-file', action='append', default=[])
    parser.add_argument('--manifest-only', action='store_true')
    parser.add_argument('--checkout', action='store_true')
    parser.add_argument('--protected-only', action='store_true')
    parser.add_argument('--regressions-only', action='store_true')
    parser.add_argument('--focused-only', action='store_true')
    parser.add_argument('--pixels-only', action='store_true')
    parser.add_argument('--smoke-only', action='store_true')
    parser.add_argument('folder', nargs='?', default='/data/bold-preflight')
    args = parser.parse_args()
    if args.freeze:
        print(json.dumps(freeze(args.runtime, args.checkout_file)))
    elif args.manifest_only:
        print(json.dumps(verify_sources(checkout=args.checkout)[1]))
    elif args.protected_only:
        print(json.dumps(protected_preflight(args.folder)))
    elif args.regressions_only or args.focused_only:
        print(json.dumps(regressions(focused=args.focused_only)))
    elif args.pixels_only:
        print(json.dumps(pixel_preflight(args.folder)))
    elif args.smoke_only:
        print(json.dumps(gateway_smoke(args.folder)))
    else:
        raise SystemExit('Select one explicit release gate; no GPU rendering is available here.')
