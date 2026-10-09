"""Sentence synthesis precedes Production visual allocation.

The single frame clock controls every visual boundary. Voice windows instead
come from actual decoded PCM samples; they are utterance measurements, never
uniform word alignment. Legacy fixed QA and its audio functions are unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from types import FunctionType, SimpleNamespace

import numpy as np
from scipy.io import wavfile

from . import audio, audio_stability
from .frame_grid import FrameGrid
from .storage import atomic_json, plan_hash

VERSION = 'MEASURED_SEMANTIC_TIMELINE_v022'
TIMING_METHOD = 'sentence_synthesis_measured_pcm'
CONFIDENCE = 'measured_utterance_window_only'


def registered_production_sources():
    """Explicit JSON-Schema descriptors bound to the native GIS manifest."""
    from .gis import coordinate_source_report
    from .infographic_contract import _read_pair
    records={s['id']:deepcopy(s)for s in coordinate_source_report()}
    for source in _read_pair('SOURCES.json')['sources']:
        if source['id']in records:continue
        records[source['id']]=dict(id=source['id'],url=source['url'],author=source.get('author','Natural Earth'),
            license=source['license']['spdx'],version=source['version'],
            source_file=source['file'],source_file_sha256=source['sha256'],
            source_manifest_record_sha256=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest())
    return records


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ids(value):
    return (isinstance(value, list) and all(isinstance(v, str) and v for v in value)
            and len(value) == len(set(value)))


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('SEMANTIC_TIMING_POLICY_INVALID')
    return value


def _script(record):
    if not isinstance(record, dict) or not isinstance(record.get('text'), str) or not record['text'].strip():
        raise ValueError('SEMANTIC_SCRIPT_REQUIRED')
    text, entries = record['text'], record.get('segments')
    if not isinstance(entries, list) or not entries:
        raise ValueError('SEMANTIC_SCRIPT_SEGMENTS_REQUIRED')
    ids, previous = set(), 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('SEMANTIC_SCRIPT_RANGE_INVALID')
        a, b = entry.get('start_char'), entry.get('end_char')
        if (type(a) is not int or type(b) is not int or not previous <= a < b <= len(text)
                or not text[a:b].strip() or text[previous:a].strip()):
            raise ValueError('SEMANTIC_SCRIPT_RANGE_INVALID')
        if not isinstance(entry.get('id'), str) or not entry['id'] or entry['id'] in ids:
            raise ValueError('SEMANTIC_SCRIPT_ID_INVALID')
        for key in ('claim_ids', 'source_ids', 'target_ids'):
            if not _ids(entry.get(key)) or not entry[key]:
                raise ValueError('SEMANTIC_REFERENCE_LIST_INVALID')
        if not _ids(entry.get('event_ids', [])):
            raise ValueError('SEMANTIC_REFERENCE_LIST_INVALID')
        ids.add(entry['id'])
        previous = b
    if text[previous:].strip():
        raise ValueError('SEMANTIC_SCRIPT_RANGE_INVALID')
    return text, deepcopy(entries)


def _sentence_ranges(text, start, end):
    """Keep exact source indices; punctuation splitting is not alignment."""
    cursor = start
    for match in re.finditer(r'[.!?。！？]+(?=\s|$)|\n+', text[start:end]):
        stop = start + match.end()
        a, b = cursor, stop
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b-1].isspace():
            b -= 1
        if a < b:
            yield a, b
        cursor = stop
    a, b = cursor, end
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b-1].isspace():
        b -= 1
    if a < b:
        yield a, b


def _relative_file(directory, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError('SEMANTIC_AUDIO_PATH_INVALID')
    root = Path(directory).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root or not path.is_file():
        raise ValueError('SEMANTIC_AUDIO_PATH_INVALID')
    return path


def _decoded(path):
    signal = audio._stereo(Path(path))
    if (signal.ndim != 2 or signal.shape[1] != 2 or not len(signal)
            or not np.all(np.isfinite(signal)) or np.max(np.abs(signal)) <= 1e-9):
        raise RuntimeError('SEMANTIC_SENTENCE_AUDIO_INVALID')
    return signal


def build_semantic_timeline(script_record, directory, provider=None, *, fps=30,
                            enabled=True, camera_arrival_seconds=.4,
                            after_state_hold_seconds=.8, language=None, speed=155):
    """Return measured semantic segments and a dynamic integer visual grid.

