"""Independent, immutable quality promotion; preserve the previous certificate."""
import hashlib
import json
from pathlib import Path

APP_ROOT=Path(__file__).resolve().parents[1]
REPO_ROOT=APP_ROOT.parent
PROMOTION_PATH=APP_ROOT/'data/production_rhythm_promotion_v001.json'


def rhythm_default_status(path=None):
    path=Path(path or PROMOTION_PATH)
    inactive=dict(active=False,preset='LEGACY',reason='rhythm_short_test_not_promoted')
    if not path.is_file():return inactive
    try:
        record=json.loads(path.read_text());root=REPO_ROOT if record.get('path_base')=='repository' else APP_ROOT
        evidence=root/record['evidence_path'];movie=root/record['final_mp4_path']
        valid=record.get('version')=='v1' and record.get('promoted') is True
        valid=valid and hashlib.sha256(evidence.read_bytes()).hexdigest()==record['evidence_sha256']
        qc=json.loads(evidence.read_text())
        required=['passed','rendered_mp4_verified','mobile_full_playback_passed','automatic_qc_passed',
                  'sfx_frame_sync_passed','sfx_repeat_prevention_passed','tts_ducking_fixture_passed',
                  'audio_only_cache_verified','approved_graphics_preserved','no_75s_render']
        valid=valid and all(qc.get(key) is True for key in required)
        valid=valid and 10<=float(qc['duration'])<=15 and qc.get('full_video_speedup') is False
        valid=valid and int(qc['decoded_frames'])==round(float(qc['duration'])*30)
        valid=valid and hashlib.sha256(movie.read_bytes()).hexdigest()==record['final_mp4_sha256']
        valid=valid and bool(record.get('source_manifest'))
        for relative,expected in record.get('source_manifest',{}).items():
            candidate=(APP_ROOT/relative).resolve()
            if not candidate.is_relative_to(APP_ROOT) or hashlib.sha256(candidate.read_bytes()).hexdigest()!=expected:valid=False;break
        return dict(active=bool(valid),preset='PRODUCTION_DEFAULT' if valid else 'LEGACY',
                    reason='rhythm_quality_gated_promotion' if valid else 'rhythm_promotion_evidence_invalid',
                    recommended=dict(pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True),record=record)
    except (OSError,ValueError,KeyError,TypeError):return {**inactive,'reason':'rhythm_promotion_evidence_invalid'}
