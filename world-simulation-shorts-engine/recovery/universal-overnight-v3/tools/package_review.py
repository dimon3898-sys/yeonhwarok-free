"""Package only reviewed public media and source-qualified documentation.

This does not build an image, open a GPU, alter a scene, or publish private
captures/job records. Run after the actual software and independent-image
receipts exist. HTTP download verification is a separate recorded operation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(media, proof_file, inputs):
    media, inputs, proof_file = Path(media), Path(inputs), Path(proof_file)
    receipt = json.loads((media / 'FINAL_DELIVERY_RECEIPT.json').read_bytes())
    proof = json.loads(proof_file.read_bytes())
    manifest_sha = sha(ROOT / 'OVERNIGHT_FILES.json')
    assert receipt['result'] == 'SOFTWARE_PREVIEW_TECHNICAL_PASS'
    assert receipt['frames'] == 150 and receipt['fullDecode'] == 'PASS'
    assert receipt['physicalNvidiaExecuted'] is False
    assert receipt['sourceManifestSHA256'] == manifest_sha == proof['sourceManifestSHA256']
    assert proof['independentPullVerified'] and proof['sourceHashesVerified']
    assert proof['sourceCommit'] == receipt['sourceCheckpointCommit']
    video = media / receipt['finalVideo']['file']
    assert sha(video) == receipt['finalVideo']['sha256']
    comparison = json.loads((ROOT / 'reports/REFERENCE_COMPARISON.json').read_bytes())
    assert comparison['candidateSHA256'] == sha(video)
    assert comparison['nvidiaRenderingVerified'] is False
    assert comparison['visualQualityPass'] is False
    destination = ROOT / 'public-review'
    destination.mkdir(exist_ok=False)
    shutil.copy2(video, destination / 'WORLD_ENGINE_OVERNIGHT_PREVIEW_5S.mp4')
    for row in receipt['checkpoints']:
        source = media / row['file']
        assert source.is_relative_to(media) and sha(source) == row['sha256']
        shutil.copy2(source, destination / source.name)
    figure = ROOT / 'reports' / comparison['comparisonPNG']['filename']
    assert sha(figure) == comparison['comparisonPNG']['sha256']
    shutil.copy2(figure, destination / 'REFERENCE_VS_SOFTWARE_PREVIEW.png')
    manifest = ''.join(sha(p) + '  ' + p.name + '\n' for p in sorted(destination.iterdir()))
    (destination / 'SHA256SUMS').write_text(manifest)

    # Explicit document allowlist; no runtime Python/JS, raw asset, credential,
    # job claim, diagnostic environment, or original reference media enters it.
    documents = ['OVERNIGHT_REPORT_KO.md', 'MOBILE_NEXT_STEPS_KO.md',
        'FEATURE_LEDGER_151.json', 'FEATURE_LEDGER_151.csv', 'UNWIRED_LEDGER_53.json',
        'UNWIRED_LEDGER_53.csv', 'REMAINING_FEATURES.json', 'DATA_READINESS.json',
        'DATA_READINESS_KO.md', 'DATA_EXTENSION_PROPOSAL.md', 'CPU_TEST_RESULTS.json',
        'SECRET_SCAN.json', 'REFERENCE_COMPARISON.json', 'VISUAL_QUALITY_REVIEW_KO.md',
        'FEATURE_SOFTWARE_OUTPUT_EVIDENCE.json', 'CANDIDATE_INPUT_VERIFICATION.json',
        'SOURCE_PROTECTION.json', 'REPAIR_HISTORY.json', 'REMAINING_FEATURES_KO.md',
        'COHERENCE_EXPERIMENT.json']
    archive_files = {'reports/' + name: (ROOT / 'reports' / name).read_bytes() for name in documents}
    archive_files['PREVIEW_CONTRACT.md'] = (ROOT / 'PREVIEW_CONTRACT.md').read_bytes()
    for name in ['STUDIO_OVERNIGHT_PROMPT.schema.json', 'VISUAL_EXTENSIONS.schema.json']:
        archive_files[name] = (ROOT / name).read_bytes()
    archive_files['STUDIO_OVERNIGHT_5S_PROMPT.json'] = (ROOT / 'PREVIEW_PROFILE.json').read_bytes()
    archive_files['SOURCE_QUALIFIED_VIDEO_PLAN_80S.json'] = (inputs / 'PLAN.json').read_bytes()
    archive_files['IMAGE_PROOF.json'] = proof_file.read_bytes()
    archive_files['SOFTWARE_PREVIEW_DELIVERY.json'] = (media / 'FINAL_DELIVERY_RECEIPT.json').read_bytes()
    archive_files['README_KO.md'] = (
        '# WORLD ENGINE 야간 작업 인계\n\n'
        '무료 SwiftShader 5초 기술 검증 결과입니다. NVIDIA·레퍼런스 품질 PASS가 아닙니다.\n'
        '원본 80초 Scene의 전역 시간축을 유지한 150프레임만 제작했습니다.\n'
        '80초 전체 렌더링과 FINAL 승격은 차단되어 있습니다.\n'
        '먼저 MP4와 비교 PNG를 검수하세요. 유료 GPU를 재배포할 필요는 없습니다.\n'
        'Scene은 근사·부분 역사 자료이며, 일별 실측 전선이나 부대 위치를 보증하지 않습니다.\n'
        '자세한 연결 상태와 차단 사유는 reports의 151개 기능표 및 남은 항목에 기록했습니다.\n'
        '실행은 검증된 후보 컨테이너 이미지와 기존 영구 데이터팩을 사용합니다.\n'
    ).encode()
    archive_files['SHA256SUMS'] = ''.join(
        hashlib.sha256(raw).hexdigest() + '  ' + name + '\n'
        for name, raw in sorted(archive_files.items())).encode()
    handoff = ROOT / 'handoff'
    handoff.mkdir(exist_ok=False)
    archive = handoff / 'WORLD_ENGINE_OVERNIGHT_HANDOFF.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for name, raw in sorted(archive_files.items()):
            output.writestr(name, raw)
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for line in output.read('SHA256SUMS').decode().splitlines():
            digest, name = line.split('  ', 1)
            assert hashlib.sha256(output.read(name)).hexdigest() == digest
    (handoff / 'SHA256SUMS').write_text(sha(archive) + '  ' + archive.name + '\n')
    return {'mediaFiles': len(list(destination.iterdir())), 'zipSHA256': sha(archive),
            'zipMembers': len(archive_files), 'privateRuntimeFilesPackaged': False,
            'nvidiaVerified': False, 'visualQualityApproved': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--media', required=True)
    parser.add_argument('--proof', required=True)
    parser.add_argument('--inputs', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.media, args.proof, args.inputs), ensure_ascii=False))
