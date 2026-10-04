"""Retimed route numbers must match the unchanged renderer's edited Scene clock."""
from copy import deepcopy
import json,subprocess,unittest
from pathlib import Path
from engine.planner import generate_plan,refresh_clock_dependent_route_information,_certify_planned_events
from engine.advanced_revisions import apply_advanced_edit

APP=Path(__file__).resolve().parents[1]

def rendered_metric(scene,event):
    script=r'''
import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';
const app=process.cwd(),THREE=await import(pathToFileURL(path.resolve(app,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const geo=(lon,lat,r=1)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180)).multiplyScalar(r),clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v)),smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
const source=fs.readFileSync(path.join(app,'web/earth_adapter.js'),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,''),{SceneRoutes}=new Function('THREE','Renderer','RouteGraphics','createAircraftV3','geo','clamp','smooth',source+';return {SceneRoutes};')(THREE,class {},{},()=>{},geo,clamp,smooth);
const input=JSON.parse(fs.readFileSync(0,'utf8')),routes=new SceneRoutes(input.scene),route=routes.byId(input.event.target_id),progress=routes.progress(input.event.time,route),total=route.curve.total*6371.0088;
console.log(JSON.stringify({progress,total_km:total,remaining_km:total*(1-progress)}));
'''
    process=subprocess.run(['node','--input-type=module','-e',script],cwd=APP,input=json.dumps({'scene':scene,'event':event}),text=True,capture_output=True,timeout=12,check=True)
    return json.loads(process.stdout)

class RetimedRouteMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=generate_plan(dict(topic='뉴욕 → 런던 → 두바이 민간 항공 여행',duration=20))

    def test_information_hold_retiming_refreshes_the_actual_local_progress_number(self):
        plan=deepcopy(self.plan);scene=plan['scenes'][1];prior=next(e for e in scene['visual_events'] if e['id']=='E005')
        prior['time']=1.6
        next(sound for sound in scene['sound_events'] if sound.get('visual_event_id')==prior['id'])['time']=1.6
        original_value=prior['value'];certificate=_certify_planned_events(plan)
        self.assertTrue(certificate['passed'],certificate['failures'])
        self.assertLess(prior['time'],1.6)
        expected=rendered_metric(scene,prior)
        self.assertEqual(prior['value'],round(expected['remaining_km']))
        self.assertNotEqual(prior['value'],original_value)
        sound=next(sound for sound in scene['sound_events'] if sound.get('visual_event_id')==prior['id'])
        self.assertEqual(sound['time'],prior['time'])
        self.assertEqual(scene['camera_start'],self.plan['scenes'][1]['camera_start'])
        self.assertEqual(scene['routes'],self.plan['scenes'][1]['routes'])

    def test_shifted_peak_uses_new_scene_progress_or_completed_sourced_connection(self):
        active_scene=deepcopy(self.plan['scenes'][1]);event=deepcopy(active_scene['visual_events'][0])
        event.update(kind='peak_reveal',text='999 km TO THE NEXT CITY',time=2.1)
        refresh_clock_dependent_route_information(active_scene,event);expected=rendered_metric(active_scene,event)
        self.assertEqual(event['kind'],'peak_reveal')
        self.assertEqual(event['value'],round(expected['remaining_km']))
        delayed=apply_advanced_edit(self.plan,['S004'],'S004 결론을 나중에 공개해')['plan']
        final=delayed['scenes'][-1];moved=next(e for e in final['visual_events'] if e['id']=='E011')
        expected=rendered_metric(final,moved)
        self.assertAlmostEqual(expected['progress'],1.)
        self.assertNotIn('REMAINING',moved['text']);self.assertNotIn('TO THE NEXT CITY',moved['text'])
        self.assertEqual(moved['value'],round(expected['total_km']))
        self.assertIn('LONDON',moved['text']);self.assertIn('DUBAI',moved['text'])
        self.assertIn(' -> ',moved['text']);self.assertNotIn('→',moved['text'])
        self.assertEqual(moved['claim_id'],'M01')

    def test_metric_refresh_never_changes_physical_or_total_distance_events(self):
        scene=deepcopy(self.plan['scenes'][0])
        for event in scene['visual_events']:
            if event['kind'] not in {'route_start','entity_departure','arrival'}:continue
            before=deepcopy(event)
            self.assertIsNone(refresh_clock_dependent_route_information(scene,event))
            self.assertEqual(event,before)
        total={'id':'TOTAL','kind':'distance_reveal','time':2.,'target_id':'R_01','text':'5,570 km','value':5570,'claim_id':'FD01'}
        before=deepcopy(total);self.assertIsNone(refresh_clock_dependent_route_information(scene,total));self.assertEqual(total,before)

if __name__=='__main__':unittest.main()
