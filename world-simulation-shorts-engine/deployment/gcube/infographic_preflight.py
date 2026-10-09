"""Immutable v021 admission and explicit v022 infographic admission, without GPU.

The release manifest is frozen with the source before CI. It admits exact files,
test IDs and native checks; source discovery never changes a release's targets.
CPU Canvas and collect-all results cannot establish NVIDIA or video quality.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import threading
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch


APP_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = APP_ROOT / 'deployment/gcube/infographic_release_manifest.json'
PARENT_DIGEST = 'sha256:2f68a880afdc56a5d3b9dc5ab52c2a87100316048d5d863e712654fee789a9dc'
PARENT_CORE_SHA = '6fd7e35087d3b7debdc75bb763bc5233142bec783397ba0a968b381b5fa9359b'
INDEPENDENT_IDS = {
    'proxy': (206, '679cd487d78bad7dd691d47489f0a0fa0a8c95cfacb5beeac435eab995890ada'),
    'diagnostic': (31, 'dffce04b767c5ea629b2dccbfeb767a9509e9f65658f1855f248d5c8f553fdc5'),
}
NEW_AUDITED_ASSETS = {
    'world-simulation-shorts-engine/web/infographic_adapter.js',
    'world-simulation-shorts-engine/web/render_infographic_earth.html',
}
NODE_FILES = {
    'test_infographic_v022.mjs', 'infographic_adapter.js',
    'test_story_progression_v021.mjs', 'story_progression_adapter.js',
    'test_reference_effects_v020.mjs', 'reference_effects_adapter.js',
    'event_quality_adapter.js', 'visual_quality_adapter.js',
    'scene_diagnostic_journal.mjs',
}
NODE_TYPES = {'AssertionError', 'SyntaxError', 'TypeError', 'RangeError',
              'ReferenceError', 'Error', 'URIError', 'EvalError'}


def _sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def _ids_sha(identities):
    return hashlib.sha256(('\n'.join(sorted(identities))+'\n').encode()).hexdigest()


def _local(root, name):
    assert isinstance(name, str) and name, 'INFOGRAPHIC_MANIFEST_PATH_INVALID'
    path = PurePosixPath(name)
    assert (not path.is_absolute() and '..' not in path.parts
            and '\\' not in name and str(path) == name), 'INFOGRAPHIC_MANIFEST_PATH_INVALID'
    file = root.joinpath(*path.parts)
    assert file.resolve().is_relative_to(root.resolve()), 'INFOGRAPHIC_MANIFEST_PATH_ESCAPE'
    return file


def _records(records, root, *, allow_empty=False):
    assert isinstance(records, list) and records, 'INFOGRAPHIC_MANIFEST_RECORDS_MISSING'
    names = [row['path'] for row in records]
    assert names == sorted(set(names)), 'INFOGRAPHIC_MANIFEST_RECORD_ORDER_INVALID'
    verified = []
    for row in records:
        name = row['path']
        assert re.fullmatch('[0-9a-f]{64}', row['sha256']), 'INFOGRAPHIC_MANIFEST_SHA_INVALID'
        assert type(row['size']) is int and row['size'] >= (0 if allow_empty else 1), 'INFOGRAPHIC_MANIFEST_SIZE_INVALID'
        file = _local(root, name)
        assert file.is_file() and os.access(file, os.R_OK), 'INFOGRAPHIC_RELEASE_FILE_MISSING:'+name
        assert file.stat().st_size == row['size'] and _sha(file) == row['sha256'], 'INFOGRAPHIC_RELEASE_FILE_CHANGED:'+name
        verified.append(dict(path=name, size=row['size'], sha256=row['sha256'], readable=True))
    return verified


def load_manifest():
    assert MANIFEST.is_file(), 'INFOGRAPHIC_FROZEN_RELEASE_MANIFEST_MISSING'
    value = json.loads(MANIFEST.read_text())
    assert value['version'] == 'v022' and value['status'] == 'FROZEN', 'INFOGRAPHIC_RELEASE_MANIFEST_NOT_FROZEN'
    assert value['parent_digest'] == PARENT_DIGEST, 'INFOGRAPHIC_RELEASE_PARENT_CHANGED'
    assert value['release_tag_prefix'] == 'gcube-v022-map-infographic-', 'INFOGRAPHIC_RELEASE_TAG_INVALID'
    parent = value['tests']['inherited_ids']
    added = value['tests']['new_ids']
    assert parent == sorted(set(parent)) and len(parent) == 767, 'INFOGRAPHIC_PARENT_TEST_IDS_INVALID'
    assert _ids_sha(parent) == PARENT_CORE_SHA, 'INFOGRAPHIC_PARENT_TEST_IDS_CHANGED'
    assert added == sorted(set(added)) and added and not set(parent) & set(added), 'INFOGRAPHIC_NEW_TEST_IDS_INVALID'
    assert _ids_sha(added) == value['tests']['new_ids_sha256'], 'INFOGRAPHIC_NEW_TEST_IDS_CHANGED'
    assert value['tests']['new_count'] == len(added), 'INFOGRAPHIC_NEW_TEST_COUNT_INVALID'
    assert value['tests']['unique_release_count'] == 1004+len(added), 'INFOGRAPHIC_RELEASE_TEST_COUNT_INVALID'
    unique = set(parent+added)
    for group, (count, digest) in INDEPENDENT_IDS.items():
        identities = value['tests'][group+'_ids']
        assert identities == sorted(set(identities)) and len(identities) == count, 'INFOGRAPHIC_INDEPENDENT_TEST_IDS_INVALID'
        assert _ids_sha(identities) == digest, 'INFOGRAPHIC_INDEPENDENT_TEST_IDS_CHANGED'
        assert not unique & set(identities), 'INFOGRAPHIC_RELEASE_TEST_GROUPS_OVERLAP'
        unique.update(identities)
    assert len(unique) == value['tests']['unique_release_count'], 'INFOGRAPHIC_RELEASE_TEST_UNIQUENESS_INVALID'
    assert type(value['native_checks']) is int and value['native_checks'] > 0, 'INFOGRAPHIC_NATIVE_INVENTORY_MISSING'
    assert type(value['production_native_checks']) is int and value['production_native_checks'] > 0, 'INFOGRAPHIC_PRODUCTION_NATIVE_INVENTORY_MISSING'
    assert type(value['canvas_checks']) is int and value['canvas_checks'] > 0, 'INFOGRAPHIC_CANVAS_INVENTORY_MISSING'
    assert type(value['canvas_snapshots']) is int and value['canvas_snapshots'] > 0, 'INFOGRAPHIC_CANVAS_SNAPSHOT_INVENTORY_MISSING'
    return value


def verify_source_manifest(*, require_checkout=False):
    manifest = load_manifest()
    runtime = _records(manifest['runtime_records'], APP_ROOT)
    frozen = _records(manifest['frozen_parent_records'], APP_ROOT)
    if require_checkout:
        _records(manifest['checkout_records'], APP_ROOT.parent, allow_empty=True)
    http = manifest['http_assets']
    assert isinstance(http, list) and http, 'INFOGRAPHIC_HTTP_INVENTORY_MISSING'
    names = [row['path'] for row in http]
    assert names == sorted(set(names)), 'INFOGRAPHIC_HTTP_INVENTORY_INVALID'
    for row in http:
        assert row['path'].startswith('web/'), 'INFOGRAPHIC_HTTP_ASSET_OUTSIDE_WEB'
        assert row['url'] == '/static/'+row['path'][4:], 'INFOGRAPHIC_HTTP_URL_INVALID'
        _records([dict(path=row['path'], size=row['size'], sha256=row['sha256'])], APP_ROOT)
    assert {row['path'] for row in runtime} >= {
        'engine/infographic_backend.py', 'engine/infographic_contract.py',
        'engine/qa_planner.py', 'engine/pipeline_stability.py',
        'web/infographic_adapter.js', 'web/render_infographic_earth.html',
        'tools/test_infographic_v022.mjs', 'deployment/gcube/infographic_preflight.py',
    }, 'INFOGRAPHIC_REQUIRED_OVERLAY_MISSING'
    return dict(passed=True, manifest_sha256=_sha(MANIFEST), runtime_records=runtime,
                frozen_parent_records=frozen, checkout_verified=require_checkout,
                new_tests=manifest['tests']['new_count'],
                unique_release_tests=manifest['tests']['unique_release_count'])


def identifiers(suite):
    values = []
    for test in suite:
        values.extend(identifiers(test) if isinstance(test, unittest.TestSuite) else [test.id()])
    return sorted(values)


def verify_test_inventory(expected):
    manifest = load_manifest()
    inherited = manifest['tests']['inherited_ids']
    added = manifest['tests']['new_ids']
    assert expected == sorted(set(expected)), 'INFOGRAPHIC_DUPLICATE_TEST_IDS'
    assert expected == sorted(inherited+added), 'INFOGRAPHIC_TEST_INVENTORY_CHANGED'
    return dict(inherited_ids=inherited, new_ids=added,
                unique_release_count=manifest['tests']['unique_release_count'])


class SafeResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed = []
        self.safe_failures = []

    def startTest(self, test):
        self.executed.append(test.id())
        super().startTest(test)

    def _record(self, test, error):
        if len(self.safe_failures) >= 25:
            return
        locations = [dict(file=Path(frame.filename).name, line=frame.lineno)
                     for frame in traceback.extract_tb(error[2])
                     if Path(frame.filename).name.startswith('test_')
                     and Path(frame.filename).suffix == '.py'][-6:]
        message = str(error[1])
        bounded = message[:8192]+'\n'+message[-65536:]
        node = []
        for filename in sorted(NODE_FILES):
            for match in re.finditer(re.escape(filename)+r':(\d+)(?::\d+)?', bounded):
                location = dict(file=filename, line=int(match.group(1)))
                if location not in node:
                    node.append(location)
        types = sorted(set(re.findall(r'\b(AssertionError|SyntaxError|TypeError|RangeError|ReferenceError|Error|URIError|EvalError)(?: \[[A-Z][A-Z0-9_]+\])?:', bounded)) & NODE_TYPES)
        codes = sorted(set(re.findall(r'\b(?:ERR_ASSERTION|INFOGRAPHIC_[A-Z0-9_]+|SEMANTIC_TIMELINE_[A-Z0-9_]+|REFERENCE_EFFECTS_[A-Z0-9_]+|STORY_PROGRESSION_[A-Z0-9_]+)\b', bounded)))[:12]
        match = re.search(r'(?:^|AssertionError:\s*)(-?\d+)\s*!=\s*0(?:\s|:|$)', message[:8192])
        self.safe_failures.append(dict(test_id=test.id().split(' (', 1)[0],
            exception_type=error[0].__name__, python_test_locations=locations,
            node_locations=node[:12], node_error_types=types, node_error_codes=codes,
            node_exit_code=int(match.group(1)) if match else None))

    def addFailure(self, test, error):
        self._record(test, error)
        super().addFailure(test, error)

    def addError(self, test, error):
        self._record(test, error)
        super().addError(test, error)

    def addSubTest(self, test, subtest, error):
        if error is not None:
            self._record(test, error)
        super().addSubTest(test, subtest, error)


def run_isolated_tests():
    manifest = load_manifest()
    loader = unittest.TestLoader()
    complete = loader.discover('tests')
    assert not loader.errors, 'INFOGRAPHIC_TEST_IMPORT_FAILURE'
    verify_test_inventory(identifiers(complete))
    selected = set(manifest['tests']['new_ids'])

    def subset(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from subset(test)
            elif test.id() in selected:
                yield test

    suite = unittest.TestSuite(subset(complete))
    expected = identifiers(suite)
    assert expected == manifest['tests']['new_ids'], 'INFOGRAPHIC_ISOLATED_TEST_INVENTORY_CHANGED'
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=1, resultclass=SafeResult).run(suite)
    print('::notice title=Isolated v022 regressions::'+json.dumps(dict(tests=result.testsRun,
          failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
          duplicate_execution_excluded_from_unique_count=True)))
    print('::notice title=Safe v022 failure metadata::'+json.dumps(result.safe_failures))
    assert sorted(result.executed) == expected and result.testsRun == len(expected), 'INFOGRAPHIC_TEST_EXECUTION_INCOMPLETE'
    assert result.wasSuccessful() and not result.skipped, 'INFOGRAPHIC_ISOLATED_TEST_FAILURE'


@contextmanager
def inherited_asset_view(audit):
    parent = {**audit, 'assets': [row for row in audit['assets']
                               if row['path'] not in NEW_AUDITED_ASSETS]}
    with patch('deployment.gcube.asset_audit.audit_assets', lambda: deepcopy(parent)):
        yield


def audit_parent_assets(require_container_assets):
    from deployment.gcube.asset_audit import audit_assets
    from deployment.gcube.story_progression_preflight import audit_parent_assets as parent_audit
    audit = audit_assets()
    assert audit['passed'], 'INFOGRAPHIC_CONTAINER_ASSET_MISSING'
    added = [row for row in audit['assets'] if row['path'] in NEW_AUDITED_ASSETS]
    assert {row['path'] for row in added} == NEW_AUDITED_ASSETS, 'INFOGRAPHIC_NEW_RENDER_ASSET_MISSING'
    expected = 83 if require_container_assets else 74
    assert len(audit['assets']) == expected, 'INFOGRAPHIC_INHERITED_AUDITOR_INVENTORY_CHANGED'
    with inherited_asset_view(audit):
        inherited, _ = parent_audit(require_container_assets)
    assert inherited['total_asset_count'] == expected-2, 'INFOGRAPHIC_PARENT_ASSET_INVENTORY_CHANGED'
    return dict(passed=True, parent_auditor_count=expected-2,
                inherited_auditor_count=expected, added_render_resources=2,
                inherited_v021_assets=inherited, assets=audit['assets']), audit


def audit_served_assets():
    from deployment.mobile_server import InternalHandler
    manifest = load_manifest()
    server = ThreadingHTTPServer(('127.0.0.1', 0), InternalHandler)
    server.application = SimpleNamespace(store=None)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    records = []
    try:
        for row in manifest['http_assets']:
            expected = _local(APP_ROOT, row['path']).read_bytes()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            connection.request('GET', row['url'])
            response = connection.getresponse()
            payload = response.read()
            connection.close()
            assert response.status == 200 and payload == expected, 'INFOGRAPHIC_STATIC_SERVING_FAILED:'+row['path']
            assert len(payload) == row['size'] and hashlib.sha256(payload).hexdigest() == row['sha256'], 'INFOGRAPHIC_STATIC_HASH_FAILED:'+row['path']
            records.append(dict(url=row['url'], status=response.status, identical=True,
                                sha256=row['sha256'], size=len(payload),
                                content_type=response.getheader('Content-Type')))
        return dict(passed=True, assets=records,
                    scope='Actual inherited readonly HTTP handler; no owner secret or GPU render request')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)


def audit_registry_assets():
    from engine.infographic_contract import load_registry, validate_registry, asset_records, _contract
    registry = load_registry()
    validation = validate_registry(registry, require_assets=True)
    assert validation['passed'], 'INFOGRAPHIC_VERIFIED_REGISTRY_FAILED'
    records = asset_records()
    assert records and len(records) == len({row['file'] for row in records}), 'INFOGRAPHIC_REGISTRY_ASSET_INVENTORY_INVALID'
    checked = []
    for row in records:
        file = _local(APP_ROOT, row['file'])
        assert file.is_file() and file.stat().st_size == row['bytes'] > 0, 'INFOGRAPHIC_REGISTRY_ASSET_MISSING:'+row['file']
        assert _sha(file) == row['sha256'], 'INFOGRAPHIC_REGISTRY_ASSET_HASH_INVALID:'+row['file']
        checked.append(dict(path=row['file'], size=row['bytes'], sha256=row['sha256'], url=row['url']))
    for file in (APP_ROOT/'data/infographic/v022').rglob('*'):
        if file.is_file():
            served = APP_ROOT/'web/infographic/v022'/file.relative_to(APP_ROOT/'data/infographic/v022')
            assert served.is_file() and served.read_bytes() == file.read_bytes(), 'INFOGRAPHIC_REGISTRY_MIRROR_INVALID'
    geometry = {row['id']: row for row in registry['geometries']}
    for name in ('CANAL_SUEZ_RIVER_NE10M', 'CANAL_SUEZ_LAKE_NE10M'):
        row = geometry[name]
        assert row['geometry_type'] == 'MultiLineString', 'INFOGRAPHIC_CANAL_TYPE_INVALID'
        assert row['scale']['denominator'] == 10000000, 'INFOGRAPHIC_CANAL_SCALE_INVALID'
        assert row['source_feature_id'] in {'209River', '209Lake Centerline'}, 'INFOGRAPHIC_CANAL_SOURCE_FEATURE_INVALID'
    assert geometry['LOCATION_SUEZ_CANAL']['geometry_type'] == 'Point', 'INFOGRAPHIC_WAYPOINT_PROMOTED_TO_GEOMETRY'
    bold = APP_ROOT/'web/fonts/NotoSansCJKkr-Bold.otf'
    provenance = json.loads((APP_ROOT/'web/fonts/BOLD_SOURCE_v022.json').read_text())
    assert _sha(bold) == provenance['sha256'] == 'da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0', 'INFOGRAPHIC_BOLD_FONT_HASH_INVALID'
    assert bold.stat().st_size == provenance['size_bytes'] and provenance['weight'] == 700, 'INFOGRAPHIC_FONT_SOURCE_INVALID'
    license_file = _local(APP_ROOT/'web/fonts', provenance['license_file'])
    assert _sha(license_file) == provenance['license_sha256'] and provenance['license'] == 'SIL OFL 1.1', 'INFOGRAPHIC_FONT_LICENSE_INVALID'
    return dict(passed=True, registry=validation, source_contract=_contract(), assets=checked,
                geometry_count=len(geometry), font=dict(file='web/fonts/NotoSansCJKkr-Bold.otf',
                    sha256=provenance['sha256'], weight=700, license=provenance['license']),
                canal_scope='Native generalized 1:10,000,000 centerline parts; gaps preserved; no bank, traffic or obstruction geometry',
                physical_gpu='NOT_RUN')


def without_infographic(plan):
    plain = deepcopy(plan)
    plain.pop('gate', None)
    plain.get('metadata', {}).pop('infographic', None)
    for scene in plain.get('scenes', []):
        scene.pop('infographic', None)
    return plain


def audit_backend(plan, folder):
    from engine.infographic_backend import infographic_command, InfographicBackend
    from urllib.parse import urlsplit
    scene = plan['scenes'][0]
    path = Path(folder)/'selected-scene.json'
    path.write_text(json.dumps(scene, ensure_ascii=False, indent=2))
    command = ['node', str(APP_ROOT/'tools/render_production_scene.mjs'), '--scene-json', str(path),
               '--url', 'http://127.0.0.1/static/render_production_earth.html']
    mapped = infographic_command(command)
    index = mapped.index('--url')+1
    assert urlsplit(mapped[index]).path == '/static/render_infographic_earth.html', 'INFOGRAPHIC_RENDER_PAGE_NOT_SELECTED'
    stripped = list(mapped)
    stripped[index] = command[command.index('--url')+1]
    assert stripped == command, 'INFOGRAPHIC_RENDER_COMMAND_OTHER_ARGS_CHANGED'
    with patch('engine.backends.CPULocalBackend.run', lambda self, values, cwd, progress: values):
        assert InfographicBackend().run(command, APP_ROOT, lambda event: None) == mapped, 'INFOGRAPHIC_GPU_TRANSPORT_CHANGED'
    return dict(passed=True, page='/static/render_infographic_earth.html',
                transport='Unchanged CPULocalBackend and strict GPU worker; only selected URL changes')


def _safe_canvas_diagnostic(stdout):
    """Admit only known test-only Canvas metadata; never forward raw output."""
    if not isinstance(stdout, str) or len(stdout) > 16384:
        return None
    try:
        payload = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get('passed') is not False:
        return None
    record = payload.get('diagnostic')
    if not isinstance(record, dict):
        return None
    phases = {'BROWSER_LAUNCH', 'PAGE_CREATE', 'PAGE_LOAD', 'BROWSER_EVALUATION',
              'SNAPSHOT_WRITE', 'METRICS_WRITE'}
    types = {'Error', 'TypeError', 'SyntaxError', 'ReferenceError', 'RangeError',
             'TimeoutError', 'TargetClosedError'}
    checks = {
        'COUNTRY_EGY_REGISTRY_PRESENT', 'COUNTRY_EGY_REAL_POLYGON_VISIBLE',
        'COUNTRY_SGP_REGISTRY_PRESENT', 'COUNTRY_SGP_REAL_POLYGON_VISIBLE',
        'POLYGON_HOLE_EMPTY_REAL_PIXELS', 'MULTIPOLYGON_ISLANDS_NO_BRIDGE',
        'ANTIMERIDIAN_FRONT_POLYGON_FILLED', 'ANTIMERIDIAN_BACKSIDE_NO_FALSE_CHORD',
        'HORIZON_PARTIAL_POLYGON_CLIPPED', 'HORIZON_BACKSIDE_ENTIRELY_HIDDEN',
        'LINE4PX_ACTUAL_PIXEL_WIDTH', 'FOUR_ROLES_MEASURED_WITH_ACTUAL_FONTS',
        'LABEL_COLLISION_RESOLVED', 'CJK_ENGLISH_NUMERIC_REAL_INK',
        'REAL_BOLD_DIFFERS_FROM_REGULAR', 'GRAPHEME_REVEAL_DOES_NOT_SPLIT_COMBINING',
    }
    codes = {
        'UNCLASSIFIED', 'CHECK_FAILED', 'EXECUTABLE_MISSING',
        'SHARED_LIBRARY_MISSING', 'SANDBOX_CONFIGURATION',
        'CRASHPAD_DATABASE_REQUIRED', 'PERMISSION_DENIED', 'TIMEOUT',
        'BROWSER_CLOSED_BEFORE_READY', 'ACTUAL_FONT_LOAD_FAILED',
        'INFOGRAPHIC_GEOMETRY_SOURCE_INVALID', 'INFOGRAPHIC_GEOMETRY_COORDINATE_INVALID',
        'INFOGRAPHIC_POLYGON_RING_INVALID', 'INFOGRAPHIC_POLYGON_AREA_INVALID',
        'INFOGRAPHIC_POLYGON_TRIANGULATION_FAILED', 'INFOGRAPHIC_AMBIGUOUS_ANTIPODAL_LINE',
        'INFOGRAPHIC_GRAPHEME_SEGMENTER_UNAVAILABLE', 'INFOGRAPHIC_TEXT_SOURCE_INVALID',
        'INFOGRAPHIC_LABEL_ROLE_INVALID', 'INFOGRAPHIC_UNVERIFIED_FONT_WEIGHT',
        'INFOGRAPHIC_TEXT_LINE_LIMIT_INVALID', 'INFOGRAPHIC_TEXT_WRAPPING_SOURCE_INVALID',
    }
    libraries = {
        'libX11.so.6', 'libX11-xcb.so.1', 'libXcomposite.so.1', 'libXdamage.so.1',
        'libXext.so.6', 'libXfixes.so.3', 'libXrandr.so.2', 'libXss.so.1',
        'libXtst.so.6', 'libxcb.so.1', 'libatk-1.0.so.0', 'libatk-bridge-2.0.so.0',
        'libatspi.so.0', 'libasound.so.2', 'libcairo.so.2', 'libcups.so.2',
        'libdbus-1.so.3', 'libdrm.so.2', 'libexpat.so.1', 'libfontconfig.so.1',
        'libfreetype.so.6', 'libgbm.so.1', 'libglib-2.0.so.0', 'libgobject-2.0.so.0',
        'libgtk-3.so.0', 'libnspr4.so', 'libnss3.so', 'libnssutil3.so',
        'libpango-1.0.so.0', 'libpangocairo-1.0.so.0', 'libsmime3.so', 'libvulkan.so.1',
    }
    signals = {'SIGABRT', 'SIGTRAP', 'SIGSEGV', 'SIGILL', 'SIGBUS', 'SIGKILL', 'SIGTERM'}
    filenames = {'test_infographic_v022.mjs', 'infographic_adapter.js',
                 'reference_effects_adapter.js', 'browser_evaluation'}
    def known(name, allowed, fallback=None):
        value = record.get(name)
        return value if isinstance(value, str) and value in allowed else fallback
    locations = []
    values = record.get('locations')
    for value in values[:8] if isinstance(values, list) else []:
        if not isinstance(value, dict):
            continue
        filename, line, column = value.get('file'), value.get('line'), value.get('column')
        if (isinstance(filename, str) and filename in filenames
                and type(line) is int and 0 < line < 100000
                and type(column) is int and 0 < column < 100000):
            locations.append(dict(file=filename, line=line, column=column))
    exitcode = record.get('process_exit_code')
    return dict(phase=known('phase', phases, 'UNKNOWN'),
                exception_type=known('exception_type', types, 'OTHER'),
                code=known('code', codes, 'UNCLASSIFIED'),
                check=known('check', checks), shared_library=known('shared_library', libraries),
                process_signal=known('process_signal', signals),
                process_exit_code=exitcode if type(exitcode) is int and 0 <= exitcode <= 255 else None,
                locations=locations, raw_details='OMITTED', GPU='NOT_RUN')


def call_native(arguments):
    result = subprocess.run(['node', 'tools/test_infographic_v022.mjs', *map(str, arguments)],
        cwd=APP_ROOT, capture_output=True, text=True, check=False, timeout=240)
    if result.returncode:
        bounded = result.stderr[:8192]+'\n'+result.stderr[-65536:]
        locations = []
        for filename in sorted(NODE_FILES):
            for match in re.finditer(re.escape(filename)+r':(\d+)(?::\d+)?', bounded):
                row = dict(file=filename, line=int(match.group(1)))
                if row not in locations:
                    locations.append(row)
        types = sorted(set(re.findall(r'\b(AssertionError|SyntaxError|TypeError|RangeError|ReferenceError|Error|URIError|EvalError)(?: \[[A-Z][A-Z0-9_]+\])?:', bounded)) & NODE_TYPES)
        codes = sorted(set(re.findall(r'\b(?:ERR_ASSERTION|INFOGRAPHIC_[A-Z0-9_]+|CANVAS_CHECK_FAILED|ACTUAL_FONT_LOAD_FAILED)\b', bounded)))[:12]
        metadata = dict(node_exit_code=result.returncode, node_locations=locations[:12],
                        node_error_types=types, node_error_codes=codes)
        diagnostic = _safe_canvas_diagnostic(result.stdout)
        if diagnostic is not None:
            metadata['canvas_diagnostic'] = diagnostic
        print('::error title=Safe infographic native failure::'+json.dumps(metadata), flush=True)
        raise RuntimeError('INFOGRAPHIC_NATIVE_COMMAND_FAILED')
    return json.loads(result.stdout)


def audit_native_adapter(plan, folder, *, production=False):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    expected_checks = manifest['production_native_checks'] if production else manifest['native_checks']
    results = []
    scenes = plan['scenes']
    source = folder/'PLAN.json'
    source.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    aggregate = call_native([source, folder])
    if len(scenes) > 1:
        assert aggregate['passed'] and aggregate['scene_count'] == len(scenes), 'INFOGRAPHIC_NATIVE_SCENE_COUNT_INVALID'
        assert aggregate['frames'] == sum(scene['frame_count'] for scene in scenes), 'INFOGRAPHIC_NATIVE_TOTAL_FRAME_COUNT_INVALID'
        assert aggregate['checks'] == expected_checks*len(scenes), 'INFOGRAPHIC_NATIVE_TOTAL_CHECK_COUNT_INVALID'
        reports = aggregate['scene_results']
        assert [row['scene_id'] for row in reports] == [scene['scene_id'] for scene in scenes], 'INFOGRAPHIC_NATIVE_SCENE_IDS_CHANGED'
    else:
        reports = [aggregate]
    for scene, report in zip(scenes, reports):
        scene_folder = folder/scene['scene_id'] if len(scenes) > 1 else folder
        assert report['passed'] and report['checks'] == expected_checks, 'INFOGRAPHIC_NATIVE_CHECK_INVENTORY_CHANGED'
        assert report['frames'] == scene['frame_count'], 'INFOGRAPHIC_NATIVE_FRAME_COUNT_INVALID'
        assert all(report[key] == 'UNCHANGED' for key in ('camera_trajectory', 'material', 'wide', 'overlay_off', 'audio')), 'INFOGRAPHIC_PARENT_RENDER_CONTRACT_CHANGED'
        assert report['source_scene_immutable'] and report['actual_draw_commands'] == 'EXECUTED', 'INFOGRAPHIC_NATIVE_OVERLAY_NOT_EXECUTED'
        assert report['parent_overlay_duplicate_labels'] == 'SUPPRESSED_BY_SINGLE_OWNER', 'INFOGRAPHIC_DUPLICATE_TEXT_OWNER'
        assert report['primary_motion_effect_peak'] <= 1, 'INFOGRAPHIC_PRIMARY_EFFECT_CONFLICT'
        assert report['added_sfx'] == report['added_routes'] == report['added_entities'] == 0, 'INFOGRAPHIC_UNSUPPORTED_STORY_ADDITION'
        if production:
            material = report['regional_lod']
            assert material['GPU'] == 'NOT_RUN', 'INFOGRAPHIC_REGIONAL_MEMORY_SCOPE_INVALID'
            if scene['regional_lod']['selected_regions']:
                atlas = APP_ROOT/'web/earth-detail/v018/manifest.json'
                records = json.loads(atlas.read_text())['textures']
                assert material['status'] == 'VERIFIED_EXISTING_REGIONAL_MATERIAL', 'INFOGRAPHIC_VERIFIED_REGIONAL_MATERIAL_NOT_USED'
                assert material['texture_uploads'] == report['additional_texture_uploads'] == len(records) == 4, 'INFOGRAPHIC_REGIONAL_TEXTURE_BUDGET_CHANGED'
                assert material['source_manifest_sha256'] == _sha(atlas), 'INFOGRAPHIC_REGIONAL_SOURCE_CHANGED'
                assert material['source_bytes'] == sum(row['bytes'] for row in records), 'INFOGRAPHIC_REGIONAL_SOURCE_BUDGET_INVALID'
                decoded = sum(row['width']*row['height']*4 for row in records)
                assert material['decoded_rgba_bytes'] == decoded, 'INFOGRAPHIC_REGIONAL_DECODE_BUDGET_INVALID'
                assert material['estimated_texture_storage_bytes'] == (decoded*4+2)//3, 'INFOGRAPHIC_REGIONAL_MEMORY_ESTIMATE_INVALID'
                assert material['covered_regions'] == [row['region_id'] for row in scene['regional_lod']['selected_regions']], 'INFOGRAPHIC_REGIONAL_SELECTION_CHANGED'
            else:
                assert material['status'] == 'NO_LOCAL_LOD' and material['texture_uploads'] == report['additional_texture_uploads'] == 0, 'INFOGRAPHIC_UNSOURCED_REGIONAL_MATERIAL'
        else:
            assert report['additional_texture_uploads'] == 0, 'INFOGRAPHIC_QA_TEXTURE_UPLOADS_CHANGED'
        assert report['changed_overlay_frames'] > 0 and report['marker_persistent_frames'] > 0, 'INFOGRAPHIC_OVERLAY_OR_MARKER_NOT_EXERCISED'
        selection = scene['infographic']
        geometry_types = {row['id']: row['geometry_type'] for row in selection['geometries']}
        declared_refs = {row['geometry_ref'] for row in selection['geometry_layers']}
        assert set(report['geometry_state_coverage']) == declared_refs, 'INFOGRAPHIC_DECLARED_GEOMETRY_COVERAGE_CHANGED'
        for name in declared_refs:
            assert geometry_types.get(name) in {'Polygon', 'MultiPolygon', 'LineString', 'MultiLineString'}, 'INFOGRAPHIC_DECLARED_NATIVE_GEOMETRY_INVALID'
            states = {row['state_after'] for row in selection['geometry_layers'] if row['geometry_ref'] == name}
            assert states <= set(report['geometry_state_coverage'][name]), 'INFOGRAPHIC_DECLARED_GEOMETRY_STATE_OMITTED'
        assert {row['id'] for row in selection['markers']} <= set(report['marker_coverage']), 'INFOGRAPHIC_DECLARED_POINT_MARKER_OMITTED'
        assert {row['id'] for row in selection['labels']} <= set(report['text_coverage']), 'INFOGRAPHIC_DECLARED_TEXT_OMITTED'
        assert report['text_coverage'] and not report['layout_omissions'], 'INFOGRAPHIC_STATE_OR_TEXT_OMITTED'
        assert report['GPU'] == 'NOT_RUN' and report['shader_compile'] == 'NVIDIA_NOT_RUN' and report['pixel_quality'] == 'NOT_RUN', 'INFOGRAPHIC_CPU_CONTRACT_MISREPORTED'
        assert report['request_order_regression']['request_identity'] == 'SAME_URL_MULTISET_AND_COUNTS', 'INFOGRAPHIC_RESOURCE_INVENTORY_CHANGED'
        if not production:
            assert report['frames'] == 720 and report['request_order_regression']['completion_order_reversed'] is True, 'INFOGRAPHIC_720_OR_ASYNC_RESOURCE_ORDER_NOT_EXERCISED'
        receipt = json.loads((scene_folder/'frame-receipts.json').read_text())
        assert len(receipt['frames']) == scene['frame_count'], 'INFOGRAPHIC_FRAME_RECEIPTS_INCOMPLETE'
        assert [row['frame'] for row in receipt['frames']] == list(range(scene['frame_count'])), 'INFOGRAPHIC_FRAME_RECEIPTS_GAP_OR_OVERLAP'
        results.append(dict(scene_id=scene['scene_id'], report=report))
    assert sum(row['report']['frames'] for row in results) == sum(scene['frame_count'] for scene in scenes), 'INFOGRAPHIC_NATIVE_SCENE_COVERAGE_INCOMPLETE'
    return dict(passed=True, scenes=results,
                frames=sum(row['report']['frames'] for row in results), physical_gpu='NOT_RUN')


def audit_canvas_pixels(folder):
    folder = Path(folder)
    summary = call_native(['--canvas-snapshots', folder])
    manifest = load_manifest()
    assert summary['status'] == 'PASS' and summary['checks'] == manifest['canvas_checks'], 'INFOGRAPHIC_CANVAS_CHECK_INVENTORY_CHANGED'
    assert summary['snapshots'] == manifest['canvas_snapshots'] and summary['gpu_result'] == 'NOT_RUN', 'INFOGRAPHIC_CANVAS_SCOPE_INVALID'
    metrics = json.loads((folder/'metrics.json').read_text())
    assert metrics['fail'] == 0 and metrics['total_pass'] == len(metrics['checks']) == manifest['canvas_checks'], 'INFOGRAPHIC_CANVAS_PIXEL_CHECK_FAILED'
    assert all(row['status'] == 'PASS' for row in metrics['checks']), 'INFOGRAPHIC_CANVAS_PIXEL_CHECK_INCOMPLETE'
    assert metrics['gpu_result'] == 'NOT_RUN' and metrics['production_scene'] is False, 'INFOGRAPHIC_CANVAS_MISREPORTED_AS_PRODUCTION'
    assert len(metrics['snapshots']) == manifest['canvas_snapshots'], 'INFOGRAPHIC_CANVAS_CAPTURE_INCOMPLETE'
    for row in metrics['snapshots']:
        file = _local(folder, row['file'])
        assert file.is_file() and file.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n', 'INFOGRAPHIC_CANVAS_CAPTURE_INVALID'
        assert _sha(file) == row['sha256'], 'INFOGRAPHIC_CANVAS_CAPTURE_HASH_INVALID'
    weights = {row['weight'] for row in metrics['font_face_status'] if row['status'] == 'loaded'}
    assert weights >= {'400', '700'}, 'INFOGRAPHIC_ACTUAL_FONT_FACES_NOT_LOADED'
    return dict(passed=True, summary=summary, metrics=metrics,
                scope='CPU Chromium Canvas2D pixel, topology and actual font measurements; NVIDIA and production map MP4 NOT_RUN')


def audit_selected_qa(baseline, folder):
    from deployment.gcube.event_quality_preflight import selected_environment
    from deployment.gcube.reference_effects_preflight import REQUEST, pose_records
    from deployment.gcube.framegrid_preflight import check
    from engine.infographic_planner import parent_qa_plan, generate_infographic_qa
    from engine.infographic_contract import (prepare_infographic, validate_infographic,
        project_renderer_version, renderer_version)
    from engine import story_progression
    from engine.qa_planner import generate_deployment_plan
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    parent = parent_qa_plan()
    assert without_infographic(parent) == without_infographic(baseline), 'INFOGRAPHIC_QA_PARENT_PLAN_CHANGED'
    original = deepcopy(parent)
    off = prepare_infographic(parent, enabled=False)
    assert off == original and parent == original and off is not parent, 'INFOGRAPHIC_OFF_PLAN_CHANGED'
    assert generate_infographic_qa({'map_infographic': False}) == original, 'INFOGRAPHIC_OFF_BUILDER_CHANGED'
    assert project_renderer_version(off) == story_progression.project_renderer_version(parent), 'INFOGRAPHIC_OFF_CACHE_CHANGED'
    assert all(renderer_version(scene) == story_progression.renderer_version(old)
               for scene, old in zip(off['scenes'], parent['scenes'])), 'INFOGRAPHIC_OFF_SCENE_CACHE_CHANGED'
    selected = generate_infographic_qa()
    assert validate_infographic(selected)['passed'], 'INFOGRAPHIC_QA_PLAN_INVALID'
    assert parent == original and without_infographic(selected) == without_infographic(parent), 'INFOGRAPHIC_QA_UNRELATED_FIELDS_CHANGED'
    assert sum(scene['frame_count'] for scene in selected['scenes']) == 720, 'INFOGRAPHIC_QA_FRAME_GRID_CHANGED'
    events = [event for scene in selected['scenes'] for event in scene['infographic']['events']]
    assert events and any(event['target_geometry_refs'] for event in events), 'INFOGRAPHIC_QA_GEOMETRY_NOT_EXERCISED'
    assert any(scene['infographic']['markers'] for scene in selected['scenes']), 'INFOGRAPHIC_QA_PERSISTENT_MARKER_NOT_EXERCISED'
    assert any(scene['infographic']['labels'] for scene in selected['scenes']), 'INFOGRAPHIC_QA_SHARED_LAYOUT_NOT_EXERCISED'
    for old, new in zip(off['scenes'], selected['scenes']):
        for name in ('sound_events', 'reference_effects', 'event_quality', 'visual_quality',
                     'second_event_camera', 'camera_start', 'camera_end', 'visual_events',
                     'labels', 'text_events', 'routes', 'entities', 'story_progression'):
            assert old.get(name) == new.get(name), 'INFOGRAPHIC_INHERITED_SCENE_FIELD_CHANGED:'+name
    (folder/'PLAN.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2))
    (folder/'PLAN_OFF.json').write_text(json.dumps(off, ensure_ascii=False, indent=2))
    on_poses = check(selected, folder/'native-on')
    off_poses = check(off, folder/'native-off')
    assert on_poses['passed'] and off_poses['passed'], 'INFOGRAPHIC_NATIVE_COLLECT_ALL_FAILED'
    assert on_poses['gpu_draw'] == off_poses['gpu_draw'] == 'NOT_RUN', 'INFOGRAPHIC_NATIVE_MISREPORTED_AS_GPU'
    assert len(pose_records(on_poses)) == len(pose_records(off_poses)) == 720, 'INFOGRAPHIC_CAMERA_POSE_COUNT_INVALID'
    assert pose_records(on_poses) == pose_records(off_poses), 'INFOGRAPHIC_CAMERA_POSES_CHANGED'
    with selected_environment(WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION='legacy'):
        legacy = generate_deployment_plan(deepcopy(REQUEST))
    assert without_infographic(legacy) == without_infographic(baseline), 'INFOGRAPHIC_LEGACY_DEFAULT_CHANGED'
    with selected_environment(WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION='v022'):
        current = generate_deployment_plan(deepcopy(REQUEST))
    assert without_infographic(current) == without_infographic(selected), 'INFOGRAPHIC_DEFAULT_ON_PARENT_CHANGED'
    assert validate_infographic(current)['passed'], 'INFOGRAPHIC_DEFAULT_ON_SELECTION_INVALID'
    backend = audit_backend(selected, folder)
    adapter = audit_native_adapter(selected, folder/'adapter')
    return dict(passed=True, plan=selected, off_exact_v021=True, unrelated_fields_unchanged=True,
                camera_pose_count=720, camera_trajectory='UNCHANGED', backend=backend,
                adapter_contract=adapter,
                native_collect_all_on=on_poses, native_collect_all_off=off_poses,
                audio='Exact v021 QA accents preserved; no TTS or added SFX', physical_gpu='NOT_RUN')


def production_script():
    """Authored source-backed geography fixture; no closure or traffic claim."""
    first = 'The map shows Egypt.'
    second = 'Singapore is shown for geographic context.'
    text = first+' '+second
    definitions = []
    events = []
    claims = []
    for index, (country, begin, end, sentence) in enumerate((
            ('EGY', 0, len(first), first),
            ('SGP', len(first)+1, len(text), second)), 1):
        segment, event, claim = f'MEASURED_{index}', f'CONTEXT_{index}', f'GEOGRAPHY_{index}'
        label = 'Egypt' if country == 'EGY' else 'Singapore'
        definitions.append(dict(id=segment, start_char=begin, end_char=end,
            claim_ids=[claim], source_ids=['natural_earth_countries'],
            target_ids=['COUNTRY_'+country], event_ids=[event]))
        claims.append(dict(id=claim, text=sentence, status='FACT',
                           source_ids=['natural_earth_countries']))
        events.append(dict(id=event, semantic_segment_ref=segment, claim_id=claim,
            target_geometry_refs=['COUNTRY_'+country], location_point_ref='LOCATION_COUNTRY_'+country,
            state_before='UNCHANGED', state_after='LOCATION', primary_role='LOCATION_LABEL',
            evidence_type='sourced_fact', watermark=None, sentence_index=0,
            text=dict(event_title=sentence, location_label=label, support_data=None)))
    return dict(text=text, segments=definitions, claims=claims, events=events,
        sources=[dict(id='natural_earth_countries', author='Natural Earth',
            url='https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries-2/',
            license='LicenseRef-Public-Domain')],
        topic='Source-backed geographic context; actual measured offline speech',
        language='en', options=dict(tts=True, subtitles=True, bgm=True, sfx=True))


def audit_synthetic_measured_media(plan, prepared, folder):
    """Exercise the original subtitle/AAC path; frames are an explicit pattern."""
    from engine.audio_stability import finish_video
    from engine.qc import probe_video, valid_scene_file
    from fractions import Fraction
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    count = sum(scene['frame_count'] for scene in plan['scenes'])
    fps = Fraction(plan['metadata']['frame_grid']['fps'])
    assert fps == 30 and prepared['subtitles']['enabled'], 'INFOGRAPHIC_SYNTHETIC_MEDIA_FIXTURE_INVALID'
    muted = folder/'SYNTHETIC_NOT_GPU_muted.mp4'
    pattern = 'testsrc2=size=1080x1920:rate=30'
    label = "drawtext=fontfile='"+str(APP_ROOT/'web/fonts/NotoSansCJKkr-Regular.otf')+"':text='SYNTHETIC MEASURED SPEECH - NO GPU MAP':fontsize=38:fontcolor=white:box=1:boxcolor=black@0.8:x=40:y=40"
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'lavfi', '-i', pattern,
        '-vf', label, '-frames:v', str(count), '-an', '-c:v', 'libx264', '-preset', 'ultrafast',
        '-crf', '28', '-threads', '4', '-pix_fmt', 'yuv420p', str(muted)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, 'INFOGRAPHIC_SYNTHETIC_PATTERN_ENCODER_FAILED'
    before_audio = _sha(Path(prepared['audio']['file']))
    outputs = finish_video(muted, folder/'final', plan, prepared['audio'], prepared['subtitles'])
    assert _sha(Path(prepared['audio']['file'])) == before_audio, 'INFOGRAPHIC_SYNTHETIC_MUX_AUDIO_SOURCE_CHANGED'
    final = Path(outputs['final'])
    media = probe_video(final)
    video = next(row for row in media['streams'] if row['codec_type'] == 'video')
    audio = next(row for row in media['streams'] if row['codec_type'] == 'audio')
    assert int(video['nb_frames']) == count and Fraction(video['avg_frame_rate']) == fps, 'INFOGRAPHIC_SYNTHETIC_VIDEO_CLOCK_INVALID'
    assert (int(video['width']), int(video['height']), video['pix_fmt']) == (1080, 1920, 'yuv420p'), 'INFOGRAPHIC_SYNTHETIC_VIDEO_FORMAT_INVALID'
    assert audio['codec_name'] == 'aac' and int(audio['channels']) == 2 and int(audio['sample_rate']) == 48000, 'INFOGRAPHIC_SYNTHETIC_AAC_FORMAT_INVALID'
    assert abs(float(video['duration'])-plan['duration']) <= 1/30, 'INFOGRAPHIC_SYNTHETIC_VIDEO_DURATION_INVALID'
    assert abs(float(audio['duration'])-float(video['duration'])) <= 1/30, 'INFOGRAPHIC_SYNTHETIC_AV_DURATION_INVALID'
    assert valid_scene_file(final, plan['duration'], 1080, 1920, 30), 'INFOGRAPHIC_SYNTHETIC_FINAL_MEDIA_INVALID'
    return dict(passed=True, file=str(final), sha256=_sha(final), frames=count, fps=30,
        video_duration=float(video['duration']), audio_duration=float(audio['duration']),
        codec='H264/AAC', subtitles='Original audio.create_subtitles and audio.finish_video ASS owner',
        resynthesized=False, physical_gpu='NOT_RUN', actual_map_video=False,
        scope='Explicit synthetic testsrc pattern with measured speech; technical AAC/video/ASS check, no map renderer or video quality claim')


def audit_measured_production(folder):
    from engine.audio import ESpeakProvider, _probe, _stereo, validate_subtitle_layout
    from engine.infographic_planner import generate_production_infographic
    from engine.infographic_contract import validate_infographic
    from engine.semantic_timeline import (validate_semantic_timeline,
        validate_production_plan, prepare_production_audio, TIMING_METHOD)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    # Provider absence or synthesis failure blocks admission. A WAV test fixture
    # is never substituted for the real packaged provider in this stage.
    provider = ESpeakProvider()
    authored = json.loads((APP_ROOT/'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
    plan = generate_production_infographic(authored, folder/'measurement',
                                           provider=provider, fps=30)
    timeline = plan['metadata']['semantic_timeline']
    assert timeline['passed'] and timeline['status'] == 'MEASURED', 'INFOGRAPHIC_PRODUCTION_TTS_NOT_MEASURED'
    assert timeline['provider'] == 'ESPEAK_OFFLINE' and timeline['word_alignment'] is False, 'INFOGRAPHIC_PRODUCTION_PROVIDER_INVALID'
    timing = validate_semantic_timeline(timeline, directory=folder/'measurement')
    assert timing['passed'] and validate_production_plan(plan)['passed'], 'INFOGRAPHIC_PRODUCTION_TIMING_INVALID'
    assert validate_infographic(plan)['passed'] and plan['gate']['passed'], 'INFOGRAPHIC_PRODUCTION_PLAN_INVALID'
    assert all(row['timing_method'] == TIMING_METHOD and row['word_alignment'] is False
               and row['sample_count'] > 0 for row in timeline['segments']), 'INFOGRAPHIC_PRODUCTION_UNMEASURED_SEGMENT'
    assert sum(scene['frame_count'] for scene in plan['scenes']) == timeline['total_frames'], 'INFOGRAPHIC_PRODUCTION_FRAME_GRID_INVALID'
    assert plan['duration'] == timeline['duration'] and plan['request']['direction_profile'] == 'MAP_INFOGRAPHIC_PRODUCTION_V022', 'INFOGRAPHIC_PRODUCTION_FIXED_QA_SUBSTITUTED'
    voice = folder/'measurement'/timeline['voice']['file']
    assert _sha(voice) == timeline['voice']['sha256'], 'INFOGRAPHIC_MEASURED_VOICE_HASH_INVALID'
    audio = prepare_production_audio(plan, timeline, folder/'measurement', folder/'mixed-audio')
    assert audio['timing']['passed'], 'INFOGRAPHIC_PRODUCTION_AUDIO_TIMING_INVALID'
    assert audio['audio']['semantic_timeline']['resynthesized'] is False, 'INFOGRAPHIC_PRODUCTION_RESYNTHESIZED'
    assert audio['audio']['semantic_timeline']['voice_sha256'] == timeline['voice']['sha256'], 'INFOGRAPHIC_PRODUCTION_AUDIO_SOURCE_CHANGED'
    assert validate_subtitle_layout(audio['subtitles'], plan['duration'])['passed'], 'INFOGRAPHIC_PRODUCTION_SUBTITLE_LAYOUT_INVALID'
    measured_duration = float(_probe(Path(audio['audio']['file']))['format']['duration'])
    assert abs(measured_duration-plan['duration']) <= 1/30, 'INFOGRAPHIC_PRODUCTION_AUDIO_DURATION_MISMATCH'
    mixed = folder/'mixed-audio'
    checkpoint_files = [Path(audio['audio']['file']), Path(audio['subtitles']['path']),
        mixed/'audio_report.json', mixed/'subtitle_report.json', mixed/'semantic-audio-reuse.json']
    assert all(file.is_file() for file in checkpoint_files), 'INFOGRAPHIC_PRODUCTION_AUDIO_CHECKPOINT_MISSING'
    checkpoint_hashes = {str(file.relative_to(mixed)): _sha(file) for file in checkpoint_files}
    physical_samples = len(_stereo(Path(audio['audio']['file'])))
    assert physical_samples == round(plan['duration']*48000), 'INFOGRAPHIC_PRODUCTION_PHYSICAL_SAMPLE_CLOCK_INVALID'
    mastering = audio['audio']['measured_mastering']
    assert mastering['version'] == 'PCM_EOF_FLUSH_SAMPLE_CLOCK_v022', 'INFOGRAPHIC_PRODUCTION_MASTERING_CONTRACT_INVALID'
    assert mastering['expected_sample_count'] == mastering['actual_sample_count'] == audio['audio']['sample_count'] == physical_samples, 'INFOGRAPHIC_PRODUCTION_MASTERING_SAMPLE_COUNT_INVALID'
    assert mastering['sample_rate'] == 48000 and abs(mastering['duration']-plan['duration']) <= 1/48000, 'INFOGRAPHIC_PRODUCTION_MASTERING_CLOCK_INVALID'
    assert mastering['eof_flushed'] is True and mastering['silence_padding'] is False and mastering['normalization_unchanged'] is True, 'INFOGRAPHIC_PRODUCTION_MASTERING_POLICY_CHANGED'
    reused = prepare_production_audio(plan, timeline, folder/'measurement', mixed)
    assert reused['timing']['passed'] and reused['audio']['semantic_timeline']['resynthesized'] is False, 'INFOGRAPHIC_PRODUCTION_CACHED_AUDIO_RESYNTHESIZED'
    assert reused['audio']['file'] == audio['audio']['file'] and reused['subtitles']['path'] == audio['subtitles']['path'], 'INFOGRAPHIC_PRODUCTION_CACHE_PATH_CHANGED'
    assert {str(file.relative_to(mixed)): _sha(file) for file in checkpoint_files} == checkpoint_hashes, 'INFOGRAPHIC_PRODUCTION_CACHED_CHECKPOINT_CHANGED'
    assert len(_stereo(Path(reused['audio']['file']))) == physical_samples, 'INFOGRAPHIC_PRODUCTION_CACHED_SAMPLE_CLOCK_CHANGED'
    path = folder/'PLAN.json'
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    backend = audit_backend(plan, folder)
    adapter = audit_native_adapter(plan, folder/'adapter', production=True)
    synthetic = audit_synthetic_measured_media(plan, audio, folder/'synthetic-not-gpu')
    report = dict(passed=True, plan=plan, provider=timeline['provider'], timing_method=TIMING_METHOD,
        total_frames=timeline['total_frames'], duration=timeline['duration'], word_alignment=False,
        source_voice_sha256=timeline['voice']['sha256'], audio_duration=measured_duration,
        resynthesized=False, subtitles='Existing FFmpeg subtitle owner; no native duplicate',
        cached_reuse=dict(passed=True, physical_samples=physical_samples, sample_rate=48000,
            checkpoints=checkpoint_hashes, resynthesized=False, files_unchanged=True,
            mastering=mastering),
        backend=backend, adapter_contract=adapter, synthetic_measured_media=synthetic,
        material_policy='Explicit Production regional base reuses verified v018/v019 installers; overlay ON/OFF leaves that base unchanged',
        physical_gpu='NOT_RUN', voice_quality='NOT_REVIEWED', direct_listening='NOT_RUN')
    return report


def run(folder, *, require_container_assets=False):
    from deployment.gcube.event_quality_preflight import selected_environment
    from deployment.gcube.story_progression_preflight import run as parent_run
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if require_container_assets:
        assert os.environ.get('WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION') == 'v022', 'INFOGRAPHIC_IMAGE_DEFAULT_MISSING'
    sources = verify_source_manifest()
    preserved, audit = audit_parent_assets(require_container_assets)
    registry = audit_registry_assets()
    with selected_environment(WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION='legacy',
                              WORLD_ENGINE_STORY_PROGRESSION_VERSION='v021'):
        with inherited_asset_view(audit):
            inherited = parent_run(folder/'v021-baseline', require_container_assets=require_container_assets)
        assert inherited['passed'], 'INFOGRAPHIC_INHERITED_V021_CONTRACT_FAILED'
        baseline = json.loads((folder/'v021-baseline/selected/PLAN.json').read_text())
        with selected_environment(WORLD_ENGINE_REFERENCE_EFFECTS_VERSION='v020',
                                  WORLD_ENGINE_EVENT_QUALITY_VERSION='v019',
                                  WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                                  WORLD_ENGINE_SECOND_EVENT_TEST='1', WORLD_ENGINE_DIRECTION_VERSION='v013'):
            selected = audit_selected_qa(baseline, folder/'selected')
    production = audit_measured_production(folder/'production')
    canvas = audit_canvas_pixels(folder/'canvas-pixels')
    serving = audit_served_assets()
    asset_union = {row['path']: dict(path=row['path'], size=row['size'], sha256=row['sha256'])
                   for row in audit['assets']}
    for row in registry['assets']:
        name = 'world-simulation-shorts-engine/'+row['path']
        asset_union[name] = dict(path=name, size=row['size'], sha256=row['sha256'])
    for name in ('web/fonts/NotoSansCJKkr-Bold.otf', 'web/fonts/BOLD_SOURCE_v022.json'):
        file = APP_ROOT/name
        name = 'world-simulation-shorts-engine/'+name
        asset_union[name] = dict(path=name, size=file.stat().st_size, sha256=_sha(file))
    inventory = load_manifest()
    expected_union = inventory['registered_asset_union_count'] if require_container_assets else inventory['native_asset_union_count']
    assert len(asset_union) == expected_union, 'INFOGRAPHIC_DEPLOYED_ASSET_UNION_CHANGED'
    report = dict(passed=True, sources=sources, preserved_parent=preserved, registry=registry,
        inherited_v021=inherited, selected_infographic={key:value for key,value in selected.items() if key != 'plan'},
        measured_production={key:value for key,value in production.items() if key != 'plan'}, canvas_pixels=canvas,
        served_assets=serving, assets=sorted(asset_union.values(), key=lambda row: row['path']),
        registered_asset_union_count=len(asset_union), camera_trajectory='UNCHANGED',
        frames=720, physical_gpu='NOT_RUN', output_quality='NOT_RUN',
        scope='Whole immutable v021 parent; OFF/ON native/source/static admission and real measured offline speech; NVIDIA pixels, actual map MP4 quality and listening NOT_RUN')
    (folder/'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('::notice title=Infographic preflight::'+json.dumps(dict(passed=True,
        inherited_auditor_assets=len(audit['assets']), registered_asset_union_count=len(asset_union),
        runtime_source_files=len(sources['runtime_records']), frames=720,
        measured_production_frames=production['total_frames'], provider=production['provider'],
        physical_gpu='NOT_RUN', output_quality='NOT_RUN')))
    return report


if __name__ == '__main__':
    import sys
    if '--manifest-only' in sys.argv:
        report = verify_source_manifest(require_checkout='--checkout' in sys.argv)
        print('::notice title=Frozen v022 source admission::'+json.dumps({
            key:value for key,value in report.items()
            if key not in {'runtime_records', 'frozen_parent_records'}}))
    else:
        candidates = [item for item in sys.argv[1:] if not item.startswith('--')]
        report = run(candidates[0] if candidates else '/data/infographic-preflight',
                     require_container_assets='--container' in sys.argv)
        raise SystemExit(not report['passed'])
