"""One-shot post-capture verification of the frozen real software preview.

This analysis helper is outside the checkout and never invokes a renderer.
"""
from pathlib import Path
import collections
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image

REPO = Path('/workspace/yeonhwarok-free-studio-startup')
NS = REPO / 'world-simulation-shorts-engine/recovery/universal-overnight-v3'
INPUT = Path('/workspace/overnight-joint-final-input-20261019')
OUTPUT = Path('/workspace/overnight-joint-final-preview-20261019')
BASELINE = Path('/workspace/overnight-final-preview-20261019')
COMMIT = 'e23613195c356ad53874030f983a30a0e30d639f'
MANIFEST = 'ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7'
PLAN_SHA = '33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e'
sys.path.insert(0, str(NS))
from preview_audio import mux_preview_sfx


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def save(name, value):
    path = OUTPUT / name
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    os.chmod(path, 0o600)
    return {'file': name, 'sha256': sha(path), 'bytes': path.stat().st_size}


receipt = load(OUTPUT / 'PREVIEW_RECEIPT.json')
assert receipt['status'] == 'SOFTWARE_PREVIEW_TECHNICAL_PASS'
assert receipt['completedFrames'] == 150 and receipt['fullDecodeVerified']
assert receipt['range']['startFrame'] == 1400 and receipt['range']['endFrame'] == 1550
assert receipt['bindings']['sourceManifestSHA256'] == MANIFEST
assert receipt['bindings']['originalPlanSHA256'] == PLAN_SHA == sha(INPUT / 'PLAN.json')
assert receipt['hardwareVerified'] is False
assert receipt['originalSceneChanged'] is False and receipt['sourceTimelineReset'] is False
assert len(receipt['checkpoints']) == 5
rows = [json.loads(line) for line in (OUTPUT / 'FRAMES.ndjson').read_text().splitlines()]
old_rows = {r['globalFrame']: r for r in map(json.loads, (BASELINE / 'FRAMES.ndjson').read_text().splitlines())}
assert [row['globalFrame'] for row in rows] == list(range(1400, 1550))
assert [row['localFrame'] for row in rows] == list(range(150))

compact = []
comparisons = []
camera_variants = set()
front_counts = collections.Counter()
area_counts = collections.Counter()
upload_frames = bounds_equal_frames = gl_error_zero_frames = 0
for row in rows:
    frame, local, diagnostic = row['globalFrame'], row['localFrame'], row['diagnostic']
    old = old_rows[frame]
    cb = diagnostic['camera']['camera']['flatBounds']
    mb = diagnostic['terrain']['bounds']
    astra = diagnostic['terrain']['astra']
    owner = diagnostic['overnightV3']
    controls = diagnostic['area'].get('controls') or {}
    fronts = [f['geometry'] for f in controls.get('fronts', [])]
    areas = [a['geometry'] for a in controls.get('areas', [])]
    assert owner['sourceManifestSHA256'] == MANIFEST
    assert owner['frameRangePreserved'] and owner['sourceTimelineReset'] is False
    assert diagnostic['frame'] == frame == diagnostic['universalVideo']['globalFrame']
    assert diagnostic['universalVideo']['testOnly'] is True
    assert diagnostic['sourceIntegrity']['sourceBeforeAreaAndFront'] is True
    assert diagnostic['sourceIntegrity']['fictional65422SceneUsed'] is False
    uploaded = (astra['actualMaterialFactorySelected'] is True and astra['gpuUploadExecuted'] is True
                and astra['testOnly'] is True and astra['uploadedTextureCount'] == 6
                and sorted(astra['selectedSourceRoles']) == ['bathymetry', 'surfaceTexture', 'terrain'])
    assert uploaded and cb == mb and diagnostic['glError'] == 0
    upload_frames += uploaded
    bounds_equal_frames += cb == mb
    gl_error_zero_frames += diagnostic['glError'] == 0
    camera_variants.add(canonical_hash(cb))
    front_counts[len(fronts)] += 1
    area_counts[len(areas)] += 1
    new_png = OUTPUT / 'frames' / f'{local:06d}.png'
    old_png = BASELINE / 'frames' / f'{old["localFrame"]:06d}.png'
    assert sha(new_png) == row['pngSha256'] == sha(old_png) == old['pngSha256']
    assert row['rawRgbaSha256'] == old['rawRgbaSha256']
    assert cb == old['diagnostic']['camera']['camera']['flatBounds']
    compact.append({
        'globalFrame': frame, 'localFrame': local, 'actualRGBA_SHA256': row['rawRgbaSha256'],
        'actualPNG_SHA256': row['pngSha256'], 'cameraBoundsSHA256': canonical_hash(cb),
        'materialBoundsSHA256': canonical_hash(mb), 'cameraMaterialBoundsEqual': cb == mb,
        'actualFrontGeometrySHA256': canonical_hash(fronts), 'actualFrontCount': len(fronts),
        'actualAreaGeometrySHA256': canonical_hash(areas), 'actualAreaCount': len(areas),
        'actualAstraRoleUploadObserved': uploaded, 'actualAstraRoles': sorted(astra['selectedSourceRoles']),
        'uploadedTextureCount': astra['uploadedTextureCount'], 'profileSHA256': owner['profileSHA256'],
        'sourceManifestSHA256': owner['sourceManifestSHA256'], 'globalClockPreserved': True,
        'physicalNvidiaExecuted': False,
    })
    comparisons.append({'globalFrame': frame, 'baselineRawRGBA_SHA256': old['rawRgbaSha256'],
                        'newRawRGBA_SHA256': row['rawRgbaSha256'], 'pixelBitExact': True,
                        'actualPngBytesSHA256Equal': True, 'actualCameraBoundsEqual': True})