Each authored semantic range can contain several sentences. They are separately
    synthesized and measured, retaining one semantic ID and explicit sentence
    windows. Hold and arrival are visual planning policies, not speech estimates.
    Missing TTS produces an explicit disabled/unready record, not fake duration.
    """
    text, definitions = _script(script_record)
    if type(enabled) is not bool or type(speed) is not int or not 1 <= speed <= 500:
        raise ValueError('SEMANTIC_TTS_OPTIONS_INVALID')
    if language is not None and (not isinstance(language, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', language)):
        raise ValueError('SEMANTIC_TTS_LANGUAGE_INVALID')
    if isinstance(fps, bool):
        raise ValueError('SEMANTIC_FPS_INVALID')
    clock = FrameGrid(fps)
    arrival = clock.frames(_seconds(camera_arrival_seconds), 'ceil')
    hold = max(1, clock.frames(_seconds(after_state_hold_seconds), 'ceil'))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    receipt_path = directory / 'semantic-timeline.json'
    if receipt_path.exists() or (directory / 'narration_v022.wav').exists():
        raise FileExistsError(receipt_path)
    report = dict(version=VERSION, script_text=text,
                  script_sha256=hashlib.sha256(text.encode()).hexdigest(), fps=str(clock.fps),
                  enabled=enabled, passed=False, status='NOT_MEASURED', segments=[],
                  total_frames=None, duration=None, voice=None, errors=[], warnings=[],
                  word_alignment=False, direct_listening='NOT_RUN', physical_gpu='NOT_RUN')
    if not enabled:
        report['status'] = 'DISABLED_BY_REQUEST'
        atomic_json(receipt_path, report, exclusive=True)
        return report
    if provider is None:
        try:
            provider = audio.ESpeakProvider()
        except RuntimeError:
            report.update(enabled=False, status='DISABLED_TTS_PROVIDER_UNAVAILABLE')
            report['errors'].append(dict(code='TTS_PROVIDER_UNAVAILABLE'))
            atomic_json(receipt_path, report, exclusive=True)
            return report
    provider_name = getattr(provider, 'name', '')
    if not isinstance(provider_name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', provider_name):
        raise ValueError('SEMANTIC_TTS_PROVIDER_ID_INVALID')
    report['provider'] = provider_name
    report['voice_quality'] = 'NOT_REVIEWED'
    if provider_name == 'ESPEAK_OFFLINE':
        report['warnings'].append(dict(code='OFFLINE_FALLBACK_VOICE_QUALITY',
                                      message='Offline provider; naturalness and pronunciation need listening review'))
    cursor, samples, ordinal = 0, [], 0
    try:
        for definition in definitions:
            start = cursor + arrival
            offset = round(Fraction(start, 1) / clock.fps * audio.SR)
            sentence_windows, pieces = [], []
            sentence_offset = offset
            for a, b in _sentence_ranges(text, definition['start_char'], definition['end_char']):
                ordinal += 1
                name = f'sentence_{ordinal:04}.wav'
                destination = directory / name
                if destination.exists():
                    raise FileExistsError(destination)
                sentence_language = language or ('ko' if re.search(r'[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]', text[a:b]) else 'en')
                # Duration metadata from the provider is not allocation input.
                provider.synthesize(text[a:b], destination, language=sentence_language, speed=speed)
                signal = _decoded(destination)
                sentence_windows.append(dict(script_start_char=a, script_end_char=b, text=text[a:b],
                    speech_start=sentence_offset/audio.SR, speech_end=(sentence_offset+len(signal))/audio.SR,
                    sample_count=len(signal), sample_rate=audio.SR, file=name, sha256=_sha(destination)))
                pieces.append(signal)
                sentence_offset += len(signal)
            segment_signal = np.concatenate(pieces, axis=0)
            end = clock.frames(Fraction(offset+len(segment_signal), audio.SR), 'ceil')
            visual_end = end + hold
            report['segments'].append(dict(id=definition['id'],
                script_range=dict(text=text[definition['start_char']:definition['end_char']],
                                  start_char=definition['start_char'], end_char=definition['end_char']),
                claim_ids=definition['claim_ids'], source_ids=definition['source_ids'],
                target_ids=definition['target_ids'], event_ids=definition.get('event_ids', []),
                speech_start=offset/audio.SR, speech_end=(offset+len(segment_signal))/audio.SR,
                sample_count=len(segment_signal), sample_rate=audio.SR, timing_method=TIMING_METHOD,
                confidence=CONFIDENCE, word_alignment=False, start_frame=start, end_frame=end,
                sentence_windows=sentence_windows,
                visual_window=dict(start_frame=cursor, camera_arrival_frame=start, reveal_frame=start,
                    speech_end_frame=end, after_state_start_frame=end, end_frame=visual_end,
                    frame_count=visual_end-cursor)))
            samples.append((offset, segment_signal))
            cursor = visual_end
    except (RuntimeError, OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        report.update(status='TTS_MEASUREMENT_FAILED')
        report['errors'].append(dict(code='TTS_MEASUREMENT_FAILED', exception_type=type(error).__name__,
                                    sentence_index=ordinal,command_category='TTS_SYNTHESIS_OR_PCM_DECODE'))
        atomic_json(receipt_path, report, exclusive=True)
        return report
    total_samples = math.ceil(Fraction(cursor, 1) / clock.fps * audio.SR)
    voice = np.zeros((total_samples, 2), np.float32)
    for offset, signal in samples:
        voice[offset:offset+len(signal)] = signal
    voice_path = directory / 'narration_v022.wav'
    with voice_path.open('xb') as stream:
        wavfile.write(stream, audio.SR, voice)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    report.update(passed=True, status='MEASURED', total_frames=cursor,
                  duration=clock.seconds(cursor), voice=dict(file=voice_path.name,
                    sha256=_sha(voice_path), sample_rate=audio.SR,
                    sample_count=len(voice), channels=2))
    checked = validate_semantic_timeline(report, directory=directory)
    if not checked['passed']:
        report.update(passed=False, status='MEASUREMENT_VALIDATION_FAILED', errors=checked['errors'])
    atomic_json(receipt_path, report, exclusive=True)
    return report


def validate_semantic_timeline(report, *, directory=None):
    errors = []
    def reject(code):
        if dict(code=code) not in errors:
            errors.append(dict(code=code))
    try:
        if (report.get('version') != VERSION or report.get('status') != 'MEASURED'
                or report.get('enabled') is not True or report.get('passed') is not True
                or report.get('word_alignment') is not False or report.get('errors') != []):
            raise ValueError('SEMANTIC_MEASURED_TIMELINE_REQUIRED')
        if not isinstance(report.get('fps'),str):raise ValueError('SEMANTIC_FPS_INVALID')
        clock = FrameGrid(report['fps'])
        text = report['script_text']
        if hashlib.sha256(text.encode()).hexdigest() != report['script_sha256']:
            reject('SEMANTIC_SCRIPT_HASH_MISMATCH')
        cursor, ids,previous_char = 0, set(),0
        if not isinstance(report['segments'], list) or not report['segments']:
            raise ValueError('SEMANTIC_MEASURED_SEGMENTS_REQUIRED')
        for segment in report['segments']:
            if segment['id'] in ids:
                reject('SEMANTIC_DUPLICATE_SEGMENT_ID')
            ids.add(segment['id'])
            source = segment['script_range']
            if (type(source['start_char']) is not int or type(source['end_char']) is not int
                    or not previous_char <= source['start_char'] < source['end_char'] <= len(text)
                    or text[previous_char:source['start_char']].strip()
                    or source['text'] != text[source['start_char']:source['end_char']]):
                reject('SEMANTIC_SCRIPT_RANGE_INVALID')
            previous_char=source['end_char']
            for key in ('claim_ids', 'source_ids', 'target_ids'):
                if not _ids(segment[key]) or not segment[key]:
                    reject('SEMANTIC_REFERENCE_LIST_INVALID')
            if (segment['timing_method'] != TIMING_METHOD or segment['confidence'] != CONFIDENCE
                    or segment['word_alignment'] is not False):
                reject('SEMANTIC_ALIGNMENT_CLAIM_INVALID')
            if not _ids(segment.get('event_ids',[])):reject('SEMANTIC_REFERENCE_LIST_INVALID')
            if (type(segment['sample_count']) is not int or segment['sample_count'] <= 0
                    or type(segment['sample_rate']) is not int or segment['sample_rate'] != audio.SR):
                reject('SEMANTIC_SAMPLE_COUNT_INVALID')
            a, b = segment['speech_start'], segment['speech_end']
            if (type(a) not in (int, float) or type(b) not in (int, float)
                    or not math.isfinite(a) or not math.isfinite(b) or a < 0 or b <= a
                    or abs((b-a)*audio.SR-segment['sample_count']) > 1e-5):
                reject('SEMANTIC_SAMPLE_DURATION_MISMATCH')
            window = segment['visual_window']
            if (set(window)!={'start_frame','camera_arrival_frame','reveal_frame','speech_end_frame','after_state_start_frame','end_frame','frame_count'}
                    or any(type(window[k]) is not int for k in window)
                    or type(segment['start_frame'])is not int or type(segment['end_frame'])is not int):
                reject('SEMANTIC_FRAME_GRID_INVALID')
            if (window['start_frame'] != cursor or window['frame_count'] != window['end_frame']-cursor
                    or not cursor <= window['camera_arrival_frame'] == window['reveal_frame']
                    == segment['start_frame'] < segment['end_frame'] == window['speech_end_frame']
                    == window['after_state_start_frame'] < window['end_frame']):
                reject('SEMANTIC_FRAME_GRID_INVALID')
            if (clock.frames(a) != segment['start_frame'] or clock.frames(b, 'ceil') != segment['end_frame']):
                reject('SEMANTIC_AUDIO_FRAME_MISMATCH')
            spoken_cursor, spoken_samples = a, 0
            if not isinstance(segment['sentence_windows'],list)or not segment['sentence_windows']:
                raise ValueError('SEMANTIC_SENTENCE_WINDOW_MISMATCH')
            for sentence in segment['sentence_windows']:
                lo, hi = sentence['script_start_char'], sentence['script_end_char']
                if (type(lo) is not int or type(hi) is not int
                        or not source['start_char'] <= lo < hi <= source['end_char']
                        or text[lo:hi] != sentence['text']):
                    reject('SEMANTIC_SENTENCE_SOURCE_MISMATCH')
                if (any(type(sentence[k])not in (int,float)or not math.isfinite(sentence[k])for k in ('speech_start','speech_end'))
                        or type(sentence['sample_count'])is not int or sentence['sample_count']<=0
                        or type(sentence['sample_rate'])is not int or sentence['sample_rate'] != audio.SR
                        or sentence['speech_end']<=sentence['speech_start']
                        or abs(sentence['speech_start']-spoken_cursor) > 1e-9
                        or abs((sentence['speech_end']-sentence['speech_start'])*audio.SR-sentence['sample_count']) > 1e-5):
                    reject('SEMANTIC_SENTENCE_WINDOW_MISMATCH')
                spoken_cursor = sentence['speech_end']
                spoken_samples += sentence['sample_count']
                if directory is not None:
                    file = _relative_file(directory, sentence['file'])
                    if _sha(file) != sentence['sha256'] or len(_decoded(file)) != sentence['sample_count']:
                        reject('SEMANTIC_SENTENCE_AUDIO_HASH_MISMATCH')
            if spoken_samples != segment['sample_count'] or abs(spoken_cursor-b) > 1e-9:
                reject('SEMANTIC_SENTENCE_WINDOW_MISMATCH')
            cursor = window['end_frame']
        if text[previous_char:].strip():reject('SEMANTIC_SCRIPT_RANGE_INVALID')
        if (type(report['total_frames']) is not int or report['total_frames'] != cursor
                or abs(report['duration']-clock.seconds(cursor)) > 1e-9):
            reject('SEMANTIC_FRAME_TOTAL_MISMATCH')
        voice = report['voice']
        expected_samples = math.ceil(Fraction(cursor, 1)/clock.fps*audio.SR)
        if (type(voice['sample_count'])is not int or type(voice['sample_rate'])is not int or type(voice['channels'])is not int
                or voice['sample_count'] != expected_samples or voice['sample_rate'] != audio.SR or voice['channels'] != 2):
            reject('SEMANTIC_VOICE_DURATION_MISMATCH')
        if directory is not None:
            voice_path = _relative_file(directory, voice['file'])
            if _sha(voice_path) != voice['sha256'] or len(audio._stereo(voice_path)) != expected_samples:
                reject('SEMANTIC_VOICE_HASH_MISMATCH')
    except (KeyError, TypeError, ValueError, AttributeError, OSError, RuntimeError) as error:
        reject(str(error) if isinstance(error, ValueError) and str(error).startswith('SEMANTIC_')
               else 'SEMANTIC_TIMELINE_INVALID')
    return dict(passed=not errors, errors=errors, word_alignment=False, physical_gpu='NOT_RUN')


def prepare_production_audio(plan, timeline, timeline_directory, output_directory):
    """Reuse the original mixer/ducking/subtitle path without synthesizing twice.

