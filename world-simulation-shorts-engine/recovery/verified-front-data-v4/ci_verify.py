#!/usr/bin/env python3
"""Free, opt-in V4 CPU verification only; no build, render, or paid operations."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = next((path for path in HERE.parents if (path / '.git').exists()), None)
NAMESPACE = 'world-simulation-shorts-engine/recovery/verified-front-data-v4'
WORKFLOW = '.github/workflows/verified-front-data-v4.yml'
BRANCH = 'development/korean-war-verified-front-v4-20261016'
BASELINE = '1c45284bf9c531cba12707cdad6516f2e72fa638'
PARENT_IMAGE = ('ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:'
                '10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb')
SCANNER_VERSION = '8.24.3'
SCANNER_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'
SCANNER_URL = ('https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/'
               'gitleaks_8.24.3_linux_x64.tar.gz')
MAX_EVIDENCE_BYTES = 2 * 1024 ** 2
REQUIRED_TEST_FILES = ('test_source_acquisition.py', 'test_georeference.py', 'test_front_evidence.py')
PARENT_ARTIFACTS = {
    'parentChronology': ('history/CHRONOLOGY_12.json',
        'c2fc87756fc137635ba2db4bd42df5893ed46007ae2033f1f06f2effcc1b6287'),
    'parentPlan': ('fixtures/PLAN_80S.json',
        'e5858f8f1bb1d3e0863ed8c3614263f838ddf4071951be8e237fd6fd8afed585'),
    'parentGeometryManifest': ('history/EXISTING_GEOMETRY_MANIFEST.json',
        'cfbbb80d78d5838532b2696c628ecbb36e8b32f14766338374cd02e5736dbd3c'),
}
EVIDENCE_FILES = {'evidence/INITIAL_ACCESS.json', 'evidence/HTTP_ERROR_CLASSIFICATION.json',
                  'evidence/OFFICIAL_ALTERNATIVES.json'}


def explicit_parent_root():
    checkout = HERE.parent / 'universal-production-v3'
    if (checkout / 'fixtures/PLAN_80S.json').is_file():
        return checkout
    # Shipped immutable image alias. No user-supplied path or URL is followed.
    return Path('/opt/world-engine-production-v3')


def audit_artifacts(*, evidence_root=HERE, parent_root=None):
    """Check actual source-denial records and unchanged plan; never admit a front."""
    root = Path(evidence_root)
    parent = explicit_parent_root() if parent_root is None else Path(parent_root)
    matrix = json.loads((root / 'EVENT_EVIDENCE_MATRIX.json').read_text())
    catalog = json.loads((root / 'SOURCE_CATALOG.json').read_text())
    documents = {}
    for key, (relative, digest) in PARENT_ARTIFACTS.items():
        raw = (parent / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError('IMMUTABLE_V3_ARTIFACT_SHA_MISMATCH')
        if matrix.get(key) != {'path': '../universal-production-v3/' + relative, 'sha256': digest}:
            raise RuntimeError('EXPLICIT_V3_ARTIFACT_BINDING_REQUIRED')
        documents[key] = json.loads(raw)
    if catalog.get('baselineCommit') != BASELINE or matrix.get('baselineCommit') != BASELINE:
        raise RuntimeError('V4_BASELINE_BINDING_REQUIRED')
    records = catalog.get('sources')
    if not isinstance(records, list) or len(records) != 11 or catalog.get('sourceCount') != 11:
        raise RuntimeError('ELEVEN_REAL_ACCESS_RECORDS_REQUIRED')
    source_ids = [row.get('sourceId') for row in records]
    if len(set(source_ids)) != len(source_ids):
        raise RuntimeError('UNIQUE_SOURCE_RECORDS_REQUIRED')
    empty_counts = ('newOriginalHistoricalSourceBodiesAcquired', 'newOfficialMapImagesAcquired',
                    'newArchivalFrontGeometriesAdmitted')
    if any(type(catalog.get(key)) is not int or catalog[key] != 0 for key in empty_counts):
        raise RuntimeError('NO_ORIGINAL_MAP_ADMISSION_IS_PERMITTED')
    references = 0
    evidence_hashes = {}
    for row in records:
        if (row.get('originalBodyRetrieved') is not False or row.get('originalSHA256') is not None
                or row.get('archivalGeometryAdmitted') is not False
                or row.get('licenseStatus') != 'UNVERIFIED'
                or row.get('labelIsVerifiedDocumentTitle') is not False):
            raise RuntimeError('SOURCE_DENIAL_CANNOT_CERTIFY_ORIGINAL_MAP')
        for key in ('originalByteLength', 'documentTitle', 'documentVersion', 'pdfPageIndex0',
                    'printedPage', 'mapCaption', 'mapDate', 'mapScale', 'projection',
                    'horizontalDatum', 'license'):
            if row.get(key) is not None:
                raise RuntimeError('UNRETRIEVED_SOURCE_METADATA_CANNOT_BE_VERIFIED')
        if row.get('acquisitionStatus') not in ('ACCESS_FAILED_NO_SOURCE_BODY',
                                               'NOT_ATTEMPTED_SHARED_HOST_POLICY'):
            raise RuntimeError('SOURCE_ACCESS_FAILURE_STATUS_REQUIRED')
        links = row.get('evidenceReferences')
        if not isinstance(links, list) or not links:
            raise RuntimeError('ACQUISITION_EVIDENCE_REFERENCE_REQUIRED')
        for link in links:
            name = link.get('path')
            if name not in EVIDENCE_FILES:
                raise RuntimeError('EXPLICIT_LOCAL_EVIDENCE_PATH_REQUIRED')
            raw = (root / name).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if link.get('sha256') != digest:
                raise RuntimeError('ACQUISITION_EVIDENCE_SHA_MISMATCH')
            evidence_hashes[name] = digest
            actual = json.loads(raw)
            index = link.get('recordIndex0')
            if type(index) is not int or not 0 <= index < len(actual):
                raise RuntimeError('ACQUISITION_EVIDENCE_INDEX_REQUIRED')
            proof = actual[index]
            if proof.get('retrievedFullSource') is True or proof.get('sourceBodyRetrieved') is True:
                raise RuntimeError('ACQUISITION_STATUS_CONTRADICTS_ORIGINAL_MAP_DENIAL')
            if proof.get('originalSHA256') is not None:
                raise RuntimeError('ERROR_RESPONSE_IS_NOT_SOURCE_ORIGINAL')
            if link.get('meaning') == 'SHARED_HOST_CONNECT_DENIAL_BASIS_ONLY_NOT_THIS_URL_REQUEST':
                if (row.get('acquisitionStatus') != 'NOT_ATTEMPTED_SHARED_HOST_POLICY'
                        or proof.get('sourceId') != row.get('failureClassification', {}).get('basisSourceId')):
                    raise RuntimeError('SHARED_HOST_DENIAL_BASIS_REQUIRED')
            elif proof.get('url') != row.get('url'):
                raise RuntimeError('ACQUISITION_EVIDENCE_URL_MISMATCH')
            references += 1
    plan = documents['parentPlan']
    stages = documents['parentChronology']['stages']
    chapters = plan['productionV3']['eventChapters']
    rows = matrix.get('rows')
    if (len(stages), len(chapters), matrix.get('eventCount'), len(rows or [])) != (12, 12, 12, 12):
        raise RuntimeError('TWELVE_PRESERVED_CHAPTERS_REQUIRED')
    if any((matrix.get(key), plan.get(key)) != (value, value) for key, value in
           (('durationSeconds', 80), ('fps', 30), ('totalFrames', 2400))):
        raise RuntimeError('PRESERVED_80_SECOND_FRAME_CONTRACT_REQUIRED')
    for key in ('newArchivalFrontCount', 'newCoordinateCount', 'newUnitPositionCount'):
        if type(matrix.get(key)) is not int or matrix[key] != 0:
            raise RuntimeError('NEW_UNVERIFIED_FRONT_OR_UNIT_FORBIDDEN')
    states = {row['stateId']: row for row in documents['parentGeometryManifest']['states']}
    if len(states) != 5 or matrix.get('existingSchematicSnapshotCount') != 5:
        raise RuntimeError('FIVE_EXISTING_SCHEMATIC_STATES_REQUIRED')
    cursor = 0
    for stage, chapter, row in zip(stages, chapters, rows):
        if (row.get('eventId'), row.get('chapterId'), row.get('title')) != (
                chapter['eventId'], chapter['chapterId'], chapter['title']):
            raise RuntimeError('EVENT_CHAPTER_BINDING_MISMATCH')
        if row.get('eventId') != stage['eventId'] or row.get('eventDate') != stage['date'] \
                or row.get('eventDate') != chapter['eventTimeWindow']:
            raise RuntimeError('EVENT_DATE_AND_SOURCE_DATE_MUST_REMAIN_DISTINCT')
        if (row.get('startFrame'), row.get('endFrame')) != (chapter['startFrame'], chapter['endFrame']) \
                or row.get('startFrame') != cursor or row.get('frameInterval') != 'HALF_OPEN':
            raise RuntimeError('CHAPTER_FRAME_RANGE_MISMATCH')
        cursor = row['endFrame']
        if (row.get('eventDateOfficialBodyVerified') is not False
                or row.get('newCoordinatesAllowed') is not False
                or row.get('confirmedNewArchivalFrontSegments') != []
                or row.get('admissionDecision') != 'NO_NEW_ARCHIVAL_GEOMETRY_ADMITTED'):
            raise RuntimeError('UNRETRIEVED_FRONT_CANNOT_GAIN_ADMISSION')
        for key in ('archivalMapDate', 'archivalMapReference', 'archivalMapPDFPageIndex0',
                    'archivalMapPrintedPage', 'originalMapScale', 'originalMapProjection', 'originalMapDatum'):
            if row.get(key) is not None:
                raise RuntimeError('UNRETRIEVED_MAP_METADATA_CANNOT_GAIN_PRECISION')
        use = row.get('videoUse', {})
        if (use.get('newVerifiedHistoricalFrontAvailable') is not False
                or use.get('exactEventDateFrontClaimAllowed') is not False
                or use.get('sourceSnapshotDateMustRemainVisible') is not True
                or use.get('geometryDataModified') is not False
                or use.get('unitPositionGenerationAllowed') is not False
                or use.get('enemyComplementGenerationAllowed') is not False
                or use.get('onScreenExistingGeometryLabel') != chapter['onScreenGeometryLabel']):
            raise RuntimeError('EXISTING_SCHEMATIC_DISCLOSURE_MUST_REMAIN')
        contexts = row.get('existingSchematicContexts', [])
        if [item.get('stateId') for item in contexts] != chapter['geometryStateIds']:
            raise RuntimeError('PRESERVED_CONTEXT_STATE_BINDING_REQUIRED')
        for context in contexts:
            original = states[context['stateId']]
            for key in ('snapshotDate', 'geometryRefs', 'geometryHashes', 'status'):
                if context.get(key) != original[key]:
                    raise RuntimeError('EXISTING_GEOMETRY_SOURCE_BINDING_MISMATCH')
            if context.get('archivalMapOriginalVerified') is not False:
                raise RuntimeError('SCHEMATIC_IS_NOT_ORIGINAL_ARCHIVAL_MAP')
    if cursor != 2400:
        raise RuntimeError('FULL_2400_FRAME_COVERAGE_REQUIRED')
    return {'schema': 'WORLD_ENGINE_V4_READINESS_ARTIFACT_AUDIT_V1', 'status': 'PASS',
            'sourceRecords': 11, 'acquisitionEvidenceReferencesChecked': references,
            'acquisitionEvidenceSHA256': evidence_hashes,
            'newHistoricalSourceBodies': 0, 'newHistoricalFrontCoordinates': 0,
            'preservedSchematicStates': 5, 'chapters': 12, 'totalFrames': 2400,
            'immutableV3ArtifactsSHA256': {key: value[1] for key, value in PARENT_ARTIFACTS.items()},
            'sceneConnection': 'NOT_CHANGED_NO_NEW_ADMITTED_GEOMETRY',
            'runtimeActualDraw': 'SKIP_REQUIRED_REAL_SOURCE',
            'image': 'NOT_BUILT_DATA_GATE', 'historicalFrontVerified': False,
            'gpuExecuted': False, 'softwareDrawExecuted': False}


def identifier(value, *, pattern=r'[1-9][0-9]{0,19}'):
    if not isinstance(value, str) or not re.fullmatch(pattern, value, re.ASCII):
        raise RuntimeError('BOUNDED_CI_IDENTIFIER_REQUIRED')
    return value


def allowed_addition(path):
    return path == WORKFLOW or path.startswith(NAMESPACE + '/')


def validate_changes(raw):
    rows = [line.split('\t') for line in raw.splitlines() if line]
    for row in rows:
        if len(row) != 2 or row[0] != 'A' or not allowed_addition(row[1]):
            raise RuntimeError('PREEXISTING_SOURCE_CHANGE_FORBIDDEN')
    return {'status': 'PASS', 'baselineCommit': BASELINE,
            'addedFiles': len(rows), 'preexistingFilesChanged': 0,
            'scope': 'ALL_TRACKED_PREEXISTING_FILES_VIA_GIT_OBJECT_COMPARISON'}


def command(arguments, *, timeout=180, cwd=None):
    result = subprocess.run(arguments, text=True, capture_output=True, check=False,
                            timeout=timeout, cwd=cwd)
    if result.returncode:
        raise RuntimeError('CI_SUBPROCESS_FAILED')
    if len(result.stdout.encode()) > MAX_EVIDENCE_BYTES:
        raise RuntimeError('CI_SUBPROCESS_OUTPUT_LIMIT')
    return result.stdout


def free_guard():
    expected = {'GITHUB_ACTIONS': 'true', 'RESULT_RUNNER_LABEL': 'ubuntu-24.04',
                'RESULT_REPOSITORY_PRIVATE': 'false',
                'GITHUB_REPOSITORY': 'dimon3898-sys/yeonhwarok-free',
                'GITHUB_REF': 'refs/heads/' + BRANCH}
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError('PUBLIC_FREE_STANDARD_RUNNER_REQUIRED')
    identifier(os.environ.get('GITHUB_RUN_ID'))
    identifier(os.environ.get('GITHUB_RUN_ATTEMPT'))
    identifier(os.environ.get('GITHUB_SHA'), pattern=r'[a-f0-9]{40}')
    if REPO is None:
        raise RuntimeError('CHECKED_OUT_REPOSITORY_REQUIRED')
    return {'status': 'PASS', 'runner': 'ubuntu-24.04', 'publicRepositoryRequired': True,
            'paidGpuExecuted': False, 'paidApiExecuted': False}


def result_path():
    root = Path(os.environ['RUNNER_TEMP']).resolve()
    return root / ('front-v4-' + identifier(os.environ.get('GITHUB_RUN_ID')) + '-' +
                   identifier(os.environ.get('GITHUB_RUN_ATTEMPT')) + '.json')


def state():
    path = result_path()
    if path.exists():
        raw = path.read_bytes()
        if len(raw) > MAX_EVIDENCE_BYTES:
            raise RuntimeError('BOUNDED_V4_EVIDENCE_REQUIRED')
        return json.loads(raw)
    return {'schema': 'WORLD_ENGINE_VERIFIED_FRONT_V4_CPU_CI_V1', 'status': 'IN_PROGRESS',
            'ciCommit': os.environ.get('GITHUB_SHA'), 'baselineCommit': BASELINE,
            'parentImage': PARENT_IMAGE, 'gpuExecuted': False, 'softwareDrawExecuted': False,
            'newImageBuilt': False, 'newImagePushed': False, 'gCubeDeployed': False,
            'paidWorkExecuted': False, 'videoQualityApproved': False,
            'actual80SecondNvidiaVideoGenerated': False,
            'newHistoricalFrontAdmission': 'BLOCKED_NO_ORIGINAL_MAP',
            'realMapGeoreferencing': 'BLOCKED_NO_ORIGINAL_MAP',
            'sceneHistoricalFrontActivation': 'NOT_EXECUTED_NO_VERIFIED_FRONT',
            'newImageAdmission': 'NOT_ALLOWED_NO_VERIFIED_RUNTIME_DATA',
            'existingV3TestsReused': 107}


def save(value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise RuntimeError('BOUNDED_V4_EVIDENCE_REQUIRED')
    result_path().write_bytes(raw)


def preflight():
    free_guard()
    command(['git', 'merge-base', '--is-ancestor', BASELINE, 'HEAD'], cwd=REPO)
    report = validate_changes(command(['git', 'diff', '--name-status', '--no-renames',
                                       BASELINE, 'HEAD'], cwd=REPO))
    if command(['git', 'diff', '--name-only', 'HEAD'], cwd=REPO).strip():
        raise RuntimeError('CLEAN_CI_CHECKOUT_REQUIRED')
    if shutil.disk_usage(os.environ['RUNNER_TEMP']).free < 12 * 1024 ** 3:
        raise RuntimeError('TWELVE_GIB_FREE_REQUIRED_FOR_EXISTING_IMAGE_PULL')
    matrix = json.loads((HERE / 'EVENT_EVIDENCE_MATRIX.json').read_text())
    if matrix.get('newArchivalFrontCount') != 0 or matrix.get('newCoordinateCount') != 0:
        raise RuntimeError('NEW_ARCHIVAL_DATA_NEEDS_EXPLICIT_RUNTIME_ADMISSION')
    if (matrix.get('eventCount'), matrix.get('durationSeconds'), matrix.get('fps'),
            matrix.get('totalFrames')) != (12, 80, 30, 2400):
        raise RuntimeError('PRESERVED_80_SECOND_TWELVE_CHAPTER_PLAN_REQUIRED')
    value = state()
    value['preflight'] = {'status': 'PASS', 'freeRunner': free_guard(), 'sourceProtection': report,
                          'newArchivalFrontCount': 0, 'newCoordinateCount': 0,
                          'durationSeconds': 80, 'fps': 30, 'totalFrames': 2400}
    save(value)


def container_command(folder):
    return ['docker', 'run', '--rm', '--network=none', '--read-only', '--user=1000:1000',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--restart=no',
            '--no-healthcheck',
            '--memory=4g', '--cpus=2', '--pids-limit=256', '--shm-size=512m',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=1g,mode=1777',
            '--mount', 'type=bind,source=' + str(folder.resolve()) + ',target=/front-v4,readonly',
            '--workdir=/front-v4', '--env=PYTHONDONTWRITEBYTECODE=1',
            '--env=PYTHONPATH=/front-v4', '--entrypoint=/usr/bin/python3',
            PARENT_IMAGE, '-B', '/front-v4/ci_verify.py', 'container-test']


class SafeTestResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.records = []

    def record(self, test, status):
        name = identifier(test.id(), pattern=r'[A-Za-z0-9_.]{1,240}')
        self.records.append({'id': name, 'status': status})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, 'PASS')

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.record(test, 'FAIL')

    def addError(self, test, error):
        super().addError(test, error)
        self.record(test, 'FAIL')

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, 'SKIP')


def container_test():
    # Only this newly added namespace is mounted. No old 107-test suite is run.
    if os.getuid() != 1000 or os.getgid() != 1000:
        raise RuntimeError('READONLY_UID_1000_CPU_TEST_REQUIRED')
    for name in REQUIRED_TEST_FILES:
        if not (HERE / 'tests' / name).is_file():
            raise RuntimeError('V4_FOCUSED_TEST_MODULE_REQUIRED')
    audit = audit_artifacts()
    tests = unittest.defaultTestLoader.discover(str(HERE / 'tests'), pattern='test_*.py')
    result = SafeTestResult()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        tests.run(result)
    skipped = len(result.skipped)
    report = {'schema': 'WORLD_ENGINE_V4_ISOLATED_CPU_TESTS_V1',
              'status': 'PASS' if result.wasSuccessful() and result.testsRun > 0 and not skipped else 'FAIL',
              'testCount': result.testsRun,
              'passed': sum(item['status'] == 'PASS' for item in result.records),
              'failed': sum(item['status'] == 'FAIL' for item in result.records),
              'skipped': skipped, 'tests': result.records,
              'testKinds': ['SYNTHETIC_TRANSPORT', 'SYNTHETIC_GEOREFERENCE',
                            'SYNTHETIC_PROVENANCE_AND_ADMISSION', 'NEW_ADDITIVE_COMPATIBILITY'],
              'historicalTruthVerified': False, 'realMapCoordinatesVerified': False,
              'gpuExecuted': False, 'softwareDrawExecuted': False,
              'artifactAudit': audit,
              'uid': os.getuid(), 'gid': os.getgid()}
    print(json.dumps(report, allow_nan=False))
    if report['status'] != 'PASS':
        raise SystemExit(1)


def test():
    free_guard()
    command(['docker', 'pull', PARENT_IMAGE], timeout=600)
    digests = json.loads(command(['docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', PARENT_IMAGE]))
    if not isinstance(digests, list) or PARENT_IMAGE not in digests:
        raise RuntimeError('IMMUTABLE_PARENT_IMAGE_DIGEST_REQUIRED')
    completed = subprocess.run(container_command(HERE), text=True, capture_output=True, check=False, timeout=600)
    if len(completed.stdout.encode()) > MAX_EVIDENCE_BYTES:
        raise RuntimeError('BOUNDED_V4_TEST_OUTPUT_REQUIRED')
    try:
        report = json.loads(completed.stdout.strip())
    except (ValueError, TypeError):
        raise RuntimeError('V4_TEST_JSON_REQUIRED') from None
    if not isinstance(report, dict) or report.get('schema') != 'WORLD_ENGINE_V4_ISOLATED_CPU_TESTS_V1':
        raise RuntimeError('V4_TEST_SCHEMA_REQUIRED')
    value = state()
    value['focusedTests'] = report
    value['cpuContainer'] = {'image': PARENT_IMAGE, 'immutableDigestPullVerified': True,
                             'exitCode': completed.returncode, 'uid': 1000, 'gid': 1000,
                             'network': 'none', 'readOnlyRoot': True, 'newNamespaceMount': 'readonly',
                             'capabilities': 'ALL_DROPPED', 'privilegeEscalation': False}
    save(value)
    if completed.returncode or report.get('status') != 'PASS' or report.get('gpuExecuted') is not False:
        raise RuntimeError('V4_FOCUSED_CPU_TESTS_FAILED')


def get_scanner(folder):
    with urllib.request.urlopen(SCANNER_URL, timeout=60) as response:
        raw = response.read(32 * 1024 ** 2 + 1)
    if len(raw) > 32 * 1024 ** 2:
        raise RuntimeError('SCANNER_ARCHIVE_SIZE_LIMIT')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        member = archive.getmember('gitleaks')
        if not member.isfile() or member.size > 32 * 1024 ** 2:
            raise RuntimeError('SCANNER_REGULAR_BINARY_REQUIRED')
        binary = archive.extractfile(member).read()
    if hashlib.sha256(binary).hexdigest() != SCANNER_SHA:
        raise RuntimeError('SCANNER_BINARY_SHA_MISMATCH')
    scanner = folder / 'gitleaks'
    scanner.write_bytes(binary)
    scanner.chmod(0o700)
    return scanner


def secret_scan(*, scanner_path=None):
    if REPO is None:
        raise RuntimeError('CHECKED_OUT_REPOSITORY_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='verified-front-scan-', dir=os.environ.get('RUNNER_TEMP')) as raw:
        folder = Path(raw)
        source = folder / 'source'
        shutil.copytree(HERE, source / NAMESPACE,
                        ignore=shutil.ignore_patterns('runs', '__pycache__', '*.pyc'))
        workflow = source / WORKFLOW
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_bytes((REPO / WORKFLOW).read_bytes())
        scanner = Path(scanner_path) if scanner_path is not None else get_scanner(folder)
        if hashlib.sha256(scanner.read_bytes()).hexdigest() != SCANNER_SHA:
            raise RuntimeError('SCANNER_BINARY_SHA_MISMATCH')
        ignore = folder / 'empty-ignore'
        ignore.write_text('')
        report = folder / 'findings.json'
        result = subprocess.run([str(scanner), 'dir', str(source), '--no-banner', '--redact=100',
                                 '--ignore-gitleaks-allow', '--gitleaks-ignore-path', str(ignore),
                                 '--report-format=json', '--report-path', str(report)],
                                text=True, capture_output=True, check=False, timeout=180)
        if not report.is_file() or report.stat().st_size > MAX_EVIDENCE_BYTES:
            raise RuntimeError('BOUNDED_SECRET_SCAN_REPORT_REQUIRED')
        findings = json.loads(report.read_text())
        if not isinstance(findings, list):
            raise RuntimeError('SECRET_SCAN_LIST_REQUIRED')
        output = {'status': 'PASS' if result.returncode == 0 and not findings else 'FAIL',
                  'findings': len(findings), 'scannerExitCode': result.returncode,
                  'scannerVersion': SCANNER_VERSION, 'scannerSHA256': SCANNER_SHA,
                  'defaultRules': True, 'customAllowlist': False, 'inlineAllowsIgnored': True,
                  'scope': 'V4_NAMESPACE_AND_NEW_WORKFLOW_EXCLUDING_HISTORICAL_RUN_RECORDS',
                  'fileCount': sum(path.is_file() for path in source.rglob('*'))}
        # Never persist Match/Secret or raw scanner stdout/stderr.
        return output


def scan():
    free_guard()
    value = state()
    value['secretScan'] = secret_scan()
    if value['secretScan']['status'] != 'PASS':
        save(value)
        raise RuntimeError('NEW_SOURCE_SECRET_SCAN_FAILED')
    value['status'] = 'CPU_VERIFIED_HISTORICAL_DATA_BLOCKED'
    save(value)


def persist():
    free_guard()
    value = state()
    outcomes = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if set(outcomes) != {'preflight', 'test', 'scan'} or any(
            item not in ('success', 'failure', 'skipped', 'cancelled') for item in outcomes.values()):
        raise RuntimeError('BOUNDED_STEP_OUTCOMES_REQUIRED')
    value['stepOutcomes'] = outcomes
    if any(item != 'success' for item in outcomes.values()):
        value['status'] = 'V4_CPU_VERIFICATION_FAILED'
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise RuntimeError('BOUNDED_V4_EVIDENCE_REQUIRED')
    relative = (NAMESPACE + '/runs/' + identifier(os.environ.get('GITHUB_RUN_ID')) + '-' +
                identifier(os.environ.get('GITHUB_RUN_ATTEMPT')) + '/cpu.json')
    command(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], cwd=REPO)
    command(['git', 'switch', '--detach', 'FETCH_HEAD'], cwd=REPO)
    target = REPO / relative
    if target.exists():
        raise RuntimeError('PRIOR_EVIDENCE_OVERWRITE_FORBIDDEN')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    command(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=REPO)
    command(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=REPO)
    command(['git', 'add', '--', relative], cwd=REPO)
    if command(['git', 'diff', '--cached', '--name-only'], cwd=REPO).splitlines() != [relative]:
        raise RuntimeError('ONLY_BOUNDED_NEW_CPU_RECORD_MAY_BE_STAGED')
    command(['git', 'commit', '-m', 'docs: persist verified-front V4 CPU evidence [skip ci]'], cwd=REPO)
    command(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], cwd=REPO)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'test', 'container-test', 'audit', 'scan', 'persist'))
    phase = parser.parse_args().phase
    if phase == 'container-test':
        container_test()
    elif phase == 'audit':
        print(json.dumps(audit_artifacts(), indent=2))
    else:
        try:
            globals()[phase]()
        except Exception as error:
            reason = str(error)
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', reason):
                reason = 'V4_CI_PHASE_FAILED'
            value = state()
            value.update(status='V4_CPU_VERIFICATION_FAILED', failedPhase=phase,
                         reasonCode=reason, errorType=type(error).__name__)
            save(value)
            print(json.dumps({'status': value['status'], 'phase': phase, 'reasonCode': reason}))
            raise SystemExit(1)
