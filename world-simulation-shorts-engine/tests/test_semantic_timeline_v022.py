"""Real PCM measurement and authored-clock contracts; never speech/GPU quality."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import wavfile

from engine import semantic_timeline as semantic
from engine.audio import SR


class MeasuredPCMFixtureProvider:
    """A real WAV fixture, explicitly not a natural-speech quality provider."""
    name='MEASURED_PCM_TEST_FIXTURE'
    def __init__(self, counts=(72001,96007,43211)):
        self.counts=counts;self.calls=[]
    def synthesize(self,text,destination,language='en',speed=155):
        count=self.counts[len(self.calls)%len(self.counts)]
        self.calls.append(dict(text=text,language=language,speed=speed))
        samples=.12*np.sin(np.arange(count,dtype=np.float64)*2*np.pi*173/SR)
        wavfile.write(destination,SR,np.column_stack((samples,samples)).astype(np.float32))
        return dict(provider=self.name,duration=99999.,word_alignment=True)


def authored_production_fixture():
    from engine.gis import resolve_location,coordinate_source_report
    text='Seoul is shown. Tokyo is shown.'
    spans=[(0,15,'seoul','LOCATION_SEOUL'),(16,len(text),'tokyo','LOCATION_TOKYO')]
    sources={s['id']:s for s in coordinate_source_report()}
    claims=[];segments=[];events=[];needed=set()
    for index,(a,b,target,point)in enumerate(spans):
        location=resolve_location(target);source=location['coordinates']['source_id'];needed.add(source)
        cid=f'F{index+1}';eid=f'E{index+1}';sid=f'N{index+1}'
        claims.append(dict(id=cid,text=location['name']+' verified geographic location',status='FACT',source_ids=[source],scope='coordinate provenance'))
        segments.append(dict(id=sid,start_char=a,end_char=b,claim_ids=[cid],source_ids=[source],target_ids=[location['id']],event_ids=[eid]))
        events.append(dict(id=eid,semantic_segment_ref=sid,claim_id=cid,target_geometry_refs=[],location_point_ref=point,
            state_before='CONTEXT',state_after='LOCATION',primary_role='LOCATION_LABEL',evidence_type='sourced_fact',watermark=None,
            text=dict(event_title=None,location_label=location['name'].upper(),support_data=None),visual_kind='region_reveal'))
    return dict(text=text,segments=segments,claims=claims,sources=[sources[s]for s in sorted(needed)],events=events,
                options=dict(bgm=False,sfx=False,subtitles=True),domain='geography',topic='Verified authored location fixture')


class SemanticTimelineV022(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema,gpu_preflight
        cls.original=(schema.validate_plan,gpu_preflight.validate_plan)
        def restore():schema.validate_plan,gpu_preflight.validate_plan=cls.original
        cls.addClassCleanup(restore)
        cls.directory=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.directory.cleanup)
        cls.fixture=authored_production_fixture();cls.provider=MeasuredPCMFixtureProvider()
        cls.timeline=semantic.build_semantic_timeline(cls.fixture,cls.directory.name,cls.provider)
        if not cls.timeline['passed']:raise AssertionError(cls.timeline)

    def test_decoded_samples_override_provider_duration_and_alignment_claim(self):
        first,second=self.timeline['segments']
        self.assertEqual((first['sample_count'],second['sample_count']),(72001,96007))
        self.assertAlmostEqual(first['speech_end']-first['speech_start'],72001/SR)
        self.assertNotEqual(first['speech_end']-first['speech_start'],99999.)
        self.assertEqual(first['timing_method'],semantic.TIMING_METHOD)
        self.assertFalse(first['word_alignment']);self.assertFalse(self.timeline['word_alignment'])
        self.assertEqual(self.timeline['voice_quality'],'NOT_REVIEWED')

    def test_unequal_real_voice_lengths_allocate_unequal_visual_scenes(self):
        a,b=self.timeline['segments']
        self.assertNotEqual(a['visual_window']['frame_count'],b['visual_window']['frame_count'])
        self.assertEqual(a['visual_window']['end_frame'],b['visual_window']['start_frame'])
        self.assertEqual(self.timeline['total_frames'],sum(s['visual_window']['frame_count']for s in self.timeline['segments']))
        self.assertTrue(semantic.validate_semantic_timeline(self.timeline,directory=self.directory.name)['passed'])

    def test_semantic_ranges_claims_sources_targets_are_exact_authored_data(self):
        for actual,declared in zip(self.timeline['segments'],self.fixture['segments']):
            self.assertEqual(actual['script_range']['text'],self.fixture['text'][declared['start_char']:declared['end_char']])
            for key in ('claim_ids','source_ids','target_ids','event_ids'):self.assertEqual(actual[key],declared[key])
        self.assertEqual(self.timeline['script_sha256'],hashlib.sha256(self.fixture['text'].encode()).hexdigest())

    def test_sentences_have_separate_measured_windows_not_uniform_word_times(self):
        record=deepcopy(self.fixture);record['segments']=[dict(record['segments'][0],end_char=len(record['text']))]
        provider=MeasuredPCMFixtureProvider((12001,48017))
        with tempfile.TemporaryDirectory()as directory:
            result=semantic.build_semantic_timeline(record,directory,provider)
            self.assertTrue(result['passed'],result)
        windows=result['segments'][0]['sentence_windows']
        self.assertEqual(len(windows),2)
        self.assertEqual([w['sample_count']for w in windows],[12001,48017])
        self.assertAlmostEqual(windows[0]['speech_end'],windows[1]['speech_start'])
        self.assertFalse(result['segments'][0]['word_alignment'])
        self.assertNotIn('word_timestamps',result['segments'][0])

    def test_frame_clock_supports_rational_fps_without_voice_speed_changes(self):
        for fps in (24,25,30,60,'30000/1001'):
            with self.subTest(fps=fps),tempfile.TemporaryDirectory()as directory:
                result=semantic.build_semantic_timeline(self.fixture,directory,MeasuredPCMFixtureProvider(),fps=fps)
                self.assertTrue(result['passed'],result)
                self.assertEqual([s['sample_count']for s in result['segments']],[72001,96007])
                self.assertAlmostEqual(result['duration'],float(Fraction(result['total_frames'],1)/Fraction(str(fps))))
                cursor=0
                for segment in result['segments']:
                    window=segment['visual_window'];self.assertEqual(window['start_frame'],cursor)
                    self.assertTrue(all(type(v)is int for v in window.values()));cursor=window['end_frame']
                self.assertEqual(cursor,result['total_frames'])

    def test_arrival_precedes_measured_voice_and_after_state_hold_is_preserved(self):
        for segment in self.timeline['segments']:
            window=segment['visual_window']
            self.assertEqual(window['camera_arrival_frame']-window['start_frame'],12)
            self.assertEqual(window['end_frame']-window['speech_end_frame'],24)
            self.assertEqual(window['reveal_frame'],segment['start_frame'])
            self.assertLess(segment['speech_end'],window['end_frame']/30)

    def test_missing_provider_is_explicit_disabled_unready_not_fixed_duration(self):
        with tempfile.TemporaryDirectory()as directory,patch('engine.audio.ESpeakProvider',side_effect=RuntimeError('not installed')):
            result=semantic.build_semantic_timeline(self.fixture,directory)
        self.assertEqual(result['status'],'DISABLED_TTS_PROVIDER_UNAVAILABLE')
        self.assertFalse(result['passed']);self.assertEqual(result['segments'],[])
        self.assertIsNone(result['total_frames']);self.assertIsNone(result['voice'])

    def test_disabled_request_never_calls_synthesis_or_fabricates_segments(self):
        provider=MeasuredPCMFixtureProvider()
        with tempfile.TemporaryDirectory()as directory:result=semantic.build_semantic_timeline(self.fixture,directory,provider,enabled=False)
        self.assertFalse(result['passed']);self.assertEqual(result['status'],'DISABLED_BY_REQUEST')
        self.assertEqual(provider.calls,[]);self.assertIsNone(result['duration'])

    def test_provider_failure_records_type_without_secret_stderr(self):
        class Broken:
            name='BROKEN_FIXTURE'
            def synthesize(self,*args,**kwargs):raise RuntimeError('Authorization: Bearer sensitive-test-token')
        with tempfile.TemporaryDirectory()as directory:
            result=semantic.build_semantic_timeline(self.fixture,directory,Broken())
            encoded=Path(directory,'semantic-timeline.json').read_text()
        self.assertEqual(result['status'],'TTS_MEASUREMENT_FAILED')
        self.assertNotIn('sensitive-test-token',encoded);self.assertNotIn('Authorization',encoded)
        self.assertEqual(result['errors'][0]['exception_type'],'RuntimeError')

    def test_empty_silent_or_invalid_audio_cannot_create_measured_timeline(self):
        class Silent:
            name='SILENT_FIXTURE'
            def synthesize(self,text,destination,**kwargs):wavfile.write(destination,SR,np.zeros((100,2),np.float32))
        with tempfile.TemporaryDirectory()as directory:result=semantic.build_semantic_timeline(self.fixture,directory,Silent())
        self.assertFalse(result['passed']);self.assertEqual(result['status'],'TTS_MEASUREMENT_FAILED')

    def test_duplicate_receipt_or_existing_voice_is_not_overwritten(self):
        original=Path(self.directory.name,'semantic-timeline.json').read_bytes()
        with self.assertRaises(FileExistsError):semantic.build_semantic_timeline(self.fixture,self.directory.name,MeasuredPCMFixtureProvider())
        self.assertEqual(Path(self.directory.name,'semantic-timeline.json').read_bytes(),original)

    def test_uncovered_text_or_overlapping_script_ranges_are_rejected_before_provider(self):
        for mutation in ('gap','overlap','duplicate','boolrange','unknownrefs'):
            record=deepcopy(self.fixture)
            if mutation=='gap':record['segments'][0]['end_char']=4
            elif mutation=='overlap':record['segments'][1]['start_char']=5
            elif mutation=='duplicate':record['segments'][1]['id']=record['segments'][0]['id']
            elif mutation=='boolrange':record['segments'][0]['start_char']=False
            else:record['segments'][0]['target_ids']=[]
            provider=MeasuredPCMFixtureProvider()
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory()as directory:
                with self.assertRaises(ValueError):semantic.build_semantic_timeline(record,directory,provider)
                self.assertEqual(provider.calls,[])

    def test_language_and_speed_are_preserved_and_no_speech_acceleration(self):
        record=deepcopy(self.fixture);record['text']='서울을 보여 줍니다.';record['segments']=[dict(record['segments'][0],start_char=0,end_char=len(record['text']))]
        provider=MeasuredPCMFixtureProvider()
        with tempfile.TemporaryDirectory()as directory:result=semantic.build_semantic_timeline(record,directory,provider,speed=145)
        self.assertTrue(result['passed'],result);self.assertEqual(provider.calls[0]['language'],'ko');self.assertEqual(provider.calls[0]['speed'],145)

    def test_sample_timing_word_claim_script_and_frame_tampering_are_rejected(self):
        for mutation in ('sample','word','script','frame','nan','inf','boolframe','sentencefloat','sentencenan'):
            report=deepcopy(self.timeline)
            if mutation=='sample':report['segments'][0]['sample_count']+=100
            elif mutation=='word':report['segments'][0]['word_alignment']=True
            elif mutation=='script':report['script_text']='forged '+report['script_text']
            elif mutation=='frame':report['segments'][1]['visual_window']['start_frame']+=1
            elif mutation=='nan':report['segments'][0]['speech_end']=float('nan')
            elif mutation=='inf':report['segments'][0]['speech_start']=float('inf')
            elif mutation=='boolframe':report['segments'][0]['start_frame']=True
            elif mutation=='sentencefloat':report['segments'][0]['sentence_windows'][0]['sample_count']=float(report['segments'][0]['sample_count'])
            else:report['segments'][0]['sentence_windows'][0]['speech_end']=float('nan')
            with self.subTest(mutation=mutation):self.assertFalse(semantic.validate_semantic_timeline(report)['passed'])

    def test_wave_hash_and_relative_path_tampering_are_rejected(self):
        for name in ('../outside.wav','/etc/passwd','narration_v022.wav'):
            report=deepcopy(self.timeline);report['segments'][0]['sentence_windows'][0]['file']=name
            self.assertFalse(semantic.validate_semantic_timeline(report,directory=self.directory.name)['passed'])
        report=deepcopy(self.timeline);report['voice']['sha256']='0'*64
        self.assertFalse(semantic.validate_semantic_timeline(report,directory=self.directory.name)['passed'])

    def test_full_builder_uses_measured_windows_and_complete_canonical_frame_receipt(self):
        with tempfile.TemporaryDirectory()as directory:
            plan=semantic.generate_production_plan(self.fixture,directory,MeasuredPCMFixtureProvider())
            self.assertTrue(plan['gate']['passed'],plan['gate'])
            self.assertEqual(len(plan['scenes']),2)
            self.assertNotEqual(plan['duration'],24)
            from engine.frame_grid import validate_frame_plan
            self.assertTrue(validate_frame_plan(plan)['passed'])
            self.assertEqual(plan['metadata']['frame_grid']['version'],'INTEGER_FRAME_CLOCK_v014')
            for scene,segment in zip(plan['scenes'],plan['metadata']['semantic_timeline']['segments']):
                self.assertEqual(scene['scene_start_frame'],segment['visual_window']['start_frame'])
                self.assertEqual(scene['scene_end_frame'],segment['visual_window']['end_frame'])
                self.assertEqual(scene['narration'],segment['script_range']['text'])
                self.assertEqual(scene['infographic']['parent_renderer_family'],'production-earth-v1')
            self.assertTrue(semantic.validate_production_plan(plan)['passed'])

    def test_full_builder_rejects_invented_source_target_state_or_unbound_event(self):
        for mutation in ('source','point','unused','physical'):
            record=deepcopy(self.fixture)
            if mutation=='source':record['sources']=[]
            elif mutation=='point':record['events'][0]['location_point_ref']='COUNTRY_KOR'
            elif mutation=='unused':record['events'].append(dict(record['events'][0],id='FAKE'))
            else:record['events'][0]['visual_kind']='entity_departure'
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory()as directory:
                with self.assertRaises(ValueError):semantic.generate_production_plan(record,directory,MeasuredPCMFixtureProvider())

    def test_production_event_sfx_uses_existing_library_and_exact_reveal_clock(self):
        record=deepcopy(self.fixture);record['options']['sfx']=True
        with tempfile.TemporaryDirectory()as directory:
            plan=semantic.generate_production_plan(record,directory,MeasuredPCMFixtureProvider())
            for scene in plan['scenes']:
                self.assertEqual(len(scene['sound_events']),1)
                self.assertEqual(scene['sound_events'][0]['visual_event_id'],scene['visual_events'][0]['id'])
                self.assertEqual(scene['sound_events'][0]['time'],scene['visual_events'][0]['time'])
                self.assertEqual(scene['sound_events'][0]['kind'],'soft_impact')
            self.assertTrue(semantic.validate_production_plan(plan)['passed'])

    def test_original_mixer_and_subtitle_functions_remain_unmodified(self):
        from engine import audio,audio_stability
        original=(audio.create_audio,audio._narration,audio._run,audio.create_subtitles,audio_stability.create_audio)
        record=deepcopy(self.fixture);record['options']['subtitles']=False
        class TransientPCMFixture(MeasuredPCMFixtureProvider):
            def synthesize(self,*args,**kwargs):
                result=super().synthesize(*args,**kwargs)
                rate,pcm=wavfile.read(args[1])
                # Real PCM crest factor triggers the inherited dynamic
                # loudnorm fallback (as the actual ESpeak fixture did).
                pcm[len(pcm)//2:len(pcm)//2+96]=.95
                wavfile.write(args[1],rate,pcm)
                return result
        # Both fixtures use the real failing 253-frame clock. The zero
        # requested hold protects one frame, so a two-frame tail loss removes
        # measured speech. Historical -t behavior differs by FFmpeg version;
        # corrected output must preserve the same natural-EOF PCM on each.
        for hold,counts in ((.8,(72000,217600)),(0.,(72000,291200))):
            with self.subTest(hold=hold),tempfile.TemporaryDirectory()as directory:
                selected=deepcopy(record);selected['after_state_hold_seconds']=hold
                provider=TransientPCMFixture(counts)
                measured=Path(directory)/'measured';mixed=Path(directory)/'mixed'
                plan=semantic.generate_production_plan(selected,measured,provider)
                self.assertEqual(plan['metadata']['semantic_timeline']['total_frames'],253)
                count=len(provider.calls)
                result=semantic.prepare_production_audio(plan,plan['metadata']['semantic_timeline'],measured,mixed)
                self.assertFalse(result['audio']['semantic_timeline']['resynthesized'])
                self.assertEqual(len(provider.calls),count)
                rate,actual=wavfile.read(result['audio']['file'])
                self.assertEqual((rate,len(actual)),(SR,404800))
                self.assertEqual(result['audio']['sample_count'],len(actual))
                self.assertEqual(result['audio']['duration'],len(actual)/SR)
                first=result['audio']['normalization']['first_pass']
                filt=('loudnorm=I=-18:TP=-2.5:LRA=8:linear=true:'
                    f"measured_I={first['input_i']}:measured_TP={first['input_tp']}:"
                    f"measured_LRA={first['input_lra']}:measured_thresh={first['input_thresh']}:"
                    f"offset={first['target_offset']}")
                base=['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(mixed/'mix_raw.wav'),
                      '-af',filt,'-ar',str(SR),'-ac','2','-c:a','pcm_s24le']
                # Physical PCM from the same protected measured loudnorm with
                # natural EOF is the preservation reference, not guessed gain.
                reference=mixed/'natural-eof.wav';legacy=mixed/'legacy-time-cut.wav'
                audio._run([*base,str(reference)])
                audio._run([*base,'-t',str(plan['duration']),str(legacy)])
                _,expected=wavfile.read(reference);_,cut=wavfile.read(legacy)
                self.assertEqual(len(expected),404800)
                # Pinned Bookworm FFmpeg5.1.9 already flushes this legacy
                # command; host7.1.5 loses3200samples. Classify BEFORE from
                # physical samples, never impose one version's historical bug.
                self.assertGreater(len(cut),0)
                self.assertLessEqual(len(cut),len(expected))
                self.assertTrue(np.array_equal(actual,expected))
                self.assertTrue(np.array_equal(cut,actual[:len(cut)]))
                if hold==0:
                    speech_end=round(plan['metadata']['semantic_timeline']['segments'][-1]['speech_end']*SR)
                    tail_start=len(actual)-3200
                    self.assertGreater(speech_end,tail_start)
                    self.assertTrue(np.any(actual[tail_start:speech_end]!=0))
                    silence_padded=np.concatenate((actual[:tail_start],np.zeros_like(actual[tail_start:])))
                    self.assertFalse(np.array_equal(silence_padded,expected))
                    if len(cut)<speech_end:
                        self.assertTrue(np.any(actual[len(cut):speech_end]!=0))
                hashes={p.name:semantic._sha(p)for p in (mixed/'mix.wav',mixed/'audio_report.json',
                    mixed/'subtitle_report.json',mixed/'semantic-audio-reuse.json')}
                with patch.object(audio,'create_subtitles',side_effect=AssertionError('duplicate ASS')), \
                     patch.object(audio,'ESpeakProvider',side_effect=AssertionError('duplicate TTS')):
                    reused=semantic.prepare_production_audio(plan,plan['metadata']['semantic_timeline'],measured,mixed)
                self.assertEqual(reused,result)
                self.assertEqual(hashes,{name:semantic._sha(mixed/name)for name in hashes})
                # A corrupted physical checkpoint cannot be silently rewritten.
                data=(mixed/'mix.wav').read_bytes();(mixed/'mix.wav').write_bytes(data[:-8]+b'forged!!')
                with self.assertRaisesRegex(ValueError,'SEMANTIC_AUDIO_CHECKPOINT_INVALID'):
                    semantic.prepare_production_audio(plan,plan['metadata']['semantic_timeline'],measured,mixed)
                self.assertEqual((mixed/'mix.wav').read_bytes(),data[:-8]+b'forged!!')
        self.assertEqual((audio.create_audio,audio._narration,audio._run,audio.create_subtitles,audio_stability.create_audio),original)

    def test_production_validator_rejects_late_camera_wrong_script_and_voice_mismatch(self):
        with tempfile.TemporaryDirectory()as directory:
            plan=semantic.generate_production_plan(self.fixture,directory,MeasuredPCMFixtureProvider())
            for mutation in ('script','camera','duration','claim','state','grid','fps','source','lod','target','unboundtext','measuredrefs'):
                forged=deepcopy(plan)
                if mutation=='script':forged['scenes'][0]['narration']='invented'
                elif mutation=='camera':forged['scenes'][0]['motion_timing']['zoom_duration']=2.
                elif mutation=='duration':forged['duration']+=1
                elif mutation=='claim':forged['story']['claims'][0]['text']='invented'
                elif mutation=='state':forged['scenes'][0]['infographic']['events'][0]['state_after']='CLOSED'
                elif mutation=='grid':forged['scenes'][1]['scene_start_frame']+=1
                elif mutation=='fps':forged['scenes'][0]['fps']='60'
                elif mutation=='source':forged['sources'][0]['url']='https://invented.invalid/';forged['metadata']['authored_script']['sources']=deepcopy(forged['sources'])
                elif mutation=='lod':forged['scenes'][0]['regional_lod']['coverage_complete']=True
                elif mutation=='target':forged['scenes'][0]['camera_end']['lon']+=1
                elif mutation=='unboundtext':forged['scenes'][0]['text_events']=[{'text':'invented'}]
                else:forged['metadata']['semantic_timeline']['segments'][0]['target_ids']=['invented']
                with self.subTest(mutation=mutation):self.assertFalse(semantic.validate_production_plan(forged)['passed'])


if __name__=='__main__':unittest.main()