assert len(camera_variants) > 1, 'SELECTED_WINDOW_DID_NOT_DEMONSTRATE_CAMERA_MOVEMENT'
evidence_record = save('FRAME_EVIDENCE_150.json', {
    'schema': 'WORLD_ENGINE_ACTUAL_FRAME_EVIDENCE_150_V3', 'sourceCheckpointCommit': COMMIT,
    'sourceManifestSHA256': MANIFEST, 'sourceGlobalRange': [1400, 1550], 'frameCount': 150,
    'hashDefinition': 'SHA256_OF_UTF8_SORTED_KEYS_COMPACT_JSON_FOR_GEOMETRY_AND_BOUNDS; ACTUAL_READPIXELS_RGBA_HASH_FOR_PIXELS',
    'evidenceScope': 'ACTUAL_LOCAL_SWIFTSHADER_DRAW_READPIXELS_NOT_NVIDIA_OR_CANDIDATE_IMAGE_EXECUTION',
    'rawDiagnosticsPubliclyIncluded': False, 'rawDiagnosticsLocalPreserved': True,
    'physicalNvidiaExecuted': False, 'frames': compact,
})
protection_record = save('OVERLAP_FRAME_PROTECTION.json', {
    'schema': 'WORLD_ENGINE_OVERLAPPING_SOFTWARE_FRAME_PROTECTION_V3', 'result': 'BIT_EXACT',
    'scope': 'ALL_150_ACTUAL_SAME_GLOBAL_SOFTWARE_FRAMES_RGBA_PNG_CAMERA', 'sourceRange': [1400, 1550],
    'framesCompared': 150, 'oldSourceCheckpoint': '6108509ba36769be62a2f69561e1b50fc4f5366e',
    'newSourceCheckpoint': COMMIT, 'oldSourceManifestSHA256': 'b98b796154a1c6685fd618beb6bc16e4f200a9967193ece12cee368c8b1d2fb2',
    'newSourceManifestSHA256': MANIFEST, 'newFull150VerifiedByThisComparison': True,
    'candidateImageExecutionVerified': False, 'physicalNvidiaExecuted': False,
    'visualImprovementClaimed': False, 'frameResults': comparisons,
})

