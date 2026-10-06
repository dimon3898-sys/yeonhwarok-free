/** Shared native camera/route contracts. This is not a rendered-pixel claim. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const THREE=await import(pathToFileURL(path.resolve(root,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const reviewed=name=>fs.readFileSync(path.join(root,'web',name),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const semantics=new Function('THREE',reviewed('flat_semantics.js')+';return {FlatSceneCore,flatClamp,flatNumber,flatSmooth,flatCameraEase,flatWindow,flatCoordinate};')(THREE);
const production=new Function('THREE','SceneFlatEntitySeparationPolishRenderer','SceneEarthPolishRenderer','flatClamp','flatNumber','flatSmooth','flatCameraEase','flatWindow','flatCoordinate',reviewed('production_visual_adapter.js')+';return {productionCameraIntervals,productionFlatCameraValues};')
 (THREE,class {},class {},semantics.flatClamp,semantics.flatNumber,semantics.flatSmooth,semantics.flatCameraEase,semantics.flatWindow,semantics.flatCoordinate);
const rhythm=new Function('SceneProductionFlatRenderer','productionCameraIntervals','productionFlatCameraValues',reviewed('rhythm_visual_adapter.js')+';return {compileRhythmRamp,rhythmRampPhase,installRhythmOnFlatCore,rhythmComponentAudit,rhythmFlatCameraValues};')
 (class {},production.productionCameraIntervals,production.productionFlatCameraValues);
let checks=0;
const check=(condition,message)=>{assert.ok(condition,message);checks++;};
const close=(a,b,message)=>check(Math.abs(a-b)<1e-10,message||`${a} differs from ${b}`);
const uniform=[{phase:0,speed:1},{phase:1,speed:1}];
const contrast=[{phase:0,speed:.7},{phase:.25,speed:2.2},{phase:.48,speed:.35},{phase:.70,speed:.35},{phase:1,speed:1.8}];
close(rhythm.rhythmRampPhase(1,0,2,[{phase:0,speed:1},{phase:1,speed:3}]),.34375,'Analytical smoothstep speed integral golden value');
for(const t of [-1,0,.01,.55,1.44,2,3])close(rhythm.rhythmRampPhase(t,0,2,uniform),Math.max(0,Math.min(1,t/2)));
let previous=0;
for(let i=0;i<=300;i++){const p=rhythm.rhythmRampPhase(i/150,0,2,contrast);check(p>=previous-1e-12,'Component moved backwards');previous=p;}
close(previous,1,'Component endpoint did not settle exactly');
const parityPoints=[0,.001,.11,.25,.48,.57,.7,.93,1];
const python=spawnSync(path.join(root,'.venv/bin/python'),['-c','import json,sys; from engine.rhythm import ramp_phase; data=json.load(sys.stdin); print(json.dumps([ramp_phase(p,data["knots"]) for p in data["points"]]))'],{cwd:root,input:JSON.stringify({knots:contrast,points:parityPoints}),encoding:'utf8'});
assert.equal(python.status,0,python.stderr);checks++;
JSON.parse(python.stdout).forEach((phase,index)=>close(rhythm.rhythmRampPhase(parityPoints[index],0,1,contrast),phase,'Python/native phase mismatch'));
const pause=[{phase:0,speed:1},{phase:.5,speed:0},{phase:.6,speed:0},{phase:1,speed:1}];
close(rhythm.rhythmRampPhase(1.05,0,2,pause),rhythm.rhythmRampPhase(1.15,0,2,pause),'Zero-speed interval is not an actual component pause');
for(const invalid of [[],[{phase:0,speed:0},{phase:1,speed:0}],[{phase:0,speed:-1},{phase:1,speed:1}],[{phase:0,speed:1},{phase:.4,speed:1},{phase:.4,speed:2},{phase:1,speed:1}],[{phase:.1,speed:1},{phase:1,speed:1}]]){
 assert.throws(()=>rhythm.compileRhythmRamp(invalid));checks++;
}
const scene={scene_id:'S_NATIVE',duration:2.5,start_time:0,production_defaults:{version:'v1'},pace:'FAST',text_density:'MINIMAL',
 coordinates:{lon:126.997785,lat:37.568295},camera_preset:'FLAT_NEXT_EVENT_PREVIEW',camera_speed:1,camera_easing:'smootherstep',
 camera_start:{lon:126,lat:36,span_degrees:24,tilt:.05,bank:0,rotation:0},camera_end:{lon:132,lat:35,span_degrees:21,tilt:.06,bank:.004,rotation:.012},
 motion_timing:{camera_travel_duration:2.3,zoom_duration:1.8,camera_speed_reference:1,next_event_lead_time:.35},
 flat_map:{center:{lon:129,lat:36},projection:'LOCAL_MERCATOR',tracking:.35,next_event:{event_time:1.6,lead_time:.35,strength:.4,coordinates:{lon:139.749462,lat:35.686963}}},
 routes:[{route_id:'R',points:[{lon:126.997785,lat:37.568295},{lon:139.749462,lat:35.686963}],start_time:.2,end_time:2.1,speed_easing:'linear'}],
 entities:[{id:'AIR',type:'aircraft',route_id:'R',start_time:.2,end_time:2.5,persistent:true}],entity_actions:[],
 labels:[],visual_events:[],rhythm_visual:{version:'v1',camera:{knots:contrast},zoom:{knots:contrast},routes:[{route_id:'R',knots:contrast}]}};
const encoded=JSON.stringify(scene),plan={scenes:[scene]},core=new semantics.FlatSceneCore(scene,plan,{width:1080,height:1920});
core.cam.values=t=>production.productionFlatCameraValues(core.cam,t);
const baselineRoute=core.route('R').progress(.9),baselineStart=core.cam.values(0),baselineEnd=core.cam.values(scene.duration);
const state=rhythm.installRhythmOnFlatCore(core);
check(state===rhythm.installRhythmOnFlatCore(core),'Repeated setup added a second ramp');
check(Math.abs(core.route('R').progress(.9)-baselineRoute)>.01,'Actual native route progress did not change');
for(const t of [0,.199,.2,.4,.9,1.3,1.6,2.1,2.4666667,2.5]){
 const pose=core.entityPose(scene.entities[0],t),route=core.route('R'),p=route.progress(t);
 close(pose.p,p,'Aircraft and head do not share route progress');
 close(pose.position.distanceTo(route.point(p,.16)),0,'Aircraft departed verified geographic geometry');
 close(pose.tangent.distanceTo(route.tangent(p)),0,'Aircraft rotation no longer follows route tangent');
 const camera=core.cam.values(t),baseline=production.productionFlatCameraValues(core.cam,t);
 close(camera.previewWeight,baseline.previewWeight,'Anticipation clock was warped');
 close(camera.projectionHandoff,baseline.projectionHandoff,'Handoff clock was warped');
 close(camera.sourceTime,t,'Scene clock was warped');
 const audit=rhythm.rhythmComponentAudit(core,t);check(audit.authoredComponentCount===3&&!audit.globalTimewarp,'Component audit is incomplete');
}
check(core.entityPose(scene.entities[0],2.5-1/30).visible,'Persistent aircraft disappeared before the cut');
close(core.cam.values(0).center.distanceTo(baselineStart.center),0,'Camera entry state changed');
close(core.cam.values(scene.duration).center.distanceTo(baselineEnd.center),0,'Camera exit state changed');
close(core.cam.values(scene.duration).span,baselineEnd.span,'Camera exit zoom changed');
close(core.route('R').progress(.2),0);close(core.route('R').progress(2.1),1);
const numeric=core.numericPreflight(30);check(numeric.finite&&numeric.maxCameraAngleDegreesPerFrame<=2.5,'Unchanged native numeric gate rejected ramp');
check(JSON.stringify(scene)===encoded,'Rhythm installation changed authored scene/events/assets');
const actionScene=structuredClone(scene);actionScene.entity_actions=[{entity_id:'AIR',action:'stop',time:1.6,stop_progress:.75}];
const actionCore=new semantics.FlatSceneCore(actionScene,{},{width:1080,height:1920});rhythm.installRhythmOnFlatCore(actionCore);
check(actionCore.entityPose(actionScene.entities[0],1.59).mode==='move'&&actionCore.entityPose(actionScene.entities[0],1.6).mode==='stop','Stop action time was warped');
close(actionCore.entityPose(actionScene.entities[0],1.6).p,.75);
const legacy=structuredClone(scene);delete legacy.rhythm_visual;
const legacyCore=new semantics.FlatSceneCore(legacy,{},{width:1080,height:1920}),legacyProgress=legacyCore.route('R').progress,legacyCamera=legacyCore.cam.values;
check(rhythm.installRhythmOnFlatCore(legacyCore)===null&&legacyCore.route('R').progress===legacyProgress&&legacyCore.cam.values===legacyCamera,'Unmarked legacy path changed');
for(const changed of ['missing','duplicate','held']){
 const invalid=structuredClone(scene);
 if(changed==='missing')invalid.rhythm_visual.routes[0].route_id='ABSENT';
 if(changed==='duplicate')invalid.rhythm_visual.routes.push(structuredClone(invalid.rhythm_visual.routes[0]));
 if(changed==='held')invalid.routes[0].progress_start=invalid.routes[0].progress_end=1;
 const invalidCore=new semantics.FlatSceneCore(invalid,{},{}),originalProgress=invalidCore.routes[0].progress;
 assert.throws(()=>rhythm.installRhythmOnFlatCore(invalidCore));checks++;
 check(invalidCore.routes[0].progress===originalProgress,'Invalid input partially patched the native route');
}
console.log(JSON.stringify({passed:true,checks,nativeCameraMaxAngle:numeric.maxCameraAngleDegreesPerFrame,scope:'Analytical phase, native shared camera/route/entity/event math; no WebGL pixels or audio claim'}));
