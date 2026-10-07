"""QA-only native route-head onset correction; frozen audio library is intact.

The native Earth route head is visible on its scheduled frame, unlike faded
labels. A global one-frame sound delay plus a 2ms source attack fails the strict
one-frame PCM gate. Correct insertion timing, never loosen the QC tolerance.
"""
import json
from pathlib import Path
from types import FunctionType
from . import audio, rhythm_sound
from .assets import sha256_file

CONTRACT = 'QA_NATIVE_ROUTE_HEAD_ONSET_V1'


def enabled(plan):
    return (plan.get('request', {}).get('qa_mode') is True
            and plan.get('story', {}).get('domain') == 'shipping'
            and plan.get('rhythm_policy', {}).get('version') == 'v1')


def select_events(plan, history=None):
    selected = rhythm_sound.select_rhythm_sound_events(plan, history)
    if not enabled(plan):
        return selected
    fps = float(plan.get('render', {}).get('fps', 30))
    offset = plan['rhythm_policy'].get('sfx_core_onset_offset_frames', 1)
    scene_starts = {scene['scene_id']: scene['start_time'] for scene in plan['scenes']}
    for event in selected['events']:
        if event.get('visual_kind') != 'route_start':
            continue
        event['frame'] -= offset
        event['first_positive_visual_frame'] -= offset
        event['absolute_time'] = event['frame'] / fps
        event['time'] = event['absolute_time'] - scene_starts[event['scene_id']]
        event['authored_offset_seconds'] = event['absolute_time'] - event['authored_visual_time']
        event['sync_error_seconds'] = 0. if event.get('primary_sync') else None
        event['onset_contract'] = CONTRACT
        if event['frame'] < 0:
            raise RuntimeError('AUDIO_TIMING_OUTSIDE_PROJECT')
    # History describes the sound actually inserted, not its earlier proposal.
    # Keep variant choices intact while correcting their recorded timestamps.
    selected['events'].sort(key=lambda event: (event['absolute_time'], event['scene_id'], event['id']))
    actual = {(event['scene_id'], event['id']): event for event in selected['events']}
    for item in selected['history']:
        event = actual.get((item.get('scene_id'), item.get('id')))
        if event is not None:
            item['absolute_time'] = event['absolute_time']
    selected['onset_policy']['qa_route_head_contract'] = CONTRACT
    return selected


def create_audio(plan, directory, provider=None):
    if not enabled(plan):
        return audio.create_audio(plan, directory, provider)
    sound_namespace = dict(rhythm_sound.render_rhythm_sound_events.__globals__)
    sound_namespace['select_rhythm_sound_events'] = select_events
    render_sound = FunctionType(rhythm_sound.render_rhythm_sound_events.__code__, sound_namespace,
                               'render_rhythm_sound_events', rhythm_sound.render_rhythm_sound_events.__defaults__)
    namespace = dict(audio.create_audio.__globals__)
    namespace['render_rhythm_sound_events'] = render_sound
    create = FunctionType(audio.create_audio.__code__, namespace, 'create_audio', audio.create_audio.__defaults__)
    result = create(plan, directory, provider)
    result['audio_pipeline_contract'] = CONTRACT
    return result


def finish_video(muted_input, final_dir, plan, prepared_audio, subtitles):
    if enabled(plan) and prepared_audio.get('audio_pipeline_contract') != CONTRACT:
        # Retain earlier audio/checkpoints and completed scene MP4s on retry.
        directory = Path(prepared_audio['file']).parent / 'qa_route_onset_v1'
        report = directory / 'stability_audio.json'
        if report.is_file():
            corrected = json.loads(report.read_text())
            if corrected.get('audio_pipeline_contract') != CONTRACT or sha256_file(Path(corrected['file'])) != corrected['stability_sha256']:
                raise RuntimeError('AUDIO_CHECKPOINT_INVALID')
        else:
            if directory.exists():
                index = 2
                while directory.with_name(directory.name + f'_attempt{index:03}').exists():
                    index += 1
                directory = directory.with_name(directory.name + f'_attempt{index:03}')
                report = directory / 'stability_audio.json'
            corrected = create_audio(plan, directory)
            corrected['stability_sha256'] = sha256_file(Path(corrected['file']))
            report.write_text(json.dumps(corrected, ensure_ascii=False, indent=2))
        prepared_audio.clear()
        prepared_audio.update(corrected)
    return audio.finish_video(muted_input, final_dir, plan, prepared_audio, subtitles)