checkpoint_checks = []
for checkpoint in receipt['checkpoints']:
    image_file = OUTPUT / checkpoint['file']
    assert sha(image_file) == checkpoint['sha256']
    with Image.open(image_file) as image:
        assert image.size == (1080, 1920)
        data = np.asarray(image.convert('RGB'))
        means = data.mean(axis=(0, 1)).tolist()
        not_black, not_white = bool(np.any(data > 0)), bool(np.any(data < 255))
        assert not_black and not_white
    checkpoint_checks.append({'file': checkpoint['file'], 'globalFrame': checkpoint['globalFrame'],
                              'sha256': checkpoint['sha256'], 'dimensions': [1080, 1920],
                              'meanRGB': means, 'notWholeBlack': not_black, 'notWholeWhite': not_white})

sfx = load(OUTPUT / 'audio/SFX_RECEIPT.json')
pcm = load(OUTPUT / 'audio/SFX_PCM_VERIFICATION.json')
assert sfx['status'] == 'PASS' and sfx['sampleCount'] == 240000
assert len(sfx['cues']) == pcm['authoredCueCount'] == 1 and pcm['peakInt16'] > 0
assert pcm['clippedSamples'] == 0 and sfx['referenceAudioSampled'] is False
assert sfx['license'] == 'CC0-1.0'
plan, request = load(INPUT / 'PLAN.json'), load(INPUT / 'PREVIEW_REQUEST.json')
final = OUTPUT / 'WORLD_ENGINE_OVERNIGHT_PREVIEW_5S_SOFTWARE_SFX.mp4'
assert not final.exists()
mux = mux_preview_sfx(OUTPUT / 'preview.mp4', OUTPUT / 'audio/SFX_PREVIEW_5S.wav', final, plan, request)
save('audio/MUX_RECEIPT.json', mux)
assert mux['status'] == 'PASS' and mux['fullDecode'] == 'PASS'
assert mux['videoFrames'] == 150 and mux['effectiveAudioSamples'] == 240000
assert mux['videoDecodedPixelsUnchanged'] is True and mux['videoFrameTimestampsUnchanged'] is True