FunctionType-local globals preserve concurrent jobs: no audio-module monkey
    patch, arbitrary user-file bypass, second mixer or new sound library.
    """
    checked = validate_semantic_timeline(timeline, directory=timeline_directory)
    if not checked['passed']:
        raise ValueError('SEMANTIC_AUDIO_TIMELINE_INVALID')
    if abs(float(plan['duration'])-timeline['duration']) > 1e-9:
        raise ValueError('SEMANTIC_AUDIO_PLAN_DURATION_MISMATCH')
    voice_path = _relative_file(timeline_directory, timeline['voice']['file'])
    signal = audio._stereo(voice_path)
    # The inherited mixer uses nearest audio samples for its output clock.
    # Rational video fps may make the padding envelope one sample longer.
    # Only terminal silence can be removed, never measured speech.
    mixer_samples = round(timeline['duration']*audio.SR)
    if len(signal) > mixer_samples:
        if np.any(signal[mixer_samples:] != 0):
            raise ValueError('SEMANTIC_AUDIO_NON_SILENT_TAIL')
        signal = signal[:mixer_samples]
    cues, metadata = [], []
    for segment in timeline['segments']:
        owners = [s for s in plan['scenes'] if float(s['start_time']) <= segment['speech_start']+1e-9
                  and float(s['start_time'])+float(s['duration']) >= segment['speech_end']-1e-9]
        if len(owners) != 1:
            raise ValueError('SEMANTIC_AUDIO_SCENE_SCOPE_INVALID')
        scene = owners[0]
        if scene.get('narration', '').strip() != segment['script_range']['text'].strip():
            raise ValueError('SEMANTIC_AUDIO_SCENE_SCRIPT_MISMATCH')
        for sentence in segment['sentence_windows']:
            cues.append(dict(start=sentence['speech_start'], end=sentence['speech_end'], text=sentence['text'],
                scene_id=scene['scene_id'], timing_source=TIMING_METHOD,
                declared_narration_event_ids=deepcopy(scene.get('narration_event_ids', [])),
                declared_claim_ids=deepcopy(segment['claim_ids']), semantic_segment_ref=segment['id'],
                word_alignment=False))
        metadata.append(dict(provider='MEASURED_SENTENCE_REUSE', scene_id=scene['scene_id'],
            duration=segment['sample_count']/audio.SR, placed_start=segment['speech_start'],
            source_sha256=timeline['voice']['sha256'], word_alignment=False))
    output_directory = Path(output_directory)
    expected_semantic = dict(version=VERSION, script_sha256=timeline['script_sha256'],
        voice_sha256=timeline['voice']['sha256'], timing_method=TIMING_METHOD,
        plan_sha256=plan_hash(plan), word_alignment=False,
        measured_duration=timeline['duration'], resynthesized=False)
    report_path = output_directory/'audio_report.json'
    subtitle_path = output_directory/'subtitle_report.json'
    reuse_path = output_directory/'semantic-audio-reuse.json'
    if report_path.exists():
        try:
            result = json.loads(report_path.read_text())
            receipt = json.loads(reuse_path.read_text())
            subtitles = json.loads(subtitle_path.read_text())
            mixed = output_directory/'mix.wav'
            mastered = result['measured_mastering']
            if (result != receipt or result['semantic_timeline'] != expected_semantic
                    or Path(result['file']).resolve() != mixed.resolve()
                    or result['sha256'] != _sha(mixed)
                    or result['sample_count'] != mixer_samples
                    or len(audio._stereo(mixed)) != mixer_samples
                    or result['duration'] != mixer_samples/audio.SR
                    or mastered != dict(version='PCM_EOF_FLUSH_SAMPLE_CLOCK_v022',
                        sample_rate=audio.SR, expected_sample_count=mixer_samples,
                        actual_sample_count=mixer_samples, duration=mixer_samples/audio.SR,
                        eof_flushed=True, silence_padding=False, normalization_unchanged=True)
                    or result['subtitle_report_sha256'] != _sha(subtitle_path)
                    or bool(subtitles['enabled']) != bool(plan.get('options',{}).get('subtitles',False))):
                raise ValueError('SEMANTIC_AUDIO_CHECKPOINT_INVALID')
            if subtitles['enabled']:
                ass = output_directory/'subtitles.ass'
                if (Path(subtitles['path']).resolve() != ass.resolve()
                        or subtitles['sha256'] != _sha(ass)
                        or not audio.validate_subtitle_layout(subtitles,timeline['duration'])['passed']):
                    raise ValueError('SEMANTIC_AUDIO_CHECKPOINT_INVALID')
            elif subtitles.get('path') is not None:
                raise ValueError('SEMANTIC_AUDIO_CHECKPOINT_INVALID')
            return dict(audio=result, subtitles=subtitles, timing=checked)
        except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
            raise ValueError('SEMANTIC_AUDIO_CHECKPOINT_INVALID') from error
    def measured_narration(bound_plan, audio_dir, provider=None):
        if bound_plan is not plan:
            raise ValueError('SEMANTIC_AUDIO_PLAN_IDENTITY_INVALID')
        return signal.astype(np.float64)*.78, deepcopy(cues), deepcopy(metadata)
    def measured_mastering(command):
        command = list(command)
        # loudnorm buffers samples. Its inherited output -t can terminate the
        # stream before EOF flush on a non-integral measured duration. Keep the
        # exact original measured filter/mix, allow its delayed tail to flush,
        # then trim by the decoded input sample clock rather than output time.
        # This local call boundary never changes the legacy audio module.
        if ('-af' in command and '-i' in command
                and Path(command[command.index('-i')+1]).name == 'mix_raw.wav'
                and Path(command[-1]).name == 'mix.wav'
                and command[command.index('-af')+1].startswith('loudnorm=')):
            raw = Path(command[command.index('-i')+1])
            rate, raw_signal = wavfile.read(raw)
            if rate != audio.SR or len(raw_signal) != mixer_samples:
                raise RuntimeError('SEMANTIC_MASTERING_INPUT_CLOCK_INVALID')
            if '-t' in command:
                index = command.index('-t')
                del command[index:index+2]
            index = command.index('-af')+1
            command[index] += f',aresample={audio.SR},atrim=end_sample={mixer_samples}'
        return audio._run(command)
    namespace = dict(audio.create_audio.__globals__)
    namespace['_narration'] = measured_narration
    namespace['_run'] = measured_mastering
    mixer = FunctionType(audio.create_audio.__code__, namespace, 'measured_semantic_mix', audio.create_audio.__defaults__)
    proxy = SimpleNamespace(**{**audio.__dict__, 'create_audio': mixer})
    stable_namespace = dict(audio_stability.create_audio.__globals__)
    stable_namespace['audio'] = proxy
    stable_mixer = FunctionType(audio_stability.create_audio.__code__, stable_namespace,
                               'stable_measured_semantic_mix', audio_stability.create_audio.__defaults__)
    result = stable_mixer(plan, Path(output_directory))
    final_signal = audio._stereo(Path(result['file']))
    if len(final_signal) != mixer_samples:
        raise RuntimeError('SEMANTIC_MASTERING_OUTPUT_CLOCK_INVALID')
    # Verify the physical mastered file rather than inherited len(pre-mix).
    result['duration'] = len(final_signal)/audio.SR
    result['sample_count'] = len(final_signal)
    result['measured_mastering'] = dict(version='PCM_EOF_FLUSH_SAMPLE_CLOCK_v022',
        sample_rate=audio.SR, expected_sample_count=mixer_samples,
        actual_sample_count=len(final_signal), duration=len(final_signal)/audio.SR,
        eof_flushed=True, silence_padding=False, normalization_unchanged=True)
    subtitles = audio.create_subtitles(plan, Path(output_directory), cues)
    if subtitles['enabled']:
        subtitles['sha256'] = _sha(subtitles['path'])
    # The inherited renderer consumes these two checkpoint receipts. Persist
    # both before handoff so it reuses the ASS instead of opening it twice.
    atomic_json(Path(output_directory)/'subtitle_report.json', subtitles, exclusive=True)
    result['semantic_timeline'] = expected_semantic
    result['subtitle_report_sha256'] = _sha(subtitle_path)
    result['sha256'] = _sha(result['file'])
    atomic_json(Path(output_directory)/'audio_report.json', result)
    atomic_json(Path(output_directory)/'semantic-audio-reuse.json', result, exclusive=True)
    return dict(audio=result, subtitles=subtitles, timing=checked)


def generate_production_plan(script_record, directory, provider=None, *, fps=30):
    """Build real variable Scenes after authored sentence PCM is measured.

    Claims, targets, source records, state changes and display text are required
    authored inputs. The builder changes only their time allocation. It does not
    parse a topic into invented states or copy the fixed QA camera fixture.
    """
    from .gis import resolve_location, verified_coordinate
    from .presets import camera_state, CAMERA_PRESETS
    from .infographic_contract import load_registry, prepare_infographic, canonical_sha
    from .infographic_framing import fit_native_geometry, select_regional_lod
    text, definitions = _script(script_record)
    registry = load_registry()
    geometry_by_id = {r['id']:r for r in registry['geometries']}
    claims = deepcopy(script_record.get('claims'))
    sources = deepcopy(script_record.get('sources'))
    authored = deepcopy(script_record.get('events'))
    if (not isinstance(claims,list) or not claims or not isinstance(sources,list) or not sources
            or not isinstance(authored,list) or not authored):
        raise ValueError('SEMANTIC_AUTHORED_PRODUCTION_REQUIRED')
    claim_by_id = {c.get('id'):c for c in claims if isinstance(c,dict)}
    source_ids = {s.get('id') for s in sources if isinstance(s,dict)}
    event_by_id = {e.get('id'):e for e in authored if isinstance(e,dict)}
    if (len(claim_by_id)!=len(claims) or len(source_ids)!=len(sources)
            or len(event_by_id)!=len(authored) or None in claim_by_id or None in source_ids or None in event_by_id):
        raise ValueError('SEMANTIC_AUTHORED_IDS_INVALID')
    used = []
    for definition in definitions:
        if (any(cid not in claim_by_id for cid in definition['claim_ids'])
                or any(sid not in source_ids for sid in definition['source_ids'])
                or not definition.get('event_ids')):
            raise ValueError('SEMANTIC_AUTHORED_REFERENCE_INVALID')
        for eid in definition['event_ids']:
            event = event_by_id.get(eid)
            if (event is None or event.get('semantic_segment_ref')!=definition['id']
                    or event.get('claim_id') not in definition['claim_ids']):
                raise ValueError('SEMANTIC_AUTHORED_EVENT_INVALID')
            refs = event.get('target_geometry_refs',[])
            point = geometry_by_id.get(event.get('location_point_ref'))
            if (not isinstance(refs,list) or any(ref not in geometry_by_id or geometry_by_id[ref]['geometry_type']=='Point' for ref in refs)
                    or point is None or point['geometry_type']!='Point' or point.get('location_id') not in definition['target_ids']):
                raise ValueError('SEMANTIC_AUTHORED_TARGET_INVALID')
            location = resolve_location(point['location_id'])
            if not verified_coordinate(location['coordinates']) or location['coordinates']['source_id'] not in source_ids:
                raise ValueError('SEMANTIC_AUTHORED_GIS_INVALID')
            # Facts use explicit source-backed geography; hypothetical states
            # require the provided claim/watermark, checked again by v022.
            if any(s not in source_ids for s in claim_by_id[event['claim_id']].get('source_ids',[])):
                raise ValueError('SEMANTIC_AUTHORED_SOURCE_INVALID')
            used.append(eid)
    if len(used)!=len(set(used)) or set(used)!=set(event_by_id):
        raise ValueError('SEMANTIC_UNUSED_OR_DUPLICATE_EVENT')
    options = dict(tts=True,subtitles=True,bgm=True,sfx=True,quality='HIGH',pace='NORMAL')
    supplied_options=script_record.get('options',{})
    if not isinstance(supplied_options,dict) or set(supplied_options)-set(options):
        raise ValueError('SEMANTIC_PRODUCTION_OPTIONS_INVALID')
    options.update(deepcopy(supplied_options))
    if options['tts'] is not True or any(type(options[k])is not bool for k in ('subtitles','bgm','sfx')):
        raise ValueError('SEMANTIC_PRODUCTION_REQUIRES_REAL_TTS')
    timeline = build_semantic_timeline(script_record,directory,provider,fps=fps,
        camera_arrival_seconds=script_record.get('camera_arrival_seconds',.4),
        after_state_hold_seconds=script_record.get('after_state_hold_seconds',.8),
        language=script_record.get('language'),speed=script_record.get('speed',155))
    if not timeline['passed']:
        return dict(schema_version='1.0',ready=False,scenes=[],
            metadata=dict(semantic_timeline=timeline,semantic_timeline_directory=str(Path(directory).resolve())),
            gate=dict(passed=False,errors=deepcopy(timeline['errors']),warnings=deepcopy(timeline['warnings'])))
    clock=FrameGrid(fps)
    scenes, events, previous = [], [], None
    allowed_kinds={'city_reveal','country_reveal','region_reveal','destination_preview','new_variable','response','consequence_reveal','final_reveal','route_blocked'}
    for index,(definition,segment) in enumerate(zip(definitions,timeline['segments'])):
        own=[event_by_id[eid]for eid in definition['event_ids']]
        point=geometry_by_id[own[0]['location_point_ref']]
        location=resolve_location(point['location_id'])
        if any(geometry_by_id[e['location_point_ref']]['location_id']!=location['id']for e in own):
            raise ValueError('SEMANTIC_SCENE_MULTIPLE_LOCATION_TARGETS')
        window=segment['visual_window'];start,end=window['start_frame'],window['end_frame']
        duration=clock.seconds(end-start);arrival=clock.seconds(window['camera_arrival_frame']-start)
        pose=camera_state(location,'GEOGRAPHY_APPROACH')
        framing=None
        geometry_refs=sorted({ref for e in own for ref in e.get('target_geometry_refs',[])})
        geometry_records=[geometry_by_id[ref]for ref in geometry_refs]
        if script_record.get('framing_profile') is not None:
            framing=fit_native_geometry(geometry_records,registry=registry,profile=script_record['framing_profile'])
            pose={k:deepcopy(framing['camera'][k])for k in ('lon','lat','height','fov','tilt','yaw','bank','target_lon','target_lat')}
            pose['location_id']=location['id']
        begin=deepcopy(previous['camera'] if previous else pose)
        entry=deepcopy(previous) if previous else dict(camera=deepcopy(begin),earth_rotation=0.,
            active_countries=[],active_routes=[],entities=[],lighting='GEOGRAPHY_READABILITY',timeline={})
        exit_state={**deepcopy(entry),'camera':deepcopy(pose)}
        sid=f'S{index+1:03}'
        visual_events=[]
        for event in own:
            sentence_index=event.get('sentence_index',0)
            if type(sentence_index)is not int or not 0<=sentence_index<len(segment['sentence_windows']):
                raise ValueError('SEMANTIC_EVENT_SENTENCE_INDEX_INVALID')
            onset=clock.frames(segment['sentence_windows'][sentence_index]['speech_start'])-start
            finish=end-start
            kind=event.get('visual_kind','region_reveal')
            if kind not in allowed_kinds:
                raise ValueError('SEMANTIC_PHYSICAL_EVENT_REQUIRES_AUTHORED_PRIMITIVE')
            if kind=='route_blocked' and (not event['target_geometry_refs']
                    or any(geometry_by_id[g]['geometry_type']not in {'LineString','MultiLineString'}for g in event['target_geometry_refs'])
                    or event['state_after']not in {'CLOSED','BLOCKED','INACTIVE'}):
                raise ValueError('SEMANTIC_ROUTE_STATE_REQUIRES_NATIVE_LINE')
            display=event['text']['event_title'] or event['text']['location_label'] or ''
            visual_events.append(dict(id=event['id'],kind=kind,time=clock.seconds(onset),
                duration=clock.seconds(finish-onset),target_id=location['id'],role='progression',
                caused_by=None,meaningful=True,description=claim_by_id[event['claim_id']]['text'],
                coordinates=deepcopy(location['coordinates']),claim_id=event['claim_id'],text=display))
            measured_event={key:deepcopy(event[key])for key in ('id','semantic_segment_ref','claim_id',
                'target_geometry_refs','location_point_ref','state_before','state_after','primary_role','evidence_type','watermark','text')}
            measured_event.update(scene_id=sid,start_frame=onset,transition_end_frame=min(finish-1,onset+max(1,clock.frames(.4))),
                                  end_frame=finish,story_source_ref=None)
            events.append(measured_event)
        # An authored sentence is the indivisible measured timing unit. Multiple
        # states may only start on supplied sentence indices, never guessed words.
        own_events=[e for e in events if e['scene_id']==sid]
        own_events.sort(key=lambda e:e['start_frame'])
        for left,right in zip(own_events,own_events[1:]):
            left['end_frame']=right['start_frame']
            left['transition_end_frame']=min(left['transition_end_frame'],left['end_frame']-1)
        scene=dict(scene_id=sid,start_time=clock.seconds(start),duration=duration,
            scene_start_frame=start,scene_end_frame=end,frame_count=end-start,fps=str(clock.fps),
            scene_type='CITY_FOCUS',narration=segment['script_range']['text'],location=location['name'],
            coordinates=deepcopy(location['coordinates']),geographic_targets=deepcopy(definition['target_ids']),
            camera_preset='GEOGRAPHY_APPROACH',camera_start=begin,camera_end=pose,camera_speed=1.,
            camera_easing='smootherstep',lighting_preset='GEOGRAPHY_READABILITY',entities=[],entity_actions=[],
            routes=[],visual_events=visual_events,effects=[],labels=[],text_events=[],sound_events=[],
            music_energy=.42,transition_in='camera_continuity',transition_out='camera_continuity',
            source_type='VERIFIED_GIS_WITH_AUTHORED_SCRIPT',fact_status='FACT' if all(claim_by_id[c]['status']=='FACT'for c in definition['claim_ids'])else 'SIMULATION',
            render_quality=options['quality'],entry_state=entry,exit_state=exit_state,directing_presets=['CITY_REVEAL'],
            claim_ids=deepcopy(definition['claim_ids']),narration_event_ids=deepcopy(definition['event_ids']),
            year=None,date=None,era='modern',timeline_position=start/timeline['total_frames'],motion_start=0.,
            description=segment['script_range']['text'],role='progression',render_mode='MASTER_V3_EARTH',
            production_defaults=dict(version='v1',profile='MAP_INFOGRAPHIC_PRODUCTION_V022',large_titles=False),
            visual_polish=dict(version='v004'),visual_mode='3D_EARTH',text_density='MINIMAL',
            motion_timing=dict(camera_travel_duration=arrival,zoom_duration=arrival,camera_speed_reference=1.,
                               focus_transition_duration=arrival,tts_playback_rate=1),semantic_segment_ref=segment['id'],
            native_framing=framing,regional_lod=select_regional_lod(geometry_records or [point],camera=pose))
        if options['sfx']:
            from .planner import SOUND_MAP
            for event in visual_events:
                sound=SOUND_MAP.get(event['kind'])
                if sound:scene['sound_events'].append(dict(id='SFX_'+event['id'],kind=sound,time=event['time'],
                    duration=min(.7,duration-event['time']),visual_event_id=event['id'],gain_db=-10.))
        scenes.append(scene);previous=exit_state
    request=dict(topic=script_record.get('topic',text),duration=timeline['duration'],quality=options['quality'],
        direction_profile='MAP_INFOGRAPHIC_PRODUCTION_V022',**{k:options[k]for k in ('tts','subtitles','bgm','sfx','pace')})
    plan=dict(schema_version='1.0',project_id=str(script_record.get('project_id','')),version=1,
        duration=timeline['duration'],request=request,options=options,
        story=dict(hook=script_record.get('hook',''),claims=claims,
            beats=[dict(scene_id=s['scene_id'],semantic_segment_ref=s['semantic_segment_ref'],summary=s['description'])for s in scenes],
            domain=script_record.get('domain','geography'),planner=VERSION,conclusion=script_record.get('conclusion',''),
            limitations=['Sentence synthesis windows are measured PCM; word alignment and factual narration verification are not claimed.']),
        scenes=scenes,required_plugins=['GEOGRAPHY'],sources=sources,
        metadata=dict(frame_grid=dict(fps=str(clock.fps),total_frames=timeline['total_frames'],gap_frames=0,overlap_frames=0),
            semantic_timeline=timeline,semantic_timeline_directory=str(Path(directory).resolve()),
            script_record_sha256=canonical_sha(script_record),authored_script=deepcopy(script_record),
            prepared_voice=deepcopy(timeline['voice']),infographic_preset='MAP_INFOGRAPHIC_PRODUCTION_V022'))
    from .frame_grid import canonicalize_plan
    # Canonical v014 receipt, with integer boundaries already allocated from
    # measured speech. This never snaps the original PCM semantic timestamps.
    canonicalize_plan(plan,fps)
    value=prepare_infographic(plan,registry,events=events,semantic_segments=timeline['segments'],
                             parent_renderer_family='production-earth-v1',semantic_timeline=timeline)
    atomic_json(Path(directory)/'production-plan.json',value,exclusive=True)
    return value


def validate_production_plan(plan):
    """Technical admission for the explicit measured v022 Production family.

    This is not a new default for saved plans. Its narration timing is measured,
    so the legacy lexical-duration estimate and camera-only retention heuristics
    do not apply. Schema, provenance, frame continuity, camera validity and the
    existing narration bindings remain mandatory. GPU admission stays upstream.
    """
    from jsonschema import Draft202012Validator
    schema_path=Path(__file__).resolve().parents[1]/'data/infographic/v022/production_scene_plan.schema.json'
    served_schema=Path(__file__).resolve().parents[1]/'web/infographic/v022/production_scene_plan.schema.json'
    from .presets import CAMERA_PRESETS,LIGHTING_PRESETS,DIRECTING_PRESETS
    from .gis import verified_coordinate,coordinate_source_report,resolve_location
    from .narration import validate_narration_bindings
    from .infographic_contract import canonical_sha, load_registry
    errors=[]
    def reject(code, scene_id=None):
        item=dict(code=code)
        if scene_id is not None:item['scene_id']=scene_id
        if item not in errors:errors.append(item)
    try:
        if schema_path.read_bytes()!=served_schema.read_bytes():reject('SEMANTIC_PRODUCTION_SCHEMA_MIRROR_MISMATCH')
        for failure in Draft202012Validator(json.loads(schema_path.read_text())).iter_errors(plan):
            reject('SCHEMA_ERROR')
        if errors:return dict(passed=False,errors=errors,warnings=[],physical_gpu='NOT_RUN')
        metadata=plan['metadata'];timeline=metadata['semantic_timeline']
        if metadata.get('infographic_preset')!='MAP_INFOGRAPHIC_PRODUCTION_V022':
            reject('SEMANTIC_PRODUCTION_PRESET_INVALID')
        checked=validate_semantic_timeline(timeline,directory=metadata['semantic_timeline_directory'])
        errors.extend(checked['errors'])
        script=metadata['authored_script']
        _,definitions=_script(script)
        if metadata['script_record_sha256']!=canonical_sha(script):reject('SEMANTIC_AUTHORED_SCRIPT_HASH_MISMATCH')
        if plan['story']['claims']!=script['claims'] or plan['sources']!=script['sources']:
            reject('SEMANTIC_AUTHORED_CONTENT_CHANGED')
        trusted_sources=registered_production_sources()
        for source in plan['sources']:
            expected=trusted_sources.get(source['id'])
            if expected is None or canonical_sha(source)!=canonical_sha(expected):
                reject('SEMANTIC_AUTHORED_SOURCE_NOT_REGISTERED')
        if not plan['options']['tts'] or abs(plan['duration']-timeline['duration'])>1e-9:
            reject('SEMANTIC_AUDIO_PLAN_DURATION_MISMATCH')
        clock=FrameGrid(timeline['fps']);grid=metadata['frame_grid']
        if (str(FrameGrid(grid['fps']).fps)!=str(clock.fps) or grid['total_frames']!=timeline['total_frames']
                or grid['gap']!=0 or grid['overlap']!=0):reject('SEMANTIC_PRODUCTION_FRAME_GRID_INVALID')
        from .frame_grid import validate_frame_plan
        try:validate_frame_plan(plan)
        except (KeyError,ValueError,TypeError):reject('SEMANTIC_PRODUCTION_FRAME_GRID_INVALID')
        claims={c['id']:c for c in plan['story']['claims']};source_ids={s['id']for s in plan['sources']}
        for claim in claims.values():
            if claim['status']=='FACT' and not claim['source_ids']:reject('UNSOURCED_FACT')
            if any(s not in source_ids for s in claim['source_ids']):reject('UNKNOWN_CLAIM_SOURCE')
            if claim['status']=='SIMULATION' and not claim.get('assumption_ids'):reject('UNBOUND_SIMULATION')
            if any(c not in claims or claims[c]['status']!='ASSUMPTION'for c in claim.get('assumption_ids',[])):
                reject('INVALID_ASSUMPTION_REFERENCE')
        from .plugins import REGISTRY
        if any(name not in REGISTRY or not REGISTRY[name].available for name in plan['required_plugins']):
            reject('UNSUPPORTED_VISUAL_REQUIREMENT')
        segments=timeline['segments']
        if len(plan['scenes'])!=len(segments) or len(definitions)!=len(segments):reject('SEMANTIC_PRODUCTION_SCENE_COUNT_INVALID')
        cursor,previous=0,None
        native={r['id']:r for r in load_registry()['geometries']}
        authored={e['id']:e for e in script['events']}
        for scene,segment,definition in zip(plan['scenes'],segments,definitions):
            sid=scene['scene_id'];window=segment['visual_window']
            fields=('scene_start_frame','scene_end_frame','frame_count')
            if any(type(scene.get(k))is not int for k in fields):reject('SEMANTIC_PRODUCTION_FRAME_GRID_INVALID',sid)
            if (scene['scene_start_frame']!=cursor or scene['scene_end_frame']!=window['end_frame']
                    or scene['frame_count']!=window['frame_count']
                    or FrameGrid(scene['fps']).fps!=clock.fps
                    or abs(scene['start_time']-clock.seconds(cursor))>1e-9
                    or abs(scene['duration']-clock.seconds(scene['frame_count']))>1e-9):
                reject('SEMANTIC_PRODUCTION_FRAME_GRID_INVALID',sid)
            if scene['narration']!=segment['script_range']['text'] or scene['semantic_segment_ref']!=segment['id']:
                reject('SEMANTIC_AUDIO_SCENE_SCRIPT_MISMATCH',sid)
            if scene['claim_ids']!=definition['claim_ids'] or scene['narration_event_ids']!=definition['event_ids']:
                reject('SEMANTIC_PRODUCTION_REFERENCE_MISMATCH',sid)
            expected_status='FACT'if all(claims[c]['status']=='FACT'for c in definition['claim_ids'])else 'SIMULATION'
            if scene['fact_status']!=expected_status:reject('SEMANTIC_FACT_STATE_CHANGED',sid)
            if any(segment.get(key)!=definition.get(key,[])for key in ('claim_ids','source_ids','target_ids','event_ids')):
                reject('SEMANTIC_MEASURED_REFERENCE_MISMATCH',sid)
            if (scene['camera_preset']not in CAMERA_PRESETS or scene['lighting_preset']not in LIGHTING_PRESETS
                    or any(p not in DIRECTING_PRESETS for p in scene['directing_presets'])):
                reject('SEMANTIC_PRODUCTION_PRESET_INVALID',sid)
            if (scene['entry_state']['camera']!=scene['camera_start'] or scene['exit_state']['camera']!=scene['camera_end']
                    or previous is not None and scene['entry_state']!=previous):reject('SCENE_DEPENDENCY_MISMATCH',sid)
            for pose in (scene['camera_start'],scene['camera_end']):
                if any(type(v)not in (int,float)or not math.isfinite(v)for k,v in pose.items()if k!='location_id'):
                    reject('INVALID_CAMERA',sid)
            point=native[authored[definition['event_ids'][0]]['location_point_ref']]
            location=resolve_location(point['location_id'])
            from .presets import camera_state
            expected_pose=camera_state(location,'GEOGRAPHY_APPROACH')
            own_geometry_ids=sorted({g for eid in definition['event_ids']for g in authored[eid]['target_geometry_refs']})
            own_geometry=[native[g]for g in own_geometry_ids]
            from .infographic_framing import fit_native_geometry,select_regional_lod
            expected_framing=None
            if script.get('framing_profile')is not None:
                expected_framing=fit_native_geometry(own_geometry,profile=script['framing_profile'])
                expected_pose={k:deepcopy(expected_framing['camera'][k])for k in ('lon','lat','height','fov','tilt','yaw','bank','target_lon','target_lat')}
                expected_pose['location_id']=location['id']
            if (canonical_sha(scene['camera_end'])!=canonical_sha(expected_pose)
                    or previous is None and canonical_sha(scene['camera_start'])!=canonical_sha(expected_pose)
                    or canonical_sha(scene.get('native_framing'))!=canonical_sha(expected_framing)):
                reject('SEMANTIC_AUTHORED_FRAMING_CHANGED',sid)
            expected_lod=select_regional_lod(own_geometry or [point],camera=expected_pose)
            if canonical_sha(scene.get('regional_lod'))!=canonical_sha(expected_lod):
                reject('SEMANTIC_REGIONAL_LOD_SOURCE_CHANGED',sid)
            if scene['coordinates']!=location['coordinates']:
                reject('SEMANTIC_AUTHORED_GIS_INVALID',sid)
            coordinates=[scene['coordinates']]+[e['coordinates']for e in scene['visual_events']if e.get('coordinates')]
            if any(not verified_coordinate(c)or c['source_id']not in source_ids for c in coordinates):reject('UNVERIFIED_GIS_COORDINATE',sid)
            if scene['entities'] or scene['routes']:reject('SEMANTIC_UNAUTHORED_PHYSICAL_PRIMITIVE',sid)
            if scene['labels'] or scene['text_events'] or scene['effects']:
                reject('SEMANTIC_UNAUTHORED_OVERLAY',sid)
            expected_ids=set(definition['event_ids'])
            if {e['id']for e in scene['visual_events']}!=expected_ids:reject('SEMANTIC_UNAUTHORED_VISUAL_EVENT',sid)
            for event in scene['visual_events']:
                original=authored[event['id']];point=native[original['location_point_ref']]
                if event['claim_id']!=original['claim_id'] or event['target_id']!=point['location_id']:
                    reject('SEMANTIC_AUTHORED_EVENT_INVALID',sid)
                expected_text=original['text']['event_title']or original['text']['location_label']or ''
                sentence=segment['sentence_windows'][original.get('sentence_index',0)]
                expected_time=clock.seconds(clock.frames(sentence['speech_start'])-cursor)
                if (event['text']!=expected_text or event['kind']!=original.get('visual_kind','region_reveal')
                        or event.get('coordinates')!=location['coordinates'] or abs(event['time']-expected_time)>1e-9):
                    reject('SEMANTIC_EVENT_MEASURED_TIMING_INVALID',sid)
            actual=scene.get('infographic',{}).get('events',[])
            if {e['id']for e in actual}!=expected_ids:reject('SEMANTIC_INFOGRAPHIC_EVENT_MISMATCH',sid)
            for event in actual:
                original=authored[event['id']]
                for key in ('semantic_segment_ref','claim_id','target_geometry_refs','location_point_ref','state_before','state_after','primary_role','evidence_type','watermark','text'):
                    if event[key]!=original[key]:reject('SEMANTIC_AUTHORED_EVENT_CHANGED',sid)
            arrival=clock.seconds(window['camera_arrival_frame']-window['start_frame'])
            timing=scene['motion_timing']
            if (any(type(timing[k])not in (int,float)or not math.isfinite(timing[k])for k in ('camera_travel_duration','zoom_duration','focus_transition_duration','tts_playback_rate','camera_speed_reference'))
                    or timing['camera_travel_duration']!=arrival or timing['zoom_duration']!=arrival
                    or timing['focus_transition_duration']!=arrival
                    or timing['tts_playback_rate']!=1 or timing['camera_speed_reference']!=1.):
                reject('SEMANTIC_CAMERA_ARRIVAL_TIMING_INVALID',sid)
            for sound in scene['sound_events']:
                event=next((e for e in scene['visual_events']if e['id']==sound['visual_event_id']),None)
                if event is None or abs(sound['time']-event['time'])>1e-9:reject('SOUND_EVENT_DESYNC',sid)
                else:
                    from .planner import SOUND_MAP
                    if sound['kind']!=SOUND_MAP.get(event['kind']):reject('SEMANTIC_UNAUTHORED_SOUND',sid)
            cursor=scene['scene_end_frame'];previous=scene['exit_state']
        if cursor!=timeline['total_frames']:reject('SEMANTIC_PRODUCTION_FRAME_TOTAL_INVALID')
        binding=validate_narration_bindings(plan);errors.extend(binding['errors'])
    except (KeyError,TypeError,ValueError,AttributeError,OSError,RuntimeError)as error:
        reject(str(error)if isinstance(error,ValueError)and str(error).startswith('SEMANTIC_')else 'SEMANTIC_PRODUCTION_PLAN_INVALID')
    return dict(passed=not errors,errors=errors,warnings=[],timing_method=TIMING_METHOD,
                retention_policy='MEASURED_SCRIPT_EVENTS_WITH_AFTER_STATE_HOLD',word_alignment=False,physical_gpu='NOT_RUN')
