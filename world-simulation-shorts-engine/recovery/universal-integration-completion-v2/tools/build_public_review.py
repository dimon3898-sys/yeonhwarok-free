#!/usr/bin/env python3
"""Package an explicit nonsecret documentation allowlist; no runtime code or logs."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'public-review'
REPORTS = [
    'RESULT_KO.md', 'GPU_5S_READINESS.md', 'STUDIO_INPUT_AND_LIMITS.md', 'CALL_GRAPH.md',
    'FEATURE_LEDGER_151.json', 'FEATURE_LEDGER_151.csv',
    'UNWIRED_LEDGER_53.json', 'UNWIRED_LEDGER_53.csv', 'CONNECTION_RECEIPTS.json',
    'CPU_TEST_RESULTS.json', 'PROTECTION.json', 'BASELINE.json',
    'HISTORY_ADMISSION.json', 'HISTORY_ADMISSION.md', 'MINIMUM_MISSING_DATA.json',
    'HISTORY_RUNTIME_NEGATIVE.json', 'CHAPTER_FEATURE_COVERAGE.json',
    'FRAME_SELECTION_TRACE_2400.csv', 'FRAME_TRACE_README.md',
    'CAMERA_CONNECTION.md', 'FRONTIER_CONNECTION.md', 'EVENT_FLOW_CONNECTION.md',
    'EXACT_INPUT_VALIDATION.json', 'CANDIDATE_INPUT_VALIDATION.json',
    'SFX_CLOCK_CPU.json', 'MEDIA_AVAILABILITY.json', 'IMAGE_CANDIDATE.json',
]
FILES = [
    'STUDIO_PROMPT_V2.schema.json', 'EVENT_FLOW_REQUEST.schema.json', 'PROMPT_V2_COOKBOOK.md',
    'SOURCE_DATA_CATALOG.json', 'COMPLETION_FILES.json', 'PACKAGED_FIXTURES.json',
    'fixtures/STUDIO_V2_80S_PROMPT.json', 'fixtures/VALIDATED_80S_SUBMISSION.json',
    'fixtures/CANDIDATE_80S_SUBMISSION.json', 'fixtures/CANDIDATE_CAPTURE_IDENTITY.json',
    'runs/39262218752-1/IMAGE_PROOF.json', 'runs/39262218752-1/IMAGE_PROOF.SHA256SUMS',
] + ['reports/' + name for name in REPORTS]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    DEST.mkdir(exist_ok=True)
    contents = {}
    for relative in FILES:
        path = ROOT / relative
        if (path.suffix not in {'.json', '.csv', '.md', '.SHA256SUMS'}
                or any(p.is_symlink() for p in (path, *path.parents))
                or not path.is_file() or not 0 < path.stat().st_size < 16 * 1024**2):
            raise RuntimeError('PUBLIC_REVIEW_ALLOWLIST_VIOLATION:' + relative)
        contents[relative] = path.read_bytes()
    summary = json.loads(contents['reports/FEATURE_LEDGER_151.json'])
    if (summary['featureCount'] != 151 or summary['previouslyUnwiredCount'] != 53
            or summary['actualOutputAppliedCount'] != 0
            or summary['candidateImage']['state'] != 'INDEPENDENT_PULL_VERIFIED'):
        raise RuntimeError('PUBLIC_REVIEW_STATE_NOT_FROZEN')
    readme = '''# WORLD ENGINE 통합 completion V2 검수 묶음

상태: **부분 통합 / USER_REVIEW_REQUIRED**. 전체 통합 PASS·GPU 품질 PASS가 아닙니다.

- [한국어 결과](reports/RESULT_KO.md)
- [151개 기능 표](reports/FEATURE_LEDGER_151.csv), [53개 미연결 표](reports/UNWIRED_LEDGER_53.csv)
- [실제 Studio 입력과 제한](reports/STUDIO_INPUT_AND_LIMITS.md)
- [12장면·2,400프레임 추적](reports/CHAPTER_FEATURE_COVERAGE.json)
- [5초 검수 전 차단 사항](reports/GPU_5S_READINESS.md)
- [후보 이미지 검증](reports/IMAGE_CANDIDATE.json)

집중 CPU 157 PASS / GPU 실행 0 / 기존 소스·FINAL 변경 0.
SUPPORTING 103 / BLOCKED 18 / UNVERIFIED 15 / NOT_APPLICABLE 15 / APPLIED 0.

자료·schema·Scene·CSV·안전한 검증 요약만 포함합니다. 런타임 소스 코드, Secret,
private 작업 기록, 원본 지도 자산, 영상, 내부 실행 로그는 포함하지 않습니다.
SHA256SUMS는 ZIP 내부 각 파일, DOWNLOAD_SHA256SUMS는 외부 다운로드 파일을 검증합니다.
'''
    contents['README.md'] = readme.encode()
    inventory = {'schema': 'WORLD_ENGINE_PUBLIC_REVIEW_INVENTORY_V1',
                 'sourceCommit': 'c5167ac6f61d4d32008b22a28a45ac05c8032670',
                 'files': {name: {'sha256': digest(raw), 'bytes': len(raw)}
                           for name, raw in sorted(contents.items())},
                 'runtimeSourceIncluded': False, 'privateLogsIncluded': False,
                 'gpuExecuted': False, 'videoRendered': False}
    contents['ARTIFACT_MANIFEST.json'] = (json.dumps(inventory, ensure_ascii=False, indent=2) + '\n').encode()
    contents['SHA256SUMS'] = ''.join(f'{digest(raw)}  {name}\n' for name, raw in sorted(contents.items())).encode()
    destination = DEST / 'WORLD_ENGINE_UNIVERSAL_COMPLETION_V2_REVIEW.zip'
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compresslevel=9)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(contents)
        for name, raw in contents.items():
            assert archive.read(name) == raw
    # A readable mobile index and inventory are available without opening a ZIP.
    (DEST / 'README.md').write_text(readme.replace('(reports/', '(../reports/'))
    (DEST / 'ARTIFACT_MANIFEST.json').write_bytes(contents['ARTIFACT_MANIFEST.json'])
    (DEST / 'DOWNLOAD_SHA256SUMS').write_text(''.join(
        f'{digest((DEST/name).read_bytes())}  {name}\n'
        for name in [destination.name, 'README.md', 'ARTIFACT_MANIFEST.json']))
    print(json.dumps({'archive': destination.name, 'bytes': destination.stat().st_size,
                      'sha256': digest(destination.read_bytes()), 'files': len(contents),
                      'zipReadback': 'PASS', 'status': 'USER_REVIEW_REQUIRED'}))


if __name__ == '__main__':
    main()
