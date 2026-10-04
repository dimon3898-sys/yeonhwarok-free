"""Package reviewed V3 deliverables without replacing any existing file."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

project = Path(__file__).resolve().parents[1]
outputs = project / 'outputs'
delivery = project.parent / 'deliverables'
required = [
    'master_cinematic_20s_v3.mp4', 'master_cinematic_20s_v3_muted.mp4',
    'preview_v3_01.png', 'preview_v3_02.png', 'preview_v3_03.png',
    'preview_v3_04.png', 'preview_v3_hero.png', 'VISUAL_COMPARISON_V2_V3.png',
]
sources = {name: outputs / name for name in required}
sources['QUALITY_REPORT_V3.md'] = project / 'QUALITY_REPORT_V3.md'
sources['CREDITS_V3.txt'] = project / 'assets/v3/CREDITS_V3.txt'
sources['VALIDATION_V3.json'] = outputs / 'master_cinematic_20s_v3_validation_v3.json'
sources['PLAYBACK_V3.json'] = outputs / 'master_cinematic_20s_v3_replay_mobile_playback_validation.json'
sources['AUDIO_VALIDATION_V3.json'] = outputs / 'v3_final_audio_validation.json'
sources['PICTURE_IDENTITY_V3.json'] = outputs / 'v3_final_picture_identity.json'
sources['PRESERVATION_V3.json'] = outputs / 'v3_preservation_final.json'
sources['METADATA_V3.json'] = outputs / 'v3_final_metadata_validation.json'
sources['PLAYBACK_DESKTOP_V3.json'] = outputs / 'master_cinematic_20s_v3_replay_playback_validation.json'
bundle_name = 'CINEMATIC_WORLD_MAP_MASTER_V3_20S.zip'
manifest_name = 'MASTER_V3_SHA256.json'
for name, source in sources.items():
    if not source.is_file():
        raise FileNotFoundError(source)
    if (delivery / name).exists():
        raise FileExistsError(delivery / name)
for name in (bundle_name, manifest_name):
    if (delivery / name).exists():
        raise FileExistsError(delivery / name)
validation = json.loads(sources['VALIDATION_V3.json'].read_text())
assert validation['decoded_full_resolution_frames'] == 600
assert validation['duration'] == 20
assert validation['dimensions'] == [1080, 1920] and validation['fps'] >= 30
assert validation['codec'] == 'h264' and validation['route_progress_monotonic']
assert validation['maximum_near_frozen_earth_run_seconds'] < 3
assert validation['maximum_camera_angle_step_degrees'] < 3
for key in ('black_frames', 'empty_earth_frames', 'exact_duplicate_frames',
            'text_clipping', 'webgl_errors', 'aircraft_outside_safe_scene',
            'label_plane_proximity', 'label_label_overlaps'):
    assert not validation[key], key
playback = json.loads(sources['PLAYBACK_V3.json'].read_text())
assert playback['ended'] and playback['currentTime'] == 20 and not playback['videoError']
assert playback['audioDecodedBytes'] > 0
assert not playback['droppedVideoFrames'] and not playback['corruptedVideoFrames']
assert playback['totalVideoFrames'] == 600
audio = json.loads(sources['AUDIO_VALIDATION_V3.json'].read_text())
assert audio['stream_duration'] == 20 and audio['actual_aac_true_peak_dbtp'] < -1
assert abs(audio['soundtrack_alignment_lag_seconds']) <= 1 / 30
assert audio['alignment_correlation'] > .95
identity = json.loads(sources['PICTURE_IDENTITY_V3.json'].read_text())
assert identity['frames'] == 600 and identity['matches_sound_master_all_frames']
assert identity['matches_reviewed_r15_first_ten_seconds']
preservation = json.loads(sources['PRESERVATION_V3.json'].read_text())
assert preservation['original_project_files_checked'] == 197
assert not preservation['changed_original_files'] and not preservation['missing_original_files']
assert not preservation['tracked_repository_changes_before_v3_staging']
metadata = json.loads(sources['METADATA_V3.json'].read_text())
assert len(metadata['files']) == 2
assert all(f['source_credit_present'] and f['cc_by_4_link_present'] for f in metadata['files'])
delivery.mkdir(exist_ok=True)
records = {}
for name, source in sources.items():
    # Exclusive destination creation also guards against concurrent collisions.
    with source.open('rb') as src, (delivery / name).open('xb') as dest:
        shutil.copyfileobj(src, dest)
    data = (delivery / name).read_bytes()
    records[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
with (delivery / manifest_name).open('x') as file:
    json.dump({'files': records, 'scope': 'V3 only; V1 and V2 retained'}, file, indent=2)
with zipfile.ZipFile(delivery / bundle_name, 'x', compression=zipfile.ZIP_DEFLATED,
                     compresslevel=6) as archive:
    for name in [*sources, manifest_name]:
        archive.write(delivery / name, arcname=name)
with zipfile.ZipFile(delivery / bundle_name) as archive:
    assert archive.testzip() is None
sizes = {name: (delivery / name).stat().st_size for name in [*sources, manifest_name, bundle_name]}
print(json.dumps({'delivery': str(delivery), 'sizes': sizes,
                  'github_regular_git_limit_bytes': 100 * 1024 * 1024,
                  'requires_large_file_method': [name for name, size in sizes.items()
                                                 if size >= 100 * 1024 * 1024]}, indent=2))
