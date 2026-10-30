#!/usr/bin/env python3
"""Four new CLI execution boundaries; no prior suite, producer or image checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PUBLISHER = ROOT / 'world-simulation-shorts-engine/recovery/label355-publication-v1/publish_label355_once.py'
BACKUP = ROOT / 'label355-safe-evidence/world-simulation-shorts-engine/recovery/label-packaging-v1/backup_build_evidence.py'
EVIDENCE = HERE / 'evidence'
PARENT = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
OLD = 'sha256:a175c1b01fda0513625a171e74987951d8c11ad083d8583fc297f4fcff2271cc'
NEW = 'sha256:' + '1' * 64
OTHER = 'sha256:' + '2' * 64
SOURCE = 'af9347963b4405dac66cdbe0ad6c6898c3d42ea0'
CASES = (
    ('normal_review_still_blocks_publication', 'D9_EXCEPTION_REVIEW_ONLY_PUBLICATION_BLOCKED', True),
    ('missing_safe_receipt', 'BLOCKED_FileNotFoundError:', False),
    ('comparison_image_id_mismatch', 'D9_EXCEPTION_IMAGE_ID_CHAIN', False),
    ('safe_receipt_parent_mismatch', 'EVIDENCE_VALUE_INVALID', False),
)


def write(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write('\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture():
    return {
        'PREFLIGHT.json': {'status': 'PASS', 'parentDigest': PARENT,
            'compressedLayerBytes': 1, 'freeBytes': 3, 'estimatedRequiredBytes': 2,
            'costGate': 'CURRENT_ATTESTED', 'scope': 'BUILD_PREFLIGHT_ONLY'},
        'INSTALLED_RESULT.json': {'schema': 'WORLD_ENGINE_INSTALLED_LABEL355_VERIFICATION_V1',
            'status': 'PASS', 'installedFilesVerified': 355, 'uid': 1000,
            'runtimeManifestSHA256': '1427779c7a52af90f37478de3ba11e1ddb664149f5b13dbd87fb05142be0252e',
            'startupManifestSHA256': 'f8afb5c2f944dea13f7a990a7c2c8e8c65c9c028bd7228f501aa6feace98ef89',
            'scope': 'INSTALLED_FILES_AND_UID1000_ONLY_OCI_HOST_CHECK_SEPARATE', 'gpuExecuted': False},
        'OCI_RESULT.json': {'schema': 'WORLD_ENGINE_LABEL355_OCI_RESULT_V1', 'status': 'PASS',
            'imageId': NEW, 'entrypointMatch': True, 'cmdUnchanged': True, 'userUnchanged': True,
            'scope': 'ACTUAL_CANDIDATE_OCI_CONFIG_ONLY', 'gpuExecuted': False},
        'BUILD_RESULT.json': {'schema': 'WORLD_ENGINE_LABEL355_BUILD_RESULT_V1', 'status': 'IDENTITY_ONLY',
            'imageId': NEW, 'parentDigest': PARENT, 'expectedSourceRows': 355,
            'scope': 'CANDIDATE_IMAGE_IDENTITY_ONLY_NOT_BUILD_OR_INSTALLED_VALIDATION', 'gpuExecuted': False},
        'IMAGE_CONFIG_SAFE.json': {'schema': 'WORLD_ENGINE_IMAGE_CONFIG_SAFE_V1',
            'status': 'CAPTURED_NOT_COMPARED', 'imageId': NEW, 'parentDigest': PARENT,
            'os': 'linux', 'architecture': 'amd64', 'rootfsType': 'layers',
            'rootfsDiffIDs': ['sha256:' + '3' * 64], 'entrypointSHA256': '4' * 64,
            'cmdSHA256': '5' * 64, 'userSHA256': '6' * 64, 'historySHA256': '7' * 64,
            'historyCount': 1, 'gpuExecuted': False},
    }


def main():
    # The parent may have preserved read-only provenance before this run.
    # SOURCE_PROVENANCE exclusive creation and exclusive case directories prevent reruns.
    EVIDENCE.mkdir(exist_ok=True)
    if any((EVIDENCE / name).exists() for name in
           ('SOURCE_PROVENANCE.json', 'EXECUTION_RESULT.json', 'execution.log', *(row[0] for row in CASES))):
        raise RuntimeError('BLOCKED_EXECUTION_EVIDENCE_ALREADY_EXISTS_NO_RETRY')
    results = []
    total = {'docker': 0, 'ghcrNetwork': 0, 'publications': 0, 'imageBuilds': 0,
             'actions': 0, 'gpu': 0, 'previousPASSReruns': 0, 'previousMock7Reruns': 0, 'retries': 0}
    provenance = {'schema': 'WORLD_ENGINE_D9_REVIEW_SOURCE_PROVENANCE_V1',
        'publisherCommit': '2f32d5e3bfddaa7c7e6ac98cd4d88b5e4a1d7cf3',
        'pinnedBackupCommit': 'e163de2602a486196ec75683ddf0609bdcffb2ed',
        'publisherSHA256': sha(PUBLISHER), 'pinnedBackupSHA256': sha(BACKUP),
        'fixtureScope': 'SYNTHETIC_RECEIPTS_NOT_ACTUAL_BUILD_IMAGE_OR_COST_EVIDENCE',
        'noMockReplacementOfPublisherOrBackup': True}
    if (provenance['publisherSHA256'] != '89888b045fb9708d188377d05e4b5d13e0ae894b2c1308b8678cce0478e95623'
            or provenance['pinnedBackupSHA256'] != '47968ef601992a6164a913e5531f62ff0b7aa38958c5da1bc7a56341fd5062c9'):
        raise RuntimeError('BLOCKED_UNEXPECTED_SOURCE_BYTES')
    write(EVIDENCE / 'SOURCE_PROVENANCE.json', provenance)
    with (EVIDENCE / 'execution.log').open('x', encoding='utf-8') as log:
        log.write('Four new real-code CLI boundaries; all prior PASS and seven local mocks SKIP.\n')
        for index, (name, expected_error, expect_review) in enumerate(CASES, 1):
            case = EVIDENCE / name
            case.mkdir()
            built, out = case / 'label355-evidence', case / 'label355-publication'
            built.mkdir()
            out.mkdir()
            receipts = fixture()
            if name == 'missing_safe_receipt':
                del receipts['IMAGE_CONFIG_SAFE.json']
            elif name == 'safe_receipt_parent_mismatch':
                receipts['IMAGE_CONFIG_SAFE.json']['parentDigest'] = OTHER
            for filename, value in receipts.items():
                write(built / filename, value)
            write(out / 'IMAGE_ID_COMPARISON.json', {'status': 'COMPARED', 'previousImageID': OLD,
                'newImageID': OTHER if name == 'comparison_image_id_mismatch' else NEW,
                'imageIDsEqual': False, 'sourceCommit': SOURCE})
            write(out / 'GHCR_PREFLIGHT.json', {'status': 'PASS'})
            inputs = [{'path': str(p.relative_to(case)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                      for p in sorted(case.rglob('*.json'))]
            audit = case / 'ISOLATION.json'
            command = [sys.executable, '-I', '-B', str(HERE / 'isolated_child.py'), str(PUBLISHER), str(audit)]
            environment = {'PATH': '/usr/bin:/bin', 'RUNNER_TEMP': str(case), 'GITHUB_RUN_ID': '0'}
            completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                       text=True, timeout=20, check=False)
            (case / 'stdout.log').write_text(completed.stdout, encoding='utf-8')
            (case / 'stderr.log').write_text(completed.stderr, encoding='utf-8')
            isolation = json.loads(audit.read_bytes()) if audit.exists() else {}
            review_path = out / 'D9_EXCEPTION_REVIEW.json'
            review = json.loads(review_path.read_bytes()) if review_path.exists() else None
            expected_review = {'status': 'REVIEW_READY_NOT_PUBLICATION_AUTHORIZED',
                'newImageID': NEW, 'previousImageID': OLD, 'sourceCommit': SOURCE,
                'cause': 'UNVERIFIED', 'registryWrites': 0}
            passed = (completed.returncode == 1 and expected_error in completed.stderr
                and not completed.stdout and isolation.get('externalAttempts') == 0
                and isolation.get('realPinnedBackupUsed') is True
                and isolation.get('executedSourceModules') == ['g2ImportDependency', 'pinnedBackup', 'publisher']
                and isolation.get('executedSourceSHA256', {}).get('publisher') == provenance['publisherSHA256']
                and isolation.get('executedSourceSHA256', {}).get('pinnedBackup') == provenance['pinnedBackupSHA256']
                and sum(row['function'] == 'review_d9_exception' for row in isolation.get('observedFunctionCalls', [])) == 1
                and sum(row['function'] == 'safe_evidence_bytes' for row in isolation.get('observedFunctionCalls', []))
                    == (4 if name == 'missing_safe_receipt' else 5)
                and (review == expected_review if expect_review else review is None)
                and not any((out / filename).exists() for filename in
                    ('PUBLICATION_ATTEMPT.json', 'PUSH_RESULT.json', 'REMOTE_RESULT.json')))
            result = {'case': name, 'status': 'PASS' if passed else 'FAIL', 'attempt': 1,
                'exitCode': completed.returncode, 'expectedError': expected_error,
                'reviewWritten': review is not None, 'publicationBlocked': completed.returncode == 1,
                'inputFiles': inputs, 'isolation': isolation, 'fixtureScope': provenance['fixtureScope']}
            write(case / 'CASE_RESULT.json', result)
            results.append(result)
            log.write(f'{index}/4 {name}: {result["status"]}; exit={completed.returncode}; expected={expected_error}\n')
            log.flush()
            print(f'{name}: {result["status"]} (exit {completed.returncode})', flush=True)
            if not passed:
                write(EVIDENCE / 'EXECUTION_RESULT.json', {'status': 'FAIL', 'cases': results,
                    'executionCounts': total, 'firstIncompleteStage': 'ACTUAL_REVIEW_CLI_BOUNDARY_' + name})
                return 1
    write(EVIDENCE / 'EXECUTION_RESULT.json', {'schema': 'WORLD_ENGINE_D9_REVIEW_EXECUTION_RESULT_V1',
        'status': 'PASS', 'newCasesPassed': len(results), 'cases': results,
        'executionCounts': total, 'publisherRuns': len(results),
        'scope': 'NEW_REAL_CODE_REVIEW_CLI_BOUNDARIES_WITH_REAL_PINNED_VALIDATOR_ONLY',
        'fixtureScope': provenance['fixtureScope'], 'publicationAuthorizationGranted': False,
        'originalD9PublicationStopPreserved': True, 'productionSourceChanged': False})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
