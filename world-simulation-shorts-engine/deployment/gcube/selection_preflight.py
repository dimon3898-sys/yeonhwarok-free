"""Source-pinned UI/API admission over the immutable v022 infographic runtime.

The previous manifest and all 1061 admitted test identities remain unchanged.
This release adds public selection checks; NVIDIA/video quality is NOT_RUN.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import http.client
import importlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
if __name__ == '__main__':
    # CLI and tests must share one module and the same captured real auditors.
    canonical = 'deployment.gcube.selection_preflight'
    sys.modules[canonical] = sys.modules[__name__]
    setattr(importlib.import_module('deployment.gcube'), 'selection_preflight', sys.modules[__name__])
MANIFEST = APP / 'deployment/gcube/selection_release_manifest.json'
PARENT_MANIFEST = APP / 'deployment/gcube/infographic_release_manifest.json'
PARENT_DIGEST = 'sha256:e5de0f00022715dd2b1653c684213cf23359f337fca160afff3215b865104fed'
TAG_PREFIX = 'gcube-v022-selection-fix-'
AUTHORIZED_RUNTIME = {
    'web/app.js', 'deployment/mobile_server.py',
    'engine/public_infographic_selection.py', 'deployment/gcube/selection_preflight.py',
}
UI_ASSET_PATH = 'world-simulation-shorts-engine/web/app.js'
BASE_UI_ASSET = dict(size=43729,
    sha256='d6a25dd6c03594ac85b6bf64d3d2997ef38d83d084e97fe85bd16d02808f6050')
_original_asset_audit = None
_original_source_audit = None


def _actual_asset_audit():
    global _original_asset_audit
    if _original_asset_audit is None:
        from deployment.gcube.asset_audit import audit_assets
        _original_asset_audit = audit_assets
    return _original_asset_audit()


def _actual_source_audit():
    global _original_source_audit
    if _original_source_audit is None:
        from deployment.gcube.visual_quality_preflight import audit_frozen_sources
        _original_source_audit = audit_frozen_sources
    return _original_source_audit()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path, root):
    return dict(path=str(path.relative_to(root)), size=path.stat().st_size, sha256=sha(path))


def identities(suite):
    return sorted(identity for test in suite for identity in
                  (identities(test) if isinstance(test, unittest.TestSuite) else [test.id()]))


def id_sha(values):
    return hashlib.sha256(('\n'.join(values) + '\n').encode()).hexdigest()


@contextmanager
def environment(**values):
    prior = {name: os.environ.get(name) for name in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for name, value in prior.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


LEGACY_ENV = dict.fromkeys((
    'WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION', 'WORLD_ENGINE_STORY_PROGRESSION_VERSION',
    'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION', 'WORLD_ENGINE_EVENT_QUALITY_VERSION',
    'WORLD_ENGINE_VISUAL_QUALITY_VERSION', 'WORLD_ENGINE_DIRECTION_VERSION'), 'legacy')
LEGACY_ENV.update(dict.fromkeys(('WORLD_ENGINE_SECOND_EVENT_TEST',
    'WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST', 'WORLD_ENGINE_RETURN_WIDE_TEST'), '0'))


def verify_records(rows, root):
    names = [row['path'] for row in rows]
    assert names == sorted(set(names)), 'SELECTION_SOURCE_INVENTORY_INVALID'
    for row in rows:
        relative = Path(row['path'])
        assert not relative.is_absolute() and '..' not in relative.parts, 'SELECTION_SOURCE_PATH_INVALID'
        file = root / relative
        assert file.is_file() and os.access(file, os.R_OK), 'SELECTION_SOURCE_MISSING'
        assert file.stat().st_size == row['size'] and sha(file) == row['sha256'], 'SELECTION_SOURCE_CHANGED:' + row['path']


def verify_sources(*, checkout=False):
    value = json.loads(MANIFEST.read_text())
    assert value['version'] == 'v022-selection' and value['status'] == 'FROZEN', 'SELECTION_MANIFEST_INVALID'
    assert value['parent_digest'] == PARENT_DIGEST and value['tag_prefix'] == TAG_PREFIX, 'SELECTION_PARENT_INVALID'
    assert sha(PARENT_MANIFEST) == value['parent_manifest_sha256'], 'SELECTION_PARENT_MANIFEST_CHANGED'
    from deployment.gcube.infographic_preflight import verify_source_manifest, load_manifest
    # The original source/renderer/GIS/camera admission is executed unchanged.
    original = verify_source_manifest(require_checkout=checkout)
    parent = load_manifest()
    inherited = sorted(parent['tests']['inherited_ids'] + parent['tests']['new_ids'])
    assert value['inherited_core_ids'] == inherited and len(inherited) == 824, 'SELECTION_ORIGINAL_CORE_IDS_CHANGED'
    assert value['proxy_ids'] == parent['tests']['proxy_ids'] and len(value['proxy_ids']) == 206, 'SELECTION_PROXY_IDS_CHANGED'
    assert value['diagnostic_ids'] == parent['tests']['diagnostic_ids'] and len(value['diagnostic_ids']) == 31, 'SELECTION_DIAGNOSTIC_IDS_CHANGED'
    assert value['new_ids'] == sorted(set(value['new_ids'])) and value['new_ids'], 'SELECTION_ADDITIVE_IDS_INVALID'
    assert not set(value['new_ids']) & set(inherited + value['proxy_ids'] + value['diagnostic_ids']), 'SELECTION_TEST_IDS_OVERLAP'
    assert id_sha(value['new_ids']) == value['new_ids_sha256'], 'SELECTION_NEW_TEST_IDS_CHANGED'
    assert value['unique_tests'] == 1061 + len(value['new_ids']), 'SELECTION_TEST_COUNT_INVALID'
    assert {row['path'] for row in value['runtime_records']} == AUTHORIZED_RUNTIME, 'SELECTION_RUNTIME_SCOPE_CHANGED'
    verify_records(value['runtime_records'], APP)
    if checkout:
        verify_records(value['checkout_records'], ROOT)
    return value, dict(passed=True, parent_manifest_unchanged=True,
        protected_original_runtime_files=len(original['runtime_records']) + len(original['frozen_parent_records']),
        original_unique_test_ids=1061, additional_test_ids=len(value['new_ids']),
        selection_manifest_sha256=sha(MANIFEST), physical_gpu='NOT_RUN')


def authorized_ui_asset_projection(audit, application_record, *, require_container_assets):
    """Admit the sole UI file delta without changing any inherited asset identity."""
    from deployment.gcube.infographic_preflight import NEW_AUDITED_ASSETS as INFOGRAPHIC
    from deployment.gcube.story_progression_preflight import NEW_AUDITED_ASSETS as STORY
    from deployment.gcube.reference_effects_preflight import (
        NEW_AUDITED_ASSETS as EFFECTS, PARENT_CONTAINER_ASSET_IDENTITY,
        PARENT_NATIVE_ASSET_IDENTITY)
    assert audit['passed'], 'SELECTION_CURRENT_ASSET_AUDIT_FAILED'
    actual = deepcopy(audit)
    rows = actual['assets']
    names = [row['path'] for row in rows]
    assert len(names) == len(set(names)), 'SELECTION_ASSET_PATH_DUPLICATE'
    expected_count = 83 if require_container_assets else 74
    assert len(rows) == expected_count, 'SELECTION_CURRENT_ASSET_INVENTORY_CHANGED'
    assert all(row['referenced'] and row['exists'] and row['readable'] and row['non_zero']
               and row['size'] > 0 for row in rows), 'SELECTION_CURRENT_ASSET_UNREADABLE'
    assert application_record['path'] == 'web/app.js', 'SELECTION_UI_ASSET_SCOPE_CHANGED'
    selected = [row for row in rows if row['path'] == UI_ASSET_PATH]
    assert len(selected) == 1, 'SELECTION_UI_ASSET_MISSING'
    current = selected[0]
    assert current['size'] == application_record['size'] and current['sha256'] == application_record['sha256'], 'SELECTION_UI_ASSET_SOURCE_CHANGED'
    baseline = deepcopy(actual)
    baseline_ui = next(row for row in baseline['assets'] if row['path'] == UI_ASSET_PATH)
    baseline_ui.update(BASE_UI_ASSET)
    excluded = INFOGRAPHIC | STORY | EFFECTS
    parent_rows = [dict(path=row['path'], size=row['size'], sha256=row['sha256'])
                   for row in baseline['assets'] if row['path'] not in excluded]
    parent_rows.sort(key=lambda row: row['path'])
    expected_parent_count = 77 if require_container_assets else 68
    assert len(parent_rows) == expected_parent_count, 'SELECTION_PARENT_ASSET_INVENTORY_CHANGED'
    digest = hashlib.sha256(json.dumps(parent_rows, sort_keys=True,
                           separators=(',', ':')).encode()).hexdigest()
    expected = PARENT_CONTAINER_ASSET_IDENTITY if require_container_assets else PARENT_NATIVE_ASSET_IDENTITY
    assert digest == expected, 'SELECTION_UNAUTHORIZED_PARENT_ASSET_DELTA'
    proof = dict(passed=True, actual_current_audit=actual, authorized_asset_delta=[dict(
        path=UI_ASSET_PATH, previous_size=BASE_UI_ASSET['size'], previous_sha256=BASE_UI_ASSET['sha256'],
        actual_size=current['size'], actual_sha256=current['sha256'])],
        inherited_parent_identity_sha256=digest, inherited_parent_count=len(parent_rows),
        only_authorized_ui_delta=True, physical_gpu='NOT_RUN',
        scope='Actual current assets audited separately; only app.js identity projected for unchanged inherited release checks')
    return baseline, proof


@contextmanager
def authorized_ui_asset_view(*, require_container_assets):
    value, _ = verify_sources()
    application_record = next(row for row in value['runtime_records'] if row['path'] == 'web/app.js')
    from deployment.gcube import visual_quality_preflight
    # Audit actual current bytes before constructing the narrowly scoped receipt view.
    baseline, proof = authorized_ui_asset_projection(_actual_asset_audit(), application_record,
                               require_container_assets=require_container_assets)
    original_source_audit = _actual_source_audit
    assert visual_quality_preflight.FROZEN_SOURCES[UI_ASSET_PATH] == BASE_UI_ASSET['sha256'], 'SELECTION_LEGACY_UI_SOURCE_CHANGED'
    actual_sources = original_source_audit()
    proof['actual_legacy_frozen_source_audit'] = deepcopy(actual_sources)

    def selection_source_audit():
        file = APP / 'web/app.js'
        assert file.stat().st_size == application_record['size'] and sha(file) == application_record['sha256'], 'SELECTION_UI_ASSET_SOURCE_CHANGED'
        # Execute every original hash/dimension check; authorize only the new UI hash.
        with patch.dict(visual_quality_preflight.FROZEN_SOURCES,
                        {UI_ASSET_PATH: application_record['sha256']}):
            result = original_source_audit()
        selected = [row for row in result['sources'] if row['file'] == UI_ASSET_PATH]
        assert len(selected) == 1 and selected[0]['actual_sha256'] == application_record['sha256'], 'SELECTION_UI_SOURCE_AUDIT_CHANGED'
        selected[0].update(legacy_expected_sha256=BASE_UI_ASSET['sha256'],
                           actual_unchanged=False, authorized_delta=True)
        result['selection_ui_compatibility'] = dict(authorized_asset_delta=proof['authorized_asset_delta'],
            actual_unmodified_audit_passed=actual_sources['passed'],
            scope='Original source checks executed with the sole explicitly authorized app.js expected hash; original dictionary restored')
        return result

    checked_sources = selection_source_audit()
    assert checked_sources['passed'], 'SELECTION_UNAUTHORIZED_FROZEN_SOURCE_DELTA'
    proof['authorized_legacy_frozen_source_audit'] = deepcopy(checked_sources)
    print('::notice title=Selection authorized asset admission::' + json.dumps(dict(
        passed=True, actual_assets=len(proof['actual_current_audit']['assets']),
        authorized_asset_delta=proof['authorized_asset_delta'],
        inherited_parent_count=proof['inherited_parent_count'],
        inherited_parent_identity_sha256=proof['inherited_parent_identity_sha256'])), flush=True)
    with patch('deployment.gcube.asset_audit.audit_assets', lambda: deepcopy(baseline)), \
         patch.object(visual_quality_preflight, 'audit_frozen_sources', selection_source_audit):
        yield proof


def protected_preflight(folder, *, require_container_assets=True):
    from deployment.gcube.infographic_preflight import run as inherited_run
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with authorized_ui_asset_view(require_container_assets=require_container_assets) as proof:
        (folder / 'SELECTION_ASSETS.json').write_text(json.dumps(proof, indent=2) + '\n')
        original = inherited_run(folder, require_container_assets=require_container_assets)
    assert original['passed'], 'SELECTION_PROTECTED_PREFLIGHT_FAILED'
    result = dict(original, selection_assets=proof)
    (folder / 'SELECTION_REPORT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def freeze(runtime_paths):
    from deployment.gcube.infographic_preflight import verify_source_manifest, load_manifest
    verify_source_manifest(require_checkout=True)
    parent = load_manifest()
    previous = os.getcwd()
    try:
        os.chdir(APP)
        with environment(**LEGACY_ENV):
            loader = unittest.TestLoader()
            suite = loader.discover('tests')
    finally:
        os.chdir(previous)
    current = identities(suite)
    assert not loader.errors and current == sorted(set(current)), 'SELECTION_TEST_DISCOVERY_FAILED'
    inherited = sorted(parent['tests']['inherited_ids'] + parent['tests']['new_ids'])
    assert set(inherited) <= set(current), 'SELECTION_INHERITED_TEST_REMOVED'
    added = sorted(set(current) - set(inherited))
    assert added, 'SELECTION_ADDITIVE_TESTS_MISSING'
    declared = set(runtime_paths) | {'deployment/gcube/selection_preflight.py'}
    assert declared == AUTHORIZED_RUNTIME, 'SELECTION_RUNTIME_SCOPE_CHANGED'
    runtime = sorted({APP / name for name in declared})
    checkout_names = [
        '.github/workflows/gcube-selection-v022.yml',
        'world-simulation-shorts-engine/deployment/gcube/Dockerfile.selection-v022',
        'world-simulation-shorts-engine/deployment/gcube/Dockerfile.selection-v022.dockerignore',
        'world-simulation-shorts-engine/tests/infographic_ui_v022.mjs',
        'world-simulation-shorts-engine/tests/fixtures/infographic_public_selection_v022/approved_before_selection_fix.json',
    ] + ['world-simulation-shorts-engine/tests/' + name.split('.', 1)[0] + '.py' for name in added]
    value = dict(version='v022-selection', status='FROZEN', parent_digest=PARENT_DIGEST,
        tag_prefix=TAG_PREFIX, parent_manifest_sha256=sha(PARENT_MANIFEST),
        runtime_records=sorted([record(file, APP) for file in runtime], key=lambda row: row['path']),
        checkout_records=sorted([record(ROOT / name, ROOT) for name in set(checkout_names)], key=lambda row: row['path']),
        inherited_core_ids=inherited, proxy_ids=parent['tests']['proxy_ids'],
        diagnostic_ids=parent['tests']['diagnostic_ids'], new_ids=added,
        new_ids_sha256=id_sha(added), unique_tests=1061 + len(added), physical_gpu='NOT_RUN')
    MANIFEST.write_text(json.dumps(value, indent=2) + '\n')
    return dict(passed=True, manifest_sha256=sha(MANIFEST), additional_tests=len(added),
                unique_tests=value['unique_tests'], tests_executed=0)


def execute_suite(suite, expected, category):
    from deployment.gcube.infographic_preflight import SafeResult
    class SelectionSafeResult(SafeResult):
        def _record(self, test, error):
            before = len(self.safe_failures)
            super()._record(test, error)
            if len(self.safe_failures) == before:
                return
            self.safe_failures[-1]['python_runtime_locations'] = [
                dict(file=Path(frame.filename).name, function=frame.name, line=frame.lineno)
                for frame in traceback.extract_tb(error[2])
                if Path(frame.filename).suffix == '.py'
                and Path(frame.filename).parent.name in {'engine', 'deployment', 'gcube'}][-8:]
            code = getattr(error[1], 'code', None)
            if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', code):
                self.safe_failures[-1]['error_code'] = code
            errno = getattr(error[1], 'errno', None)
            if isinstance(errno, int):
                self.safe_failures[-1]['errno'] = errno
    assert identities(suite) == expected, 'SELECTION_TEST_SUITE_CHANGED:' + category
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=1, resultclass=SelectionSafeResult).run(suite)
    report = dict(category=category, tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), failure_locations=result.safe_failures)
    summary = {key: value for key, value in report.items() if key != 'failure_locations'}
    summary['safe_failure_records'] = len(result.safe_failures)
    print('::notice title=Selection regressions::' + json.dumps(summary), flush=True)
    for index, failure in enumerate(result.safe_failures, 1):
        print('::notice title=Selection regression failure ' + str(index) + '::' + json.dumps(failure), flush=True)
    assert sorted(result.executed) == expected, 'SELECTION_TEST_EXECUTION_INCOMPLETE:' + category
    assert result.wasSuccessful() and not result.skipped, 'SELECTION_REGRESSION_FAILED:' + category
    return report


@contextmanager
def legacy_codespaces_fixture_view():
    """Supply added application interfaces only to the old synthetic HTTP fixture.

    The seven immutable Codespaces tests retain their request guards, planner,
    storage and worker assertions. Real applications never enter this adapter.
    """
    import test_codespaces_origin
    from deployment.mobile_server import MobileApplication
    fixture = test_codespaces_origin.CodespacesHTTPTests
    original = fixture.setUp
    assert fixture.__module__ == 'test_codespaces_origin', 'SELECTION_LEGACY_FIXTURE_SCOPE_CHANGED'
    if getattr(original, '_selection_legacy_fixture_adapter', False):
        # Core execution and its admission tests may nest the same narrow view.
        yield fixture
        return

    def adapted_set_up(test):
        original(test)
        try:
            assert type(test.app) is SimpleNamespace, 'SELECTION_LEGACY_FIXTURE_APP_CHANGED'
            missing = ('create_project', 'check_profile_selection', 'check_revision_profile_selection')
            assert all(not hasattr(test.app, name) for name in missing), 'SELECTION_LEGACY_FIXTURE_ALREADY_HAS_SELECTION'
            test.app.create_project = MobileApplication.create_project.__get__(test.app, SimpleNamespace)
            test.app.check_profile_selection = Mock()
            test.app.check_revision_profile_selection = Mock()
        except BaseException:
            test.tearDown()
            raise

    adapted_set_up._selection_legacy_fixture_adapter = True
    with patch.object(fixture, 'setUp', adapted_set_up):
        yield fixture


FOCUSED_ORIGINAL_IDS = {
    'test_codespaces_origin.CodespacesHTTPTests.test_all_ten_post_endpoints_dispatch_with_exact_codespaces_origin',
    'test_codespaces_origin.CodespacesHTTPTests.test_all_ten_post_endpoints_reject_wrong_origin_before_body_or_auth',
    'test_direction.DirectionFixtures.test_actual_mixed_core_onsets_match_native_visibility_receipts',
    'test_gpu_bundle.PreflightTests.test_all_five_suez_qa12_native_checks_and_repeat_audio_pass',
    'test_infographic_integration_v022.InfographicIntegration.test_real_production_render_handoff_reuses_verified_audio_and_subtitle_checkpoints',
}
FOCUSED_ADDITIVE_MODULES = (
    'test_infographic_selection_backend_v022.',
    'test_selection_release_assets_v022.',
    'test_selection_release_harness_v022.',
)


def prepare_regression_runtime():
    # Same scratch directories as the original immutable release test harness.
    for name in ('cache', 'audio'):
        (Path('/run/world-engine') / name).mkdir(parents=True, exist_ok=True)


def focused_regressions(value):
    """Fast diagnosis only; the full frozen union remains mandatory afterward."""
    prepare_regression_runtime()
    with environment(**LEGACY_ENV):
        loader = unittest.TestLoader()
        complete = loader.discover('tests')
        assert not loader.errors, 'SELECTION_TEST_IMPORT_FAILURE'
        expected = sorted(value['inherited_core_ids'] + value['new_ids'])
        assert identities(complete) == expected, 'SELECTION_UNREGISTERED_TEST_IDS'
        selected = {identity for identity in value['new_ids']
                    if identity.startswith(FOCUSED_ADDITIVE_MODULES)} | FOCUSED_ORIGINAL_IDS
        assert FOCUSED_ORIGINAL_IDS <= set(value['inherited_core_ids']), 'SELECTION_FOCUSED_ORIGINAL_IDS_CHANGED'

        def subset(suite):
            for test in suite:
                if isinstance(test, unittest.TestSuite):
                    yield from subset(test)
                elif test.id() in selected:
                    yield test

        with authorized_ui_asset_view(require_container_assets=True), legacy_codespaces_fixture_view():
            result = execute_suite(unittest.TestSuite(subset(complete)), sorted(selected), 'focused-release-diagnosis')
    return dict(passed=True, subset_only=True, full_regression_still_required=True,
                result=result, physical_gpu='NOT_RUN')


def regressions(value):
    prepare_regression_runtime()
    with environment(**LEGACY_ENV):
        loader = unittest.TestLoader()
        complete = loader.discover('tests')
        assert not loader.errors, 'SELECTION_TEST_IMPORT_FAILURE'
        expected = sorted(value['inherited_core_ids'] + value['new_ids'])
        assert identities(complete) == expected, 'SELECTION_UNREGISTERED_TEST_IDS'
        with authorized_ui_asset_view(require_container_assets=True), legacy_codespaces_fixture_view():
            core = execute_suite(complete, expected, 'core-and-public-selection')
        loader = unittest.TestLoader()
        proxy = loader.discover('deployment/gcube', pattern='test_*.py')
        assert not loader.errors, 'SELECTION_PROXY_IMPORT_FAILURE'
        security = execute_suite(proxy, value['proxy_ids'], 'proxy-security-gpu-logic')
        previous = os.getcwd()
        sys.path.insert(0, '/tmp/proxy-diag')
        try:
            os.chdir('/tmp/proxy-diag')
            diagnostic = unittest.TestLoader().loadTestsFromNames(['test_observer', 'test_server_diag'])
            diag = execute_suite(diagnostic, value['diagnostic_ids'], 'independent-diagnostic')
        finally:
            os.chdir(previous)
            sys.path.remove('/tmp/proxy-diag')
    assert sum(row['tests'] for row in (core, security, diag)) == value['unique_tests'], 'SELECTION_TEST_TOTAL_INVALID'
    return dict(passed=True, groups=[core, security, diag], unique_tests=value['unique_tests'], physical_gpu='NOT_RUN')


def gateway_selection_smoke(folder):
    """Real public HTTP create/approve and command mapping; never enqueue render."""
    from deployment.gcube.server import BoundedHTTPServer, GcubeApplication, GcubeHandler
    from deployment.gcube.infographic_preflight import audit_backend
    from engine.infographic_contract import validate_infographic
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='selection-owner-') as private:
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
        origin = 'https://selection-smoke.service.gcube.ai:24999'
        cookie = None

        def call(method, route, data=None):
            headers = {'Host': origin[8:], 'X-Forwarded-Proto': 'http',
                'X-Forwarded-For': '8.8.8.8, 10.0.0.2', 'X-Envoy-External-Address': '10.0.0.2'}
            if method == 'POST':
                headers.update(Origin=origin, **{'Content-Type': 'application/json'})
            if cookie:
                headers['Cookie'] = cookie
            # Cold measured speech/source validation shares the CI CPU with
            # native regressions; this is a test client budget, not app policy.
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=180)
            connection.request(method, route, json.dumps(data) if data is not None else None, headers)
            response = connection.getresponse()
            status, values, payload = response.status, dict(response.getheaders()), response.read()
            connection.close()
            assert code.encode() not in payload, 'SELECTION_SECRET_DISCLOSED'
            return status, values, json.loads(payload) if payload else None

        try:
            assert call('GET', '/api/health')[0] == 200
            assert call('GET', '/api/projects')[0] == 401
            assert call('POST', '/auth/login', {'password': 'wrong'})[0] == 401
            status, headers, _ = call('POST', '/auth/login', {'password': code})
            assert status == 200 and all(flag in headers['Set-Cookie'] for flag in ('Secure', 'HttpOnly', 'SameSite=Strict'))
            cookie = headers['Set-Cookie'].split(';', 1)[0]
            request = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                qa_mode=False, quality='HIGH', pace='FAST_PLUS', direction_profile='REFERENCE_MASTER',
                tts=False, subtitles=False, bgm=True, sfx=True)
            created = []
            for _ in range(2):
                status, _, item = call('POST', '/api/projects', request)
                assert status == 201, 'SELECTION_PUBLIC_CREATE_FAILED:' + str(item.get('error', {}).get('code', 'UNKNOWN'))
                plan = item['plan']
                assert plan['metadata']['infographic']['version'] == 'v022', 'SELECTION_PUBLIC_METADATA_MISSING'
                assert all(scene['infographic']['version'] == 'v022' for scene in plan['scenes']), 'SELECTION_PUBLIC_SCENE_MISSING'
                assert validate_infographic(plan)['passed'], 'SELECTION_PUBLIC_CONTRACT_FAILED'
                project = item['project']['id']
                status, _, approved = call('POST', '/api/projects/' + project + '/approve',
                    {'version': item['version'], 'plan_hash': plan['plan_hash']})
                assert status == 200 and approved['plan']['plan_hash'] == plan['plan_hash'], 'SELECTION_PUBLIC_APPROVAL_CHANGED_PLAN'
                mapped = audit_backend(approved['plan'], folder)
                created.append(dict(version=item['version'], frames=sum(scene['frame_count'] for scene in plan['scenes']),
                    infographic='v022', backend=mapped['page'], approved=True, render_requested=False))
            script = json.loads((APP / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
            status, _, item = call('POST', '/api/projects',
                dict(direction_profile='MAP_INFOGRAPHIC_PRODUCTION_V022', script_record=script))
            assert status == 201, 'SELECTION_PUBLIC_PRODUCTION_FAILED:' + str(item.get('error', {}).get('code', 'UNKNOWN'))
            plan = item['plan']
            assert validate_infographic(plan)['passed'], 'SELECTION_PUBLIC_PRODUCTION_CONTRACT_FAILED'
            assert plan['metadata']['infographic']['parent_renderer_family'] == 'production-earth-v1', 'SELECTION_PUBLIC_PRODUCTION_FAMILY_FAILED'
            project = item['project']['id']
            status, _, approved = call('POST', '/api/projects/' + project + '/approve',
                {'version': item['version'], 'plan_hash': plan['plan_hash']})
            assert status == 200 and approved['plan']['plan_hash'] == plan['plan_hash'], 'SELECTION_PUBLIC_PRODUCTION_APPROVAL_CHANGED'
            mapped = audit_backend(approved['plan'], folder)
            production = dict(infographic='v022', family='production-earth-v1', approved=True,
                scene_count=len(plan['scenes']), backend=mapped['page'],
                measured_frames=plan['metadata']['semantic_timeline']['total_frames'], render_requested=False)
            start = time.monotonic()
            while time.monotonic() - start < 61:
                assert thread.is_alive() and call('GET', '/api/health')[0] == 200
                assert call('GET', '/auth/session')[0] == 200
                time.sleep(min(2, max(.01, 61 - (time.monotonic() - start))))
            return dict(passed=True, login='PASS', health='PASS', secure_cookie='PASS',
                repeated_new_qa=created, production=production,
                persistence_seconds=round(time.monotonic() - start, 3),
                render_requested=False, physical_gpu='NOT_RUN')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            app.scheduler.close()


def run(folder):
    value, source = verify_sources()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    protected = protected_preflight(folder / 'protected-v022', require_container_assets=True)
    assert protected['passed'], 'SELECTION_PROTECTED_PREFLIGHT_FAILED'
    tests = regressions(value)
    with environment(WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION='v022'):
        smoke = gateway_selection_smoke(folder / 'public-gateway')
    report = dict(passed=True, sources=source, protected_v022=protected,
                  regressions=tests, public_gateway=smoke, physical_gpu='NOT_RUN', output_quality='NOT_RUN')
    (folder / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Selection release gate::' + json.dumps(dict(passed=True,
        unique_tests=value['unique_tests'], original_tests=1061, new_tests=len(value['new_ids']),
        protected_assets=protected['registered_asset_union_count'], public_gateway=smoke,
        physical_gpu='NOT_RUN', output_quality='NOT_RUN')), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--runtime', action='append', default=[])
    parser.add_argument('--manifest-only', action='store_true')
    parser.add_argument('--checkout', action='store_true')
    parser.add_argument('--smoke-only', action='store_true')
    parser.add_argument('--protected-only', action='store_true')
    parser.add_argument('--regressions-only', action='store_true')
    parser.add_argument('--focused-only', action='store_true')
    parser.add_argument('folder', nargs='?', default='/data/selection-preflight')
    args = parser.parse_args()
    if args.freeze:
        print(json.dumps(freeze(args.runtime)))
    elif args.manifest_only:
        print(json.dumps(verify_sources(checkout=args.checkout)[1]))
    elif args.smoke_only:
        print(json.dumps(gateway_selection_smoke(args.folder)))
    elif args.protected_only:
        protected_preflight(args.folder, require_container_assets=True)
    elif args.regressions_only:
        value, _ = verify_sources()
        regressions(value)
    elif args.focused_only:
        value, _ = verify_sources()
        focused_regressions(value)
    else:
        run(args.folder)
