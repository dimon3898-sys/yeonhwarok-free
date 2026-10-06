"""Rendered semantic receipts, rather than authored timestamps, govern sync."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from engine.rhythm_qc import analyze_frame_sound_sync


class RhythmFrameSync(unittest.TestCase):
    def sample(self):
        plan={'rhythm_policy':{'version':'v1'},'options':{'sfx':True},'scenes':[{
            'scene_id':'S1','start_time':2.5,'duration':3,'render_mode':'FLAT_MAP_PREMIUM',
            'visual_events':[{'id':'E1','time':1,'kind':'route_start','meaningful':True},
                             {'id':'OPTIONAL','time':2,'kind':'country_reveal','meaningful':True}],
            'sound_events':[{'id':'A1','time':1,'visual_event_id':'E1'}],
        }]}
        # The authored event was at 3.5s; its actual semantic receipt is at 4.0s.
        audits=[{'scene_id':'S1','t':1.5,'meaningfulEventsRendered':[{
            'event_id':'E1','kind':'route_start','rendered_primitive':'route_head',
            'actual_time':1.5,'scheduled_time':1,'visible':True,
        }]}]
        cues={'enabled':True,'sources':[{'id':'ROUTE_START_01','sample_rate':48000}],
              'events':[{'id':'A1','scene_id':'S1','visual_event_id':'E1',
                         'visual_kind':'route_start','layer':'core','primary_sync':True,
                         'pre_hit':False,'post_hit':False,'enabled':True,
                         'sfx_variant':'ROUTE_START_01','absolute_time':4,'time':1.5,
                         'onset_sample':192000,'first_10percent_peak_sample':192024,
                         'attack_10percent_peak_seconds':.0005,
                         'first_positive_visual_frame':106,'sync_error_seconds':0}]}
        return plan,audits,cues

    def move_core(self,cues,absolute):
        core=cues['events'][0]
        core.update(absolute_time=absolute,time=absolute-2.5,onset_sample=round(absolute*48000),
                    first_10percent_peak_sample=round(absolute*48000)+24)

    def test_actual_receipt_and_global_pcm_timing_override_authored_policy(self):
        plan,audits,cues=self.sample()
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertTrue(result['passed'],result['errors'])
        event=result['events'][0]
        self.assertEqual(event['authored_visual_time'],3.5)
        self.assertEqual(event['visual_onset_seconds'],4)
        self.assertEqual(event['core_insertion_seconds'],4)
        self.assertEqual(event['primitive'],'route_head')
        self.assertEqual(event['core_insertion_difference_frames'],0)
        self.assertAlmostEqual(event['attack_10percent_peak_seconds'],.0005)
        self.assertAlmostEqual(event['onset_difference_frames'],.015)
        self.assertEqual(result['metrics']['required_bound_events'],1)
        self.assertEqual(result['metrics']['meaningful_events'],2)

    def test_missing_actual_receipt_and_core_are_failures(self):
        plan,audits,cues=self.sample()
        audits[0]['meaningfulEventsRendered']=[]
        # Matching the authored event does not replace a rendered receipt.
        self.move_core(cues,3.5)
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertFalse(result['passed'])
        self.assertIn('RHYTHM_SYNC_MISSING_RENDERED_EVENT',{e['code'] for e in result['errors']})
        plan,audits,cues=self.sample();cues['events']=[]
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertFalse(result['passed'])
        self.assertIn('RHYTHM_SYNC_MISSING_CORE_CUE',{e['code'] for e in result['errors']})

    def test_one_frame_offsets_pass_and_early_or_late_cores_fail(self):
        for offset,expected in [(0,True),(-1,True),(1,True),(-2,False),(2,False)]:
            with self.subTest(offset_frames=offset):
                plan,audits,cues=self.sample();self.move_core(cues,4+offset/30)
                result=analyze_frame_sound_sync(plan,audits,cues)
                self.assertEqual(result['passed'],expected,result['errors'])
                self.assertAlmostEqual(result['events'][0]['core_insertion_difference_frames'],offset)
                if not expected:
                    self.assertIn('RHYTHM_SYNC_CORE_OUTSIDE_ONE_FRAME',{e['code'] for e in result['errors']})

    def test_pcm_attack_is_measured_separately_and_has_bounded_allowance(self):
        plan,audits,cues=self.sample()
        cues['events'][0]['first_10percent_peak_sample']+=3200
        # The supplied attack field still claims 0.5ms; measured PCM wins.
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertFalse(result['passed'])
        self.assertEqual(result['events'][0]['core_insertion_difference_frames'],0)
        self.assertGreater(result['events'][0]['pcm_onset_difference_frames'],2)
        self.assertEqual(result['events'][0]['source_attack_allowance_seconds'],.001)
        self.assertIn('RHYTHM_SYNC_PCM_OUTSIDE_ONE_FRAME',{e['code'] for e in result['errors']})
        plan,audits,cues=self.sample()
        del cues['events'][0]['first_10percent_peak_sample']
        del cues['events'][0]['attack_10percent_peak_seconds']
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertTrue(result['passed'],result['errors'])
        self.assertFalse(result['metrics']['pcm_onset_measurement_complete'])
        self.assertEqual(result['events'][0]['onset_basis'],'core_insertion')
        self.assertIn('RHYTHM_SYNC_PCM_ATTACK_UNAVAILABLE',{e['code'] for e in result['warnings']})

    def test_explicit_pre_and_post_layers_do_not_change_sync_result(self):
        plan,audits,cues=self.sample()
        for layer,offset in [('pre',-.2),('post',.3)]:
            cue=deepcopy(cues['events'][0])
            cue.update(id='A1_'+layer,layer=layer,primary_sync=False,
                       pre_hit=layer=='pre',post_hit=layer=='post',absolute_time=4+offset,
                       onset_sample=round((4+offset)*48000),
                       first_10percent_peak_sample=round((4+offset)*48000)+24)
            cues['events'].append(cue)
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(len(result['events']),1)
        self.assertEqual(result['metrics']['excluded_pre_post_layers'],2)

    def test_known_unbound_opening_is_reported_and_extra_unbound_core_fails(self):
        plan,audits,cues=self.sample()
        plan['scenes'][0]['start_time']=0
        audits[0]['t']=4;audits[0]['meaningfulEventsRendered'][0]['actual_time']=4
        plan['scenes'][0]['duration']=5
        plan['scenes'][0]['sound_events'].append({'id':'A_OPEN','time':0,'visual_event_id':None})
        opening=deepcopy(cues['events'][0])
        opening.update(id='A_OPEN',visual_event_id=None,visual_kind=None,onset_sample=0,
                       absolute_time=0,first_10percent_peak_sample=24)
        cues['events'].append(opening)
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result['unbound_opening_cues'][0]['cue_id'],'A_OPEN')
        cues['events'].append({**opening,'id':'EXTRA_UNBOUND'})
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertFalse(result['passed'])
        self.assertIn('RHYTHM_SYNC_UNBOUND_CORE',{e['code'] for e in result['errors']})
        cues['events'][-1]=deepcopy(opening)
        result=analyze_frame_sound_sync(plan,audits,cues)
        self.assertFalse(result['passed'])
        self.assertIn('RHYTHM_SYNC_EXTRA_UNBOUND_CORE',{e['code'] for e in result['errors']})

    def test_receipt_and_core_kinds_must_match_the_meaningful_event(self):
        for target in ['receipt','core']:
            with self.subTest(target=target):
                plan,audits,cues=self.sample()
                if target=='receipt':audits[0]['meaningfulEventsRendered'][0]['kind']='country_reveal'
                else:cues['events'][0]['visual_kind']='country_reveal'
                result=analyze_frame_sound_sync(plan,audits,cues)
                self.assertFalse(result['passed'])
                expected='RHYTHM_SYNC_INVALID_SEMANTIC_RECEIPT' if target=='receipt' else 'RHYTHM_SYNC_CORE_KIND_MISMATCH'
                self.assertIn(expected,{e['code'] for e in result['errors']})

    def test_raw_frames_wrappers_and_paths_have_the_same_result(self):
        plan,audits,cues=self.sample()
        expected=analyze_frame_sound_sync(plan,audits,cues)
        for wrapped in [audits[0],{'frames':audits},{'audits':audits},[{'frames':audits}]]:
            self.assertEqual(analyze_frame_sound_sync(plan,wrapped,cues),expected)
        with tempfile.TemporaryDirectory() as directory:
            audit_path=Path(directory)/'audit.json';cue_path=Path(directory)/'cues.json'
            audit_path.write_text(json.dumps(audits));cue_path.write_text(json.dumps(cues))
            self.assertEqual(analyze_frame_sound_sync(plan,audit_path,cue_path),expected)

    def test_legacy_untagged_audits_and_sfx_off_are_skipped(self):
        plan,audits,cues=self.sample();del plan['rhythm_policy']
        result=analyze_frame_sound_sync(plan,[{'scene_id':'S1','t':0}],cues)
        self.assertTrue(result['passed']);self.assertTrue(result['skipped'])
        self.assertEqual(result['skip_reason'],'LEGACY_PLAN_WITHOUT_RHYTHM_V1')
        plan,audits,cues=self.sample();plan['options']['sfx']=False
        result=analyze_frame_sound_sync(plan,[],None)
        self.assertTrue(result['passed']);self.assertTrue(result['skipped'])
        self.assertEqual(result['skip_reason'],'SFX_DISABLED')


if __name__=='__main__':unittest.main()