warnings = [
    'Qualified schematic territory transitions and partial archival front, not daily surveyed bilateral ownership.',
    'The original global1400..1450 contextual schematic state predates the chapter retreat title; original timing and source qualifiers preserved.',
    'No source-supported national-unit/route or bilateral scalar-territory profile available; none invented.',
    'Local SwiftShader evidence does not verify NVIDIA hardware or execution of the newly built candidate image.',
]
verification = {
    'schema': 'WORLD_ENGINE_FREE_ACTUAL_PREVIEW_VERIFICATION_V3', 'technicalResult': 'PASS_SOFTWARE_ONLY',
    'sourceCheckpointCommit': COMMIT, 'sourceManifestSHA256': MANIFEST, 'sourcePlanRawSHA256': PLAN_SHA,
    'sourceTimelineTotalFrames': 2400, 'sourceRange': [1400, 1550], 'outputFrames': 150,
    'halfOpenFrameOrderNoDuplicates': True, 'uniqueRawFrameHashes': len({r['rawRgbaSha256'] for r in rows}),
    'actualCameraBoundsVariants': len(camera_variants), 'actualGeographicFrontCounts': dict(front_counts),
    'actualSuppliedAreaCounts': dict(area_counts), 'actualAstraUploadDiagnosticFrames': upload_frames,
    'terrainAndNativeCameraBoundsExactFrames': bounds_equal_frames, 'glErrorZeroFrames': gl_error_zero_frames,
    'actual150CaptureEncodeDecodeWallMilliseconds': receipt['totalWallMs'], 'fullDecodeVerified': True,
    'boundedFramesInMemory': max(f['boundedMemory']['simultaneousCapturedFrames'] for f in receipt['fragments']),
    'checkpoints': checkpoint_checks, 'physicalNvidiaExecuted': False, 'candidateImageExecutionVerified': False,
    'full80VideoRendered': False, 'visualQualityApproved': False, 'referenceEquivalentClaimed': False,
    'authoredSfxCueCount': len(sfx['cues']), 'selectedAudioWindowSilent': False, 'warnings': warnings,
}
save('FREE_RENDER_VERIFICATION.json', verification)
save('CHECKOUT_PROVENANCE.json', {
    'sourceCheckpointCommit': COMMIT, 'sourceManifestSHA256': MANIFEST,
    'previewBindingSourceBaseCommit': receipt['bindings']['sourceCommit'],
    'previewBindingSourceCommitMeaning': 'PRESERVED_SOURCE_BASE_NOT_NEW_IMAGE_VERIFICATION',
    'actualExecution': 'LOCAL_CHROMIUM_SWIFTSHADER_FREE_CPU', 'physicalNvidiaExecuted': False,
    'candidateImageExecutionVerified': False, 'priorInitialAndCoherentProofsPreserved': True,
    'originalPlanRawSHA256': PLAN_SHA, 'all150SameGlobalFramesProtected': True,
})
delivery = {
    'schema': 'WORLD_ENGINE_FREE_PREVIEW_DELIVERY_V3', 'result': 'SOFTWARE_PREVIEW_TECHNICAL_PASS',
    'finalVideo': {'file': final.name, 'sha256': sha(final), 'bytes': final.stat().st_size},
    'silentVideoPreserved': {'file': 'preview.mp4', 'sha256': sha(OUTPUT / 'preview.mp4')},
    'sourceCheckpointCommit': COMMIT, 'sourceManifestSHA256': MANIFEST, 'sourceGlobalRange': [1400, 1550],
    'durationSeconds': 5, 'frames': 150, 'fps': 30, 'resolution': [1080, 1920], 'codec': 'h264',
    'audioEnabled': True, 'authoredCueCount': len(sfx['cues']), 'effectiveAudioSilent': False,
    'sampleRate': 48000, 'effectiveAudioSamples': 240000, 'AACCodecPaddingSamples': mux['codecPaddingSamples'],
    'checkpoints': receipt['checkpoints'], 'videoPixelsAndTimestampsUnchangedBySFX': True, 'fullDecode': 'PASS',
    'softwareRenderSeconds': receipt['totalWallMs'] / 1000, 'total150FrameWallTimeMeasured': True,
    'actualCameraBoundsVariants': len(camera_variants), 'cameraMovementDemonstratedInThisWindow': True,
    'frameEvidence': evidence_record, 'overlapProtection': {**protection_record, 'comparedFrames': 150, 'result': 'BIT_EXACT'},
    'physicalNvidiaExecuted': False, 'candidateImageExecutionVerified': False, 'referenceQualityPass': False,
    'userVideoReview': 'REQUIRED', 'full80VideoRendered': False, 'finalPromotion': False,
    'publicDownloadsVerified': False, 'warnings': warnings,
}
save('FINAL_DELIVERY_RECEIPT.json', delivery)
checksums = [f'{sha(final)}  {final.name}']
checksums.extend(f'{sha(OUTPUT / row["file"])}  {row["file"]}' for row in receipt['checkpoints'])
with (OUTPUT / 'FINAL_SHA256SUMS').open('x') as stream:
    stream.write('\n'.join(checksums) + '\n')
os.chmod(OUTPUT / 'FINAL_SHA256SUMS', 0o600)
print(json.dumps({'result': delivery['result'], 'finalVideo': delivery['finalVideo'],
                  'receiptSHA256': sha(OUTPUT / 'FINAL_DELIVERY_RECEIPT.json'),
                  'all150SameGlobalFrames': 'BIT_EXACT', 'cameraBoundsVariants': len(camera_variants),
                  'softwareSeconds': delivery['softwareRenderSeconds'], 'nvidiaHardwareVerified': False}))
