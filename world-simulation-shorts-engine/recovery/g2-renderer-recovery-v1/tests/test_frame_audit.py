import copy
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery_frame_audit_test',HERE/'tools/audit_recovery_video.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

def row(index):
    return {'frame':index,'globalFrame':index,'timeSeconds':index/30,'diagnostic':{
        'fieldId':'field'+str(index),'sourceControlFrame':index,'ownerMasks':[{'geometry':{'type':'Polygon','coordinates':[[[1,1],[2,1],[1,2],[1,1]]]}}],
        'unknownMask':{'frame':index},'contestedMask':{'frame':index},'sharedFront':{'frame':index,'geometry':{'type':'LineString','coordinates':[[1,1],[2,2]]}},
        'actualCamera':{'bounds':[93,-3,123,43]},'camera':{'admission':{'localUsed':False},'sourceFrame':index},
        'marker':{'position':[486,1043.4782608695652],'safeArea':True},'projectEventPoint':[486,1043.4782608695652],
        'annotation':{'text':'SYNTHETIC DEMO','drawn':True,'roi':[578,74,942,122]},'sourceGeometryUnchanged':True}}

class FrameAuditTests(unittest.TestCase):
    def test_same_frame_state_is_exact_and_terrain_metadata_does_not_change_the_scene(self):
        before=[row(i) for i in range(180)];after=copy.deepcopy(before)
        for item in after:item['diagnostic']['newTerrainSourceReceipt']={'style':'NEW_SOURCE_ONLY'}
        self.assertTrue(audit.compare_scene_states(before,after)['exactCameraOwnerFrontMarkerClock'])

    def test_camera_geometry_marker_and_global_clock_mutations_are_detected(self):
        before=[row(i) for i in range(180)];after=copy.deepcopy(before)
        after[5]['diagnostic']['actualCamera']['bounds'][0]+=.01
        after[6]['diagnostic']['ownerMasks'][0]['geometry']['coordinates'][0][1][0]+=.01
        after[7]['diagnostic']['marker']['position'][0]+=1
        after[8]['globalFrame']+=1
        result=audit.compare_scene_states(before,after)
        self.assertEqual(result['sameStateFrames'],176)
        self.assertEqual([v['frame'] for v in result['stateDifferences']],[5,6,7,8])

    def test_frame_gap_and_reordered_state_sequence_are_not_accepted(self):
        frames=[row(i) for i in range(180)]
        with self.assertRaisesRegex(ValueError,'CAPTURE_SEQUENCE_INCOMPLETE'):audit.compare_scene_states(frames,frames[:-1])
        reordered=copy.deepcopy(frames);reordered[50],reordered[51]=reordered[51],reordered[50]
        self.assertFalse(audit.compare_scene_states(frames,reordered)['exactCameraOwnerFrontMarkerClock'])

    def test_source_footprint_at_camera_edge_or_crossed_by_camera_is_a_failure(self):
        frames=[row(i) for i in range(180)]
        receipt={'terrainAsset':{'bounds':[92,-4,124,44],'pixelSpacing':[1/60,1/60]},'nativeWindowPolicy':{'gutterSourcePixels':8}}
        self.assertTrue(audit.coverage(receipt,frames)['allActualViewportsStrictlyInsideSource'])
        receipt['terrainAsset']['bounds'][0]=93
        self.assertFalse(audit.coverage(receipt,frames)['allActualViewportsStrictlyInsideSource'])

    def test_frozen_edge_metrics_detect_step_and_do_not_refit_a_threshold(self):
        image=np.zeros((1920,1080,3),dtype=np.uint8)
        # Actual projection of104E for[93,-3,123,43] is396px.
        image[:,396:]=100
        result=audit.edge_metrics(image,[93,-3,123,43])
        self.assertEqual(result['verticalMedianAbsRgbJump'],100)
        self.assertTrue(result['verticalAboveFrozenBaselineControlP99'])
        self.assertEqual(audit.VERTICAL_THRESHOLD,12.133750066757203)
        self.assertEqual(audit.HORIZONTAL_THRESHOLD,.75)
        uniform=audit.edge_metrics(np.full_like(image,50),[93,-3,123,43])
        self.assertFalse(uniform['verticalAboveFrozenBaselineControlP99'])

    def test_unsafe_or_missing_source_http_proof_never_becomes_pass(self):
        receipt={'terrainAsset':{'url':'/recovery-assets/a.png','sha256':'abc','bytes':123}}
        raw=b'pin';base={'sourceStyle':copy.deepcopy(receipt),'terrainStyleReceiptSHA256':audit.sha(raw),'terrainAssetHTTPRequests':[{'url':'/recovery-assets/a.png','httpStatus':200,'sha256':'abc','bytes':123}]}
        self.assertEqual(audit.source_trace(base,receipt,raw)['status'],'PASS')
        for key,value in [('httpStatus',404),('sha256','other'),('bytes',122)]:
            changed=copy.deepcopy(base);changed['terrainAssetHTTPRequests'][0][key]=value
            self.assertEqual(audit.source_trace(changed,receipt,raw)['status'],'UNVERIFIED')
        changed=copy.deepcopy(base);changed['terrainStyleReceiptSHA256']='wrong'
        self.assertEqual(audit.source_trace(changed,receipt,raw)['status'],'UNVERIFIED')

    def test_timestamp_gap_and_audio_or_wrong_output_are_rejected(self):
        probe={'streams':[{'codec_name':'h264','width':1080,'height':1920,'avg_frame_rate':'30/1','nb_frames':'180'}],
            'format':{'duration':'6.000000'},'frames':[{'best_effort_timestamp_time':f'{i/30:.6f}'} for i in range(180)]}
        self.assertEqual(len(audit.validate_video_probe(probe)),180)
        changed=copy.deepcopy(probe);changed['frames'][77]['best_effort_timestamp_time']='2.600000'
        with self.assertRaisesRegex(ValueError,'PTS_GAP'):audit.validate_video_probe(changed)
        changed=copy.deepcopy(probe);changed['streams'].append({'codec_type':'audio'})
        with self.assertRaisesRegex(ValueError,'ONE_STREAM'):audit.validate_video_probe(changed)
        changed=copy.deepcopy(probe);changed['streams'][0]['width']=720
        with self.assertRaisesRegex(ValueError,'CANONICAL_VIDEO'):audit.validate_video_probe(changed)

    def test_boolean_is_not_a_numeric_camera_value_or_an_admission_flag(self):
        self.assertTrue(audit.semantic_equal(18.0,18))
        self.assertFalse(audit.semantic_equal(False,0))
        self.assertFalse(audit.semantic_equal(float('nan'),float('nan')))
        self.assertFalse(audit.semantic_equal(18,18.000000000000004))

    def test_adapter_hash_mismatch_and_scope_escape_are_not_verified(self):
        relative=(HERE/'tools/audit_recovery_video.py').relative_to(audit.REPO).as_posix()
        digest=audit.sha((audit.REPO/relative).read_bytes())
        self.assertEqual(audit.adapter_bindings({'adapterBindings':[{'path':relative,'sha256':digest}]})['status'],'PASS')
        self.assertEqual(audit.adapter_bindings({'adapterBindings':[{'path':relative,'sha256':'changed'}]})['status'],'UNVERIFIED')
        self.assertEqual(audit.adapter_bindings({'adapterBindings':[{'path':'../private','sha256':digest}]})['status'],'UNVERIFIED')
        self.assertEqual(audit.adapter_bindings({})['status'],'UNVERIFIED')

if __name__=='__main__':unittest.main()
