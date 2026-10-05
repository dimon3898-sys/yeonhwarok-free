"""Bounded fixes for pale place names over the actual B75 exposed surface.

The owned, immutable fixture is a byte-exact read-only copy of B75 v002. These
tests create only isolated temporary planning stores and pure renderer-geometry
certificates; no production versions, approvals, GL contexts or videos change.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from engine.planner import apply_readable_place_labels, generate_plan
from engine.revisions import _place_label_edit_requested, _status_label_edit_requested, _explicit_secondary_scene_edit, preview_revision
from engine.schema import validate_plan
from engine.storage import EngineError, ProjectStore, canonical


APP = Path(__file__).resolve().parents[1]
FIXTURE = APP / 'tests/fixtures/shipping75_v002_label_readability_original.json'
ORIGINAL_SHA = '12d997d125443af691267b88ef6743d4295438c108705f6af8bea154abaffab5'
REQUEST = 'Scene4와Scene5 지명 라벨이 밝은 지표에서 안 보여. 대비와 크기를 높여.'


class PlaceLabelReadabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_bytes = FIXTURE.read_bytes()
        if sha256(cls.original_bytes).hexdigest() != ORIGINAL_SHA:
            raise AssertionError('The exact production-plan fixture was changed')
        cls.original = json.loads(cls.original_bytes)
        cls.future_shipping = generate_plan(deepcopy(cls.original['request']))
        cls.future_day = generate_plan(dict(
            topic='런던에서 파리, 로마로 이어지는 민간 항공 여행',
            duration=20, quality='HIGH', style='차분한 여행과 탐험'))

    def preview(self, plan, request):
        with tempfile.TemporaryDirectory(prefix='wss-place-label-', dir='/tmp') as directory:
            store = ProjectStore(directory)
            base = store.create(deepcopy(plan['request']), deepcopy(plan))
            pid = base['project']['id']
            stored_path = store.version_path(pid, base['version']) / 'scene_plan.json'
            before_bytes = stored_path.read_bytes()
            result = preview_revision(store, pid, base['version'], request)
            self.assertEqual(stored_path.read_bytes(), before_bytes)
            self.assertFalse((stored_path.parent / 'approval.json').exists())
            self.assertFalse(result['approved'])
            return base['plan'], result

    def test_existing_renderer_consumes_the_three_fields_without_shader_or_font_changes(self):
        adapter = (APP / 'web/earth_adapter.js').read_bytes()
        self.assertEqual(sha256(adapter).hexdigest(),
                         'c0f6c890e67ab5be7aea56739f384db01f1df962330564947dc3a1e378c172f9')
        source = adapter.decode()
        self.assertIn('num(label.size,46)*scale', source)
        self.assertIn("label.color||'#e2e8ed'", source)
        self.assertIn('opacity*num(label.opacity,.96)', source)
        self.assertIn("c.font=`300 ${font}px 'Open Sans'`", source)
        # Only the existing fields are used: both world-space projection and its
        # safe-area/BBox clamp remain the exact frozen renderer implementation.
        self.assertIn('this.w*.13+width/2,this.w*.83-width/2', source)

    def test_future_day_labels_use_dark_ink_while_generated_night_and_hero_keep_baseline(self):
        found = set()
        for plan in (self.future_shipping, self.future_day):
            self.assertTrue(plan['gate']['passed'], plan['gate']['errors'])
            self.assertTrue(plan['gate']['semantic_visibility']['passed'])
            for scene in plan['scenes']:
                for label in scene['labels']:
                    if label.get('role') != 'city':
                        self.assertNotIn('size', label)
                        if label.get('role') == 'status' and scene['lighting_preset'] in {'GEOGRAPHY_READABILITY', 'DAY_DOCUMENTARY'}:
                            self.assertEqual(label['color'], '#102430')
                            self.assertEqual(label['opacity'], 1.0)
                            original = next(item for old in self.original['scenes'] for item in old['labels']
                                            if item.get('role') == 'status' and item['text'] == label['text'])
                            self.assertEqual({k:v for k,v in label.items() if k not in {'color','opacity'}},
                                             {k:v for k,v in original.items() if k not in {'color','opacity'}})
                        else:
                            self.assertNotIn('color', label)
                        continue
                    found.add(scene['lighting_preset'])
                    if scene['lighting_preset'] in {'GEOGRAPHY_READABILITY', 'DAY_DOCUMENTARY'}:
                        self.assertEqual(label['color'], '#102430')
                        self.assertGreaterEqual(label['size'], 52)
                        self.assertEqual(label['opacity'], 1.0)
                    else:
                        self.assertNotIn('color', label)
                        self.assertNotIn('size', label)
                        self.assertEqual(label['opacity'], .9)
        self.assertTrue({'GEOGRAPHY_READABILITY', 'DAY_DOCUMENTARY', 'CINEMATIC_NIGHT', 'HERO'} <= found)

    def test_actual_b75_two_scene_revision_changes_only_place_label_appearance(self):
        before, result = self.preview(self.original, REQUEST)
        after = result['plan']
        self.assertTrue(after['gate']['passed'], after['gate']['errors'])
        self.assertTrue(after['gate']['semantic_visibility']['passed'])
        self.assertEqual(result['affected_scenes'], ['S004', 'S005'])
        self.assertEqual({(row['scene_id'], row['field']) for row in result['diff']},
                         {('S004', 'labels'), ('S005', 'labels')})
        unchanged = 0
        for old, new in zip(before['scenes'], after['scenes']):
            if old['scene_id'] not in {'S004', 'S005'}:
                self.assertEqual(canonical(old), canonical(new))
                unchanged += 1
                continue
            self.assertEqual({key for key in old if old[key] != new[key]}, {'labels'})
            self.assertEqual(len(old['labels']), len(new['labels']))
            for old_label, new_label in zip(old['labels'], new['labels']):
                if old_label.get('role') != 'city':
                    self.assertEqual(canonical(old_label), canonical(new_label))
                    continue
                delta = {key for key in old_label.keys() | new_label.keys()
                         if old_label.get(key) != new_label.get(key)}
                self.assertEqual(delta, {'color', 'size', 'opacity'})
                self.assertEqual({key: new_label[key] for key in delta},
                                 {'color': '#102430', 'size': 52, 'opacity': 1.0})
        self.assertEqual(unchanged, 8)
        for key in before:
            if key not in {'scenes', 'gate'}:
                self.assertEqual(before[key], after[key])
        self.assertEqual(sha256(FIXTURE.read_bytes()).hexdigest(), ORIGINAL_SHA)

    def test_explicit_night_and_hero_label_edits_use_scene_lighting_without_changing_it(self):
        before, result = self.preview(self.original,
                                     'Scene8와Scene9 도시명 라벨 대비와 크기를 높여.')
        self.assertTrue(result['plan']['gate']['passed'], result['plan']['gate']['errors'])
        self.assertEqual(result['affected_scenes'], ['S008', 'S009'])
        for index in (7, 8):
            old, new = before['scenes'][index], result['plan']['scenes'][index]
            self.assertEqual({key for key in old if old[key] != new[key]}, {'labels'})
            self.assertEqual(new['labels'][0]['color'], '#e2e8ed')
            self.assertEqual(new['labels'][0]['size'], 52)
            self.assertEqual(new['labels'][0]['opacity'], 1.0)
            self.assertEqual(new['lighting_preset'], old['lighting_preset'])

    def test_country_visibility_subtitle_and_entity_sizing_are_not_place_label_edits(self):
        for text in ('일본이 안 보여', 'Scene4 자막 크기를 높여',
                     'Scene4 선박 크기를 높여', 'Scene4 항공기 크기를 높여'):
            self.assertFalse(_place_label_edit_requested(text), text)
        # Preserve the existing bounded geography-readability grammar; this
        # label patch does not add a separate general-language interpreter.
        before, result = self.preview(self.original, 'Scene8 일본이안보여')
        old, new = before['scenes'][7], result['plan']['scenes'][7]
        self.assertEqual({key for key in old if old[key] != new[key]}, {'lighting_preset', 'labels'})
        self.assertEqual(new['lighting_preset'], 'GEOGRAPHY_READABILITY')
        self.assertEqual(new['labels'][0]['color'], '#102430')
        self.assertEqual(new['labels'][0]['size'], 52)
        self.assertEqual(new['labels'][0]['opacity'], 1.0)
        self.assertEqual({key: value for key, value in new['labels'][0].items()
                          if key not in {'color', 'size', 'opacity'}},
                         {key: value for key, value in old['labels'][0].items()
                          if key not in {'color', 'size', 'opacity'}})
        for text in ('Scene4 자막 크기를 높여', 'Scene4 선박 크기를 높여'):
            with self.assertRaises(EngineError) as error:
                self.preview(self.original, text)
            self.assertEqual(error.exception.code, 'UNSUPPORTED_EDIT')

    def test_missing_or_already_correct_place_labels_are_explicit_noops(self):
        missing = deepcopy(self.original)
        missing['scenes'][3]['labels'] = []
        with self.assertRaises(EngineError) as error:
            self.preview(missing, 'Scene4 지명 라벨 대비와 크기를 높여.')
        self.assertEqual(error.exception.code, 'UNSUPPORTED_LABEL_EDIT')
        already = deepcopy(self.original)
        for scene in already['scenes'][3:5]:
            apply_readable_place_labels(scene['labels'], scene['lighting_preset'], explicit_edit=True)
        with self.assertRaises(EngineError) as error:
            self.preview(already, REQUEST)
        self.assertEqual(error.exception.code, 'NO_CHANGES')

    def test_fresh_day_to_night_revision_restyles_only_the_dependent_place_palette(self):
        target = next(scene for scene in self.future_day['scenes']
                      if scene['lighting_preset'] == 'DAY_DOCUMENTARY'
                      and scene['scene_type'] not in {'COUNTRY_FOCUS', 'COMPARISON', 'TERRITORY', 'TIMELINE'})
        request = f"Scene{int(target['scene_id'][1:])} 밤으로"
        before, result = self.preview(self.future_day, request)
        self.assertTrue(result['plan']['gate']['passed'], result['plan']['gate']['errors'])
        self.assertEqual(result['affected_scenes'], [target['scene_id']])
        for old, new in zip(before['scenes'], result['plan']['scenes']):
            if old['scene_id'] != target['scene_id']:
                self.assertEqual(canonical(old), canonical(new))
                continue
            self.assertEqual({key for key in old if old[key] != new[key]}, {'lighting_preset', 'labels'})
            self.assertEqual(new['lighting_preset'], 'CINEMATIC_NIGHT')
            for a, b in zip(old['labels'], new['labels']):
                if a.get('role') != 'city':
                    self.assertEqual(a, b)
                    continue
                self.assertEqual(a['color'], '#102430')
                self.assertEqual(b['color'], '#e2e8ed')
                self.assertEqual({key for key in a.keys() | b.keys() if a.get(key) != b.get(key)}, {'color'})

    def test_legacy_night_to_day_or_readability_updates_palette_and_preserves_status_contents(self):
        legacy = deepcopy(self.original)
        # Use a real legacy NIGHT Scene, and the same already-verified canal
        # status label as a non-city control. COMPARISON scenes stay readable.
        legacy['scenes'][7]['labels'].append(deepcopy(legacy['scenes'][4]['labels'][1]))
        for request, expected in [('Scene8 낮으로', 'DAY_DOCUMENTARY'),
                                  ('Scene8 지형을 밝게 보이게', 'GEOGRAPHY_READABILITY')]:
            with self.subTest(request=request):
                before, result = self.preview(legacy, request)
                self.assertTrue(result['plan']['gate']['passed'], result['plan']['gate']['errors'])
                self.assertEqual(result['affected_scenes'], ['S008'])
                for old, new in zip(before['scenes'], result['plan']['scenes']):
                    if old['scene_id'] != 'S008':
                        self.assertEqual(canonical(old), canonical(new))
                        continue
                    self.assertEqual({key for key in old if old[key] != new[key]}, {'lighting_preset', 'labels'})
                    self.assertEqual(new['lighting_preset'], expected)
                    status_before, status_after = old['labels'][1], new['labels'][1]
                    self.assertEqual({k:v for k,v in status_after.items() if k not in {'color','opacity'}},
                                     {k:v for k,v in status_before.items() if k not in {'color','opacity'}})
                    self.assertEqual((status_after['color'],status_after['opacity']),('#102430',1.0))
                    self.assertNotIn('size',status_after)
                    label = new['labels'][0]
                    self.assertEqual((label['color'], label['size'], label['opacity']), ('#102430', 52, 1.0))
                    for key in old['labels'][0]:
                        if key != 'opacity':
                            self.assertEqual(old['labels'][0][key], label[key])

    def test_camera_only_revision_keeps_every_place_label_even_in_a_legacy_palette(self):
        before, result = self.preview(self.original, 'Scene4 카메라를 조금 더 빠르게')
        self.assertTrue(result['plan']['gate']['passed'], result['plan']['gate']['errors'])
        self.assertEqual(result['affected_scenes'], ['S004'])
        for old, new in zip(before['scenes'], result['plan']['scenes']):
            if old['scene_id'] != 'S004':
                self.assertEqual(canonical(old), canonical(new))
                continue
            self.assertEqual({key for key in old if old[key] != new[key]}, {'camera_speed'})
            self.assertEqual(canonical(old['labels']), canonical(new['labels']))

    def test_actual_combined_city_and_canal_status_request_changes_only_eight_appearance_fields(self):
        before, result = self.preview(self.original,
                                     'Scene4와Scene5 지명과 운하 상태 라벨의 대비를 높여.')
        self.assertTrue(result['plan']['gate']['passed'],result['plan']['gate']['errors'])
        self.assertEqual(result['affected_scenes'],['S004','S005'])
        self.assertEqual({(row['scene_id'],row['field']) for row in result['diff']},
                         {('S004','labels'),('S005','labels')})
        differences=[]
        for old,new in zip(before['scenes'],result['plan']['scenes']):
            if old['scene_id'] not in {'S004','S005'}:
                self.assertEqual(canonical(old),canonical(new));continue
            self.assertEqual({k for k in old if old[k]!=new[k]},{'labels'})
            for index,(a,b) in enumerate(zip(old['labels'],new['labels'])):
                for key in a.keys()|b.keys():
                    if a.get(key)!=b.get(key):differences.append((old['scene_id'],index,key))
                if a['role']=='status':
                    self.assertEqual({k:v for k,v in a.items() if k not in {'color','opacity'}},
                                     {k:v for k,v in b.items() if k not in {'color','opacity'}})
                    self.assertNotIn('size',b)
                    self.assertEqual((b['color'],b['opacity']),('#102430',1.0))
        expected={(sid,0,key) for sid in ('S004','S005') for key in ('color','size','opacity')}
        expected|={('S005',1,'color'),('S005',1,'opacity')}
        self.assertEqual(set(differences),expected)

    def test_status_only_supported_phrases_do_not_restyle_city_labels(self):
        for request in ('Scene5 운하 상태 라벨이 안 보여. 대비를 높여.',
                        'Scene5 status label contrast'):
            with self.subTest(request=request):
                self.assertTrue(_status_label_edit_requested(request))
                self.assertFalse(_place_label_edit_requested(request))
                before,result=self.preview(self.original,request)
                self.assertTrue(result['plan']['gate']['passed'],result['plan']['gate']['errors'])
                old,new=before['scenes'][4],result['plan']['scenes'][4]
                self.assertEqual({k for k in old if old[k]!=new[k]},{'labels'})
                self.assertEqual(old['labels'][0],new['labels'][0])
                a,b=old['labels'][1],new['labels'][1]
                self.assertEqual({k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)},{'color','opacity'})
                self.assertNotIn('size',b)

    def test_missing_unverified_and_nonstatus_labels_do_not_authorize_status_edit(self):
        for kind in ('missing','unverified','nonstatus'):
            with self.subTest(kind=kind):
                candidate=deepcopy(self.original)
                if kind=='missing':candidate['scenes'][4]['labels']=candidate['scenes'][4]['labels'][:1]
                elif kind=='unverified':candidate['scenes'][4]['labels'][1]['coordinates']['lon']+=.01
                else:candidate['scenes'][4]['labels'][1]['role']='caption'
                with self.assertRaises(EngineError) as error:
                    self.preview(candidate,'Scene5 상태 라벨 대비를 높여.')
                self.assertEqual(error.exception.code,'UNSUPPORTED_LABEL_EDIT')
        for request in ('Scene5 자막 대비를 높여','Scene5 선박 크기를 높여',
                        'Scene5 상태 라벨 크기를 높여'):
            self.assertFalse(_status_label_edit_requested(request))

    def test_night_switch_syncs_status_color_but_keeps_46_pixel_font_and_safe_width(self):
        candidate=deepcopy(self.original)
        target=candidate['scenes'][7]
        target['lighting_preset']='DAY_DOCUMENTARY'
        target['labels'].append(deepcopy(candidate['scenes'][4]['labels'][1]))
        target['labels'][1]['size']=46
        apply_readable_place_labels(target['labels'],target['lighting_preset'],include_status=True)
        before,result=self.preview(candidate,'Scene8 밤으로')
        self.assertTrue(result['plan']['gate']['passed'],result['plan']['gate']['errors'])
        a,b=before['scenes'][7]['labels'][1],result['plan']['scenes'][7]['labels'][1]
        self.assertEqual({k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)},{'color'})
        self.assertEqual((b['color'],b['size'],b['opacity']),('#e2e8ed',46,1.0))
        from fontTools.ttLib import TTFont
        with TTFont(APP.parent/'cinematic-world-map/assets/v3/fonts/OpenSans-Light.ttf') as font:
            cmap=font.getBestCmap();metrics=font['hmtx'].metrics;units=font['head'].unitsPerEm
            width=lambda size:sum(metrics[cmap[ord(ch)]][0]/units*size+2.7 for ch in b['text'])-2.7
            self.assertLess(width(46),.70*1080)
            self.assertGreater(width(52),.70*1080)

    def test_explicit_mixed_label_commands_fail_before_records_or_base_changes(self):
        requests=(
            'Scene5 낮으로 바꾸고 상태 라벨 대비를 높여.',
            'Scene5 밤으로 전환하고 지명 라벨 대비를 높여.',
            'Scene5 조명을 더 밝게 해줘. 상태 라벨 대비를 높여.',
            'Scene5 카메라를 더 빠르게 하고 상태 라벨 대비를 높여.',
            'Scene5 카메라를 천천히 움직여 주고 지명 라벨 대비를 높여.',
            'Scene5 카메라 속도를 조금 더 높여. 상태 라벨 대비를 높여.',
            'Scene5 줌아웃해 주고 상태 라벨 대비를 높여.',
            'Scene5 switch to night and improve status label contrast',
            'Scene5 make the camera faster and improve place label contrast',
            'Scene5 speed up the camera and improve status label contrast',
            'Scene5 지명 라벨 대비를 높여. 카메라를 더 빠르게.',
            'Scene5 상태 라벨 대비를 높여. 카메라를 천천히',
            'Scene5 지명 라벨 대비를 높여. 밤으로.',
            'Scene5 상태 라벨 대비를 높여. 주간으로',
            'Scene5 improve place label contrast. Faster camera.',
            'Scene5 항로 두 개를 추가하고 상태 라벨 대비를 높여.',
            'Scene5 배 두 척 추가하고 상태 라벨 대비를 높여.',
            'Scene5 비행기를 빼고 지명 라벨 대비를 높여.',
            'Scene5 지명 라벨 대비를 높여. 비행기 빼.',
            'Scene5 add two ships and improve status label contrast',
            'Scene5 remove the aircraft and improve city label contrast',
        )
        with tempfile.TemporaryDirectory(prefix='wss-mixed-label-block-',dir='/tmp') as directory:
            store=ProjectStore(directory)
            base=store.create(deepcopy(self.original['request']),deepcopy(self.original))
            pid=base['project']['id'];path=store.path(pid)
            before={str(p.relative_to(path)):p.read_bytes() for p in path.rglob('*') if p.is_file()}
            for request in requests:
                with self.subTest(request=request):
                    self.assertTrue(_explicit_secondary_scene_edit(request))
                    with self.assertRaises(EngineError) as error:
                        preview_revision(store,pid,base['version'],request)
                    self.assertEqual(error.exception.code,'UNSUPPORTED_COMBINED_LABEL_EDIT')
                    self.assertIn('각각 요청',error.exception.message)
                    after={str(p.relative_to(path)):p.read_bytes() for p in path.rglob('*') if p.is_file()}
                    self.assertEqual(before,after)
                    self.assertEqual(list((path/'revisions').iterdir()),[])
                    self.assertFalse((store.version_path(pid,base['version'])/'approval.json').exists())

    def test_explanatory_brightness_night_and_camera_context_keep_exact_label_scope(self):
        requests=(
            'Scene5 상태 라벨이 밝은 지표에서 안 보여. 대비를 높여.',
            'Scene5 밤 배경에서 상태 라벨이 안 보여. 대비를 높여.',
            'Scene5 낮은 대비 때문에 상태 라벨이 안 보여. 대비를 높여.',
            'Scene5 빠른 카메라 이동 구간에서 상태 라벨이 안 보여. 대비를 높여.',
            'Scene5 카메라를 빠르게 움직이는 구간에서 상태 라벨이 안 보여. 대비를 높여.',
            'Scene5 줌아웃 중 상태 라벨이 안 보여. 대비를 높여.',
            'Scene5 밤으로 바뀌면서 상태 라벨이 안 보여. 대비를 높여.',
            'Scene5 항로 두 개 추가된 지도에서 상태 라벨이 안 보여. 대비를 높여.',
            'Scene5 improve status label contrast on the bright ground',
            'Scene5 improve status label contrast on the night backdrop',
        )
        for request in requests:
            with self.subTest(request=request):
                self.assertFalse(_explicit_secondary_scene_edit(request))
                before,result=self.preview(self.original,request)
                self.assertTrue(result['plan']['gate']['passed'],result['plan']['gate']['errors'])
                self.assertEqual(result['affected_scenes'],['S005'])
                for old,new in zip(before['scenes'],result['plan']['scenes']):
                    if old['scene_id']!='S005':self.assertEqual(canonical(old),canonical(new));continue
                    self.assertEqual({key for key in old if old[key]!=new[key]},{'labels'})
                    self.assertEqual(old['labels'][0],new['labels'][0])
                    a,b=old['labels'][1],new['labels'][1]
                    self.assertEqual({key for key in a.keys()|b.keys() if a.get(key)!=b.get(key)},{'color','opacity'})
                    self.assertNotIn('size',b)

    def test_existing_camera_and_ship_or_route_composites_are_not_label_guarded(self):
        request='32~38초 카메라를 조금 더 빠르게 하고 배 두 척 추가'
        self.assertFalse(_place_label_edit_requested(request))
        self.assertFalse(_status_label_edit_requested(request))
        before,result=self.preview(self.original,request)
        self.assertTrue(result['plan']['gate']['passed'],result['plan']['gate']['errors'])
        self.assertEqual(result['affected_scenes'],['S005','S006'])
        for index in (4,5):
            old,new=before['scenes'][index],result['plan']['scenes'][index]
            self.assertGreater(new['camera_speed'],old['camera_speed'])
            self.assertEqual(len(new['entities']),len(old['entities'])+2)
            self.assertEqual(new['labels'],old['labels'])
            self.assertEqual(new['lighting_preset'],old['lighting_preset'])
        for request in ('Scene2 항로 두 개 추가','Scene2 카메라를 더 빠르게 하고 항로 두 개 추가'):
            self.assertFalse(_place_label_edit_requested(request))
            self.assertFalse(_status_label_edit_requested(request))
        before,routes=self.preview(self.future_day,'Scene2 카메라를 더 빠르게 하고 항로 두 개 추가')
        self.assertTrue(routes['plan']['gate']['passed'],routes['plan']['gate']['errors'])
        self.assertEqual(routes['affected_scenes'],['S002'])
        self.assertEqual(len(routes['plan']['scenes'][1]['routes']),len(self.future_day['scenes'][1]['routes'])+2)
        self.assertGreater(routes['plan']['scenes'][1]['camera_speed'],before['scenes'][1]['camera_speed'])
        self.assertEqual(routes['plan']['scenes'][1]['labels'],before['scenes'][1]['labels'])

    def test_place_label_style_does_not_bypass_a_known_duplicate_event_gate(self):
        legacy = deepcopy(self.original)
        scene = legacy['scenes'][1]
        event = next(item for item in scene['visual_events'] if item['id'] == 'E008')
        place = scene['labels'][0]
        event.update(kind='region_reveal', target_id=place['coordinates']['location_id'],
                     text=place['text'], coordinates=deepcopy(place['coordinates']),
                     value=None, unit='', claim_id='F01', description='다음 지역의 위치 공개')
        next(sound for sound in scene['sound_events'] if sound['visual_event_id'] == 'E008')['kind'] = 'soft_impact'
        before, result = self.preview(legacy, REQUEST)
        self.assertFalse(result['plan']['gate']['passed'])
        self.assertEqual({(error['scene_id'], error['event_id']) for error in result['plan']['gate']['errors']
                          if error['code'] == 'PLAN_DUPLICATE_PLACE_LABEL'}, {('S002', 'E008')})
        self.assertEqual(canonical(before['scenes'][1]), canonical(result['plan']['scenes'][1]))

    def test_52_pixel_place_names_fit_the_frozen_overlay_safe_area_with_installed_font(self):
        from fontTools.ttLib import TTFont
        font_path = APP.parent / 'cinematic-world-map/assets/v3/fonts/OpenSans-Light.ttf'
        with TTFont(font_path) as font:
            cmap = font.getBestCmap()
            metrics = font['hmtx'].metrics
            units = font['head'].unitsPerEm
            samples = deepcopy(self.original['scenes'][3]['labels'])
            apply_readable_place_labels(samples, 'GEOGRAPHY_READABILITY', explicit_edit=True)
            samples += [label for plan in (self.future_shipping, self.future_day)
                        for scene in plan['scenes'] for label in scene['labels']
                        if label.get('role') == 'city' and label.get('size')]
            for label in samples:
                size = label['size']
                # Same per-glyph advance + 2.7px spacing as overlay; this is a
                # layout check, not a browser-rasterization or contrast claim.
                width = sum(metrics[cmap[ord(ch)]][0] / units * size + 2.7
                            for ch in label['text']) - 2.7
                self.assertLessEqual(width, (.83 - .13) * 1080, label['text'])
                lo, hi = .13 * 1080 + width / 2, .83 * 1080 - width / 2
                self.assertLessEqual(lo, hi)
                for projected_x in (-1080, 0, 540, 1080, 2160):
                    x = max(lo, min(hi, projected_x + 100))
                    self.assertGreaterEqual(x - width / 2, .13 * 1080 - 1e-9)
                    self.assertLessEqual(x + width / 2, .83 * 1080 + 1e-9)
                # A collision-shifted label is culled above .80H by the frozen
                # code, so any retained font-height box still fits the screen.
                self.assertLess(.80 * 1920 + .2 * size, 1920)


if __name__ == '__main__':
    unittest.main()
