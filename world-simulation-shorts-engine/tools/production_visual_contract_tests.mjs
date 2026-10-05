/** Renderer-policy contracts only. Actual pixels/audio require native render QC. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const THREE=await import(new URL('../../cinematic-world-map/node_modules/three/build/three.module.js',import.meta.url));
const source=fs.readFileSync(path.join(root,'web/production_visual_adapter.js'),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const flatSource=fs.readFileSync(path.join(root,'web/flat_semantics.js'),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const semantics=new Function('THREE',flatSource+';return {FlatSceneCore,FlatCameraRig,FlatProjection,FlatRoute,flatClamp,flatNumber,flatSmooth,flatCameraEase,flatWindow,flatCoordinate};')(THREE);
const api=new Function('THREE','SceneFlatEntitySeparationPolishRenderer','SceneEarthPolishRenderer','flatClamp','flatNumber','flatSmooth','flatCameraEase','flatWindow','flatCoordinate',source+';return {productionLabelScene,productionCameraIntervals,productionFlatCameraValues,productionRouteEmphasis,productionUsesRouteHeadAnchor,SceneProductionFlatRenderer,SceneProductionEarthRenderer,PRODUCTION_ROUTE_POLICY};')
 (THREE,class {prepareFrame(){return {labels:this.sceneSpec.labels.map(label=>({...label,anchor:{x:label.coordinates.lon,y:label.coordinates.lat}}))};}},class {overlay(){this.labels=this.sceneSpec.labels.map(label=>({...label}));}dispatchEventAudit(){this.eventAudit=[{event_id:'E_PEAK',kind:'peak_reveal',rendered_primitive:'network',visible:true}];}},semantics.flatClamp,semantics.flatNumber,semantics.flatSmooth,semantics.flatCameraEase,semantics.flatWindow,semantics.flatCoordinate);
let assertions=0;
const scene={scene_id:'S1',duration:3,start_time:0,production_defaults:{version:'v1'},text_density:'MINIMAL',pace:'FAST',coordinates:{lon:126.99,lat:37.56},camera_preset:'FLAT_REGION_FOCUS',camera_speed:1,flat_map:{projection:'LOCAL_MERCATOR',camera_start:{lon:126,lat:36,span_degrees:25},camera_end:{lon:134,lat:35,span_degrees:20}},motion_timing:{camera_travel_duration:1.2,zoom_duration:.9},labels:[],visual_events:[],text_events:[{id:'T1',text:'706 km',event_id:'E1',coordinates:{lon:131,lat:35},start_time:.5,end_time:1.5,role:'distance'},{id:'T2',text:'THREE CITIES · ONE NETWORK',coordinates:{lon:131,lat:35},role:'title',start_time:0,end_time:3}]};
const encoded=JSON.stringify(scene),adapted=api.productionLabelScene(scene);
assert.equal(JSON.stringify(scene),encoded,'Authored immutable Scene JSON changed');assertions++;
assert.equal(adapted.labels.length,1,'Unapproved explanatory title survived');assertions++;
assert.equal(adapted.labels[0].text,'706 km');assertions++;
assert.deepEqual(adapted.labels[0].coordinates,scene.text_events[0].coordinates,'Text detached from verified geography');assertions++;
const approved=structuredClone(scene);approved.production_defaults.large_titles=true;approved.text_events[1].large_title_approved=true;
assert.equal(api.productionLabelScene(approved).labels.length,2);assertions++;
assert.equal(api.productionLabelScene({...scene,text_density:'NONE'}).labels.length,0);assertions++;
const question=structuredClone(scene);question.text_events=[{id:'T_HOOK',event_id:'E_HOOK',text:'NEXT?',role:'question',coordinates:question.coordinates,start_time:0,end_time:1.1}];
const questionLabel=api.productionLabelScene(question).labels[0];
assert.equal(questionLabel.kind,'hook_reveal','Actually drawn map question lacks a hook audit');assertions++;
assert.equal(questionLabel.size,48,'Short map question became a large explanatory title');assertions++;
assert.deepEqual(questionLabel.coordinates,question.coordinates);assertions++;
const projection=new semantics.FlatProjection(scene.coordinates),camera=new THREE.OrthographicCamera(-10,10,17.77,-17.77,.01,2000),rig=new semantics.FlatCameraRig(camera,scene,projection,[]);
const at=api.productionFlatCameraValues(rig,.6),settled=api.productionFlatCameraValues(rig,1.2),later=api.productionFlatCameraValues(rig,2.4);
assert.ok(at.center.x>rig.values(.6).center.x,'FAST authored camera interval did not accelerate travel');assertions++;
assert.equal(settled.center.x,projection.point(rig.end).x);assertions++;
assert.equal(later.center.x,settled.center.x,'Camera does not settle after authored travel');assertions++;
assert.equal(at.sourceTime,.6);assertions++;
assert.equal(at.globalTimewarp,false);assertions++;
assert.equal(settled.span,rig.end.span_degrees);assertions++;
const authored=structuredClone(scene);authored.motion_timing.camera_speed_reference=1;
authored.routes=[{route_id:'R',points:[{lon:126.99,lat:37.56},{lon:139.75,lat:35.69}],start_time:.3,end_time:2.6}];
authored.entities=[{id:'AIR',type:'aircraft',route_id:'R',start_time:.3,end_time:2.9,persistent:true}];
const revised=structuredClone(authored);revised.camera_speed=1.5;
const originalCore=new semantics.FlatSceneCore(authored,{},{width:1080,height:1920}),revisedCore=new semantics.FlatSceneCore(revised,{},{width:1080,height:1920});
const originalCamera=api.productionFlatCameraValues(originalCore.cam,.8),revisedCamera=api.productionFlatCameraValues(revisedCore.cam,.8);
assert.ok(revisedCamera.center.x>originalCamera.center.x,'Natural-language faster-camera edit was overridden by authored motion timing');assertions++;
assert.ok(Math.abs(revisedCamera.cameraTravelDuration-.8)<1e-12);assertions++;
assert.ok(Math.abs(revisedCamera.zoomDuration-.6)<1e-12);assertions++;
assert.equal(revisedCamera.sourceTime,.8);assertions++;
assert.deepEqual(originalCore.entityPose(originalCore.entities[0],.8).position.toArray(),revisedCore.entityPose(revisedCore.entities[0],.8).position.toArray(),'Camera speed changed the verified entity route pose');assertions++;
assert.equal(originalCore.routes[0].progress(.8),revisedCore.routes[0].progress(.8),'Camera speed changed route progress');assertions++;
assert.equal(api.productionCameraIntervals({...revised,motion_timing:{camera_travel_duration:1.2,zoom_duration:.9}}).travel,1.2,'Existing production JSON without the new optional reference was retimed');assertions++;
// Route context must not drag a new-variable or blocked-city status to a
// different place. Test the actual Flat/Earth adapter wrappers, not just a flag.
const locationLabels=[
 {text:'ASSUMPTION',event_id:'E008',role:'status',route_id:'R',coordinates:{lon:121.568333,lat:25.035833,source_id:'GIS_TAIPEI'}},
 {text:'ASSUMED HOLD',event_id:'E009',role:'status',route_id:'R',coordinates:{lon:139.749462,lat:35.686963,source_id:'GIS_TOKYO'}},
 {text:'706 km',event_id:'E005',role:'distance',route_id:'R',coordinates:{lon:139.749462,lat:35.686963,source_id:'GIS_TOKYO'}}];
const anchorScene={text_density:'MINIMAL',labels:locationLabels},anchorEncoded=JSON.stringify(anchorScene);
const verifiedRoute=new semantics.FlatRoute({route_id:'R',points:[{lon:126.997785,lat:37.568295},{lon:139.749462,lat:35.686963}],start_time:0,end_time:2},projection,2),head=verifiedRoute.coordinate(.4);
const flatContext={productionReady:true,sceneSpec:anchorScene,core:{sceneSpec:anchorScene,route:()=>verifiedRoute,routeProgress:()=>.4}};
const anchoredFlat=api.SceneProductionFlatRenderer.prototype.prepareFrame.call(flatContext,.8).labels;
for(let i=0;i<2;i++){assert.deepEqual(anchoredFlat[i].coordinates,locationLabels[i].coordinates,'Flat status moved to a route head instead of its explicit city');assertions++;}
assert.ok(Math.abs(anchoredFlat[2].coordinates.lon-head.lon)<1e-10&&Math.abs(anchoredFlat[2].coordinates.lat-head.lat)<1e-10,'Flat distance is not attached to the actual verified route head');assertions++;
const earthHead=new THREE.Vector3(Math.cos(head.lat*Math.PI/180)*Math.cos(head.lon*Math.PI/180),Math.sin(head.lat*Math.PI/180),-Math.cos(head.lat*Math.PI/180)*Math.sin(head.lon*Math.PI/180));
const earthContext={sceneSpec:anchorScene,routes:{byId:()=>({curve:{getPoint:()=>earthHead.clone()}}),progress:()=>.4}};
api.SceneProductionEarthRenderer.prototype.overlay.call(earthContext,.8);
for(let i=0;i<2;i++){assert.deepEqual(earthContext.labels[i].coordinates,locationLabels[i].coordinates,'Earth status moved to a route head instead of its explicit city');assertions++;}
assert.ok(Math.abs(earthContext.labels[2].coordinates.lon-head.lon)<1e-10&&Math.abs(earthContext.labels[2].coordinates.lat-head.lat)<1e-10,'Earth distance is not attached to the actual verified route head');assertions++;
assert.equal(JSON.stringify(anchorScene),anchorEncoded,'Route-label display policy mutated stored source coordinates');assertions++;
assert.ok(api.productionUsesRouteHeadAnchor({...locationLabels[0],display_anchor:'route_head'}),'Explicit future route-head opt-in was not honored');assertions++;
const next=structuredClone(scene);next.camera_preset='FLAT_NEXT_EVENT_PREVIEW';next.flat_map.next_event={event_time:1.2,lead_time:.5,coordinates:{lon:139.75,lat:35.68}};next.motion_timing.next_event_lead_time=.4;
const preview=new semantics.FlatCameraRig(camera,next,projection,[]);
assert.equal(api.productionFlatCameraValues(preview,.75).previewWeight,0);assertions++;
assert.ok(api.productionFlatCameraValues(preview,1).previewWeight>0,'Next-event preview does not precede event');assertions++;
assert.ok(api.productionRouteEmphasis({route_id:'R1'},null));assertions++;
assert.ok(!api.productionRouteEmphasis({route_id:'R1',faint:true},null));assertions++;
assert.ok(!api.productionRouteEmphasis({route_id:'R1',visibility_role:'secondary'},null));assertions++;
assert.ok(api.productionRouteEmphasis({route_id:'R1'},'R1'));assertions++;
assert.ok(!api.productionRouteEmphasis({route_id:'R2'},'R1'));assertions++;
assert.ok(api.PRODUCTION_ROUTE_POLICY.coreWidth1080>5.5);assertions++;
const earth={sceneSpec:{production_defaults:{version:'v1'}},eventVisibility:[{visible:true}],labels:[]};
api.SceneProductionEarthRenderer.prototype.drawStoryInformation.call(earth,1);
assert.deepEqual(earth.eventVisibility,[],'Inherited large Earth story banner was not disabled');assertions++;
const oldRoute=id=>({id,start:0,end:2,curve:{getPoint:()=>new THREE.Vector3(1,0,0)}});
const older=[oldRoute('A'),oldRoute('B')],peak={sceneSpec:{visual_events:[{id:'E_PEAK',kind:'peak_reveal',time:.4,target_id:'NEW'}]},duration:2,w:1080,h:1920,labels:[],routes:{routes:older,byId:id=>older.find(route=>route.id===id),progress:()=>1},graphics:{items:older.map(()=>({mesh:{visible:true}}))},project:()=>({visible:true,x:540,y:960})};
api.SceneProductionEarthRenderer.prototype.dispatchEventAudit.call(peak,.6);
assert.equal(peak.eventAudit.length,0,'An inherited already-complete network counted as a new peak');assertions++;
const fresh={...oldRoute('NEW'),start:.4,end:1.6};peak.routes.routes=[...older,fresh];peak.routes.byId=id=>peak.routes.routes.find(route=>route.id===id);peak.routes.progress=(_,route)=>route.id==='NEW'?.2:1;peak.graphics.items.push({mesh:{visible:true}});
api.SceneProductionEarthRenderer.prototype.dispatchEventAudit.call(peak,.6);
assert.equal(peak.eventAudit.length,1);assertions++;
assert.equal(peak.eventAudit[0].fresh_route_id,'NEW');assertions++;
// Approved public v004 source identities from its preserved production lock.
const approvedFrozenSources={
 "web/flat_polish_renderer.js": "329e0da4ec4d21f0f4d26e63257709718dd27c7af3c406fe062e320657da554b",
 "web/earth_polish_adapter.js": "667c8079db74356300a1f97c0fae9a0ac56553abf7e6160d9a7f090a7e953d5e",
 "web/geographic_polish_transition.js": "843feb33625242de9673ea5e9461d7876bce83cfb67cf05f8a6a281ef08efb6a",
 "web/render_flat_polish.html": "288ccb8f01293b586314173cf59a445ba71c9dc7e7a00970c754e10ae657d705",
 "web/render_earth_polish.html": "38cc0c4aee842c1ee7c354784bf82acbe77c5c776b2d84774bf67ecd39d2d105",
 "tools/render_flat_polish_scene.mjs": "0256aee4e8d7e62683e1d234861ff98f99b3824e61bb7ee28781f05a1515c301",
 "tools/render_earth_polish_scene.mjs": "6a2cb49f09c4327d810939c76dc042781af05f79f19e25cf08f28e16031e25b6",
 "web/flat_entity_separation_polish.js": "e73df2e7e9dc1038e4121272b5dbdd0dc87c0b7c3f4a74eb6751607e94a8b97e",
 "web/render_flat_separation_polish.html": "93089e0ff84663bf2c8fc14bb0690e84e96c43c848a95b1760b2c88483b273d8",
 "tools/render_flat_separation_polish_scene.mjs": "8b606e35bbf60e152732204991ed335caaa4fe075d1a1f4cab8902256b66f3ff"
};
for(const [file,expected] of Object.entries(approvedFrozenSources)){
 const digest=typeof expected==='string'?expected:expected.sha256;
 if(!digest||!file.startsWith('web/')&&!file.startsWith('tools/')||!fs.existsSync(path.join(root,file)))continue;
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex'),digest,'Frozen approved renderer changed: '+file);assertions++;
}
console.log(JSON.stringify({passed:true,assertions,scope:'Actual authored camera timing/settle, anticipation before events, minimal georeferenced labels, explicit title authorization, primary-secondary route policy; pure CPU contracts, not rendered-pixel review'},null,2));
