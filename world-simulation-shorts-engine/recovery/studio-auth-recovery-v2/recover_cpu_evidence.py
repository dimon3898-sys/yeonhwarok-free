"""Recover an existing free CPU artifact; never rerun a container or GPU job."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPOSITORY = 'dimon3898-sys/yeonhwarok-free'
RUN_ID = '39074308838'
ARTIFACT = 'studio-startup-cpu-39074308838-1'
EXPECTED_IMAGE = ('ghcr.io/dimon3898-sys/world-simulation-shorts-engine@'
                  'sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94')
EXPECTED_CASES = {
    'missing-origin': (1, 'STUDIO_HTTPS_ORIGIN_REQUIRED'),
    'missing-owner': (1, 'STUDIO_OWNER_CONFIGURATION_REQUIRED'),
    'generic-aliases': (1, 'STUDIO_HTTPS_ORIGIN_REQUIRED'),
    'optional-policy-absent': (0, None),
}


def recover(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='studio-cpu-artifact-') as private:
        command = ['gh', 'run', 'download', RUN_ID, '--repo', REPOSITORY,
                   '--name', ARTIFACT, '--dir', private]
        result = subprocess.run(command, capture_output=True, timeout=120)
        if result.returncode:
            return {'status': 'BLOCKED', 'errorCode': 'PREVIOUS_CPU_ARTIFACT_DOWNLOAD_FAILED',
                    'sourceRunId': RUN_ID, 'downloadExitCode': result.returncode,
                    'rawOutputPublished': False, 'testsRerun': False}
        root = Path(private)
        raw = (root / 'results.json').read_bytes()
        if len(raw) > 128_000:
            raise ValueError('CPU_ARTIFACT_SIZE_INVALID')
        sums = (root / 'SHA256SUMS').read_text().splitlines()
        if len(sums) != 1 or not re.fullmatch(r'[0-9a-f]{64}  results\.json', sums[0]):
            raise ValueError('CPU_ARTIFACT_MANIFEST_INVALID')
        sha = hashlib.sha256(raw).hexdigest()
        if sums[0].split()[0] != sha:
            raise ValueError('CPU_ARTIFACT_HASH_MISMATCH')
        source = json.loads(raw)
        if (source.get('schema') != 'WORLD_ENGINE_STUDIO_STARTUP_CPU_REPRODUCTION_V1'
                or source.get('image') != EXPECTED_IMAGE or source.get('result') != 'PASS'):
            raise ValueError('CPU_ARTIFACT_CONTRACT_INVALID')
        cases = source.get('cases', [])
        if len(cases) != len(EXPECTED_CASES):
            raise ValueError('CPU_ARTIFACT_CASES_INVALID')
        safe_cases = []
        seen = set()
        for case in cases:
            name = case.get('case')
            expected = EXPECTED_CASES.get(name)
            if (name in seen or expected is None or case.get('status') != 'PASS'
                    or (case.get('actualContainerExitCode'), case.get('firstRecordedErrorCode')) != expected
                    or case.get('testScope') not in {'ACTUAL_ORIGINAL_CONTAINER_ENTRYPOINT',
                                                    'CONFIGURATION_FUNCTION_ONLY'}):
                raise ValueError('CPU_ARTIFACT_CASE_RESULT_INVALID')
            seen.add(name)
            safe_cases.append({k: case[k] for k in ('case', 'status', 'testScope',
                                                    'actualContainerExitCode', 'firstRecordedErrorCode')})
        return {'status': 'PASS', 'sourceRunId': RUN_ID, 'artifact': ARTIFACT,
                'sourceResultsSHA256': sha, 'downloadSHA256Verified': True,
                'image': EXPECTED_IMAGE, 'cases': safe_cases, 'testsRerun': False,
                'nvidiaHardwareVerified': False, 'actual5373CauseConfirmed': False}


if __name__ == '__main__':
    target = Path(sys.argv[1])
    try:
        record = recover(target)
    except Exception:
        record = {'status': 'BLOCKED', 'errorCode': 'CPU_EVIDENCE_RECOVERY_FAILED',
                  'rawOutputPublished': False, 'testsRerun': False}
    target.mkdir(parents=True, exist_ok=True)
    (target / 'CPU_EVIDENCE.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'status': record['status'], 'testsRerun': False}))
