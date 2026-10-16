/** CPU-only public API/input regression; no mock is presented as GPU evidence. */
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {registerHooks} from 'node:module';
const namespace=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),engine=path.resolve(namespace,'../..'),
 hook=registerHooks({resolve(s,c,next){
  if(s==='/three.js')return{url:new URL('file://'+path.join(engine,'web/vendor/three/0.170.0/three.module.js')).href,shortCircuit:true};
  if(s.startsWith('/modules/'))return{url:new URL('file://'+path.join(engine,'web/map_infographic_v1',s.slice(9))).href,shortCircuit:true};
  if(s.startsWith('/production-v3/'))return{url:new URL('file://'+path.join(namespace,s.slice(15))).href,shortCircuit:true};return next(s,c);
 }});
let createProductionNativeCamera,nativeGraphicReservations,nativeBoundarySupport,compileMovingLayoutContract;
try{
 ({createProductionNativeCamera,nativeGraphicReservations,nativeBoundarySupport}=await import('../production_native_camera.mjs'));
 ({compileMovingLayoutContract}=await import('../../../web/map_infographic_v1/moving_layout_v4.mjs'));
}finally{hook.deregister();}
test('native reservations retain measured marker/glyph boxes and exact finite boundary support',()=>{
 assert.deepEqual(nativeGraphicReservations([{kind:'MARKER',role:'MARKER',box:[100,200,32,32]}]),[{kind:'MARKER',role:'MARKER',box:[98,198,134,234]}]);
 const regional={primary:'P',secondary:[],geometries:[{id:'P',geometry_type:'Polygon',coordinates:[[[0,0],[10,0],[10,10],[0,0]]]}]},
  visual={primaryWidth:2,primaryEdgeWidth:4,glowWidth:6,glowRadius:2,secondaryWidth:1,secondaryEdgeWidth:2},
  result=nativeBoundarySupport({regional,visual,project:p=>p});
 assert.equal(result.length,3);assert.ok(result.every(row=>row.sourceId==='P'&&row.role==='PRIMARY'));
 assert.equal(result[0].radiusPx,3+Math.SQRT2*3.230769*2+2);
});
test('camera extension forwards frozen original material inputs and unchanged native marker size',()=>{
 const bounds=[-10,-20,10,20],theme={primaryWidth:2,secondaryWidth:1,primaryEdgeWidth:4,secondaryEdgeWidth:2,glowWidth:6,glowRadius:2,glowGain:.1},
  polygon={id:'P',geometry_type:'Polygon',coordinates:[[[-8,-10],[8,-10],[8,10],[-8,10],[-8,-10]]]},
  plans={REGIONAL:{primary:'P',secondary:[],geometries:[polygon],theme,framing:{bounds},layout:{safe:[48,72,1032,1848],canonical:[1080,1920]},
   anchor:{coordinates:[0,0]},scale:{marker:{pixels:32}},assets:{terrain:{bounds,pixelSpacing:[.01,.01]}}},
   CONTINENT:{theme:{...theme},framing:{bounds:[-30,-60,30,60]},scale:{marker:{pixels:24}},assets:{terrain:{bounds:[-30,-60,30,60],pixelSpacing:[.1,.1]}}}},
  marker={kind:'MARKER',role:'MARKER',box:[524,944,32,32],geographicAnchor:[0,0]},
  layoutContract=compileMovingLayoutContract({regionalPlan:plans.REGIONAL,measuredLayout:[marker]}),
  material={dem:false,verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL'},
  calls=[];let actualBounds=[...bounds];
 let parentLocked=true;
 const native={cameraPlan:{totalFrames:100},layoutContract,evidence:{frozenMaterialParameters:structuredClone(material)},
  factory:{evidence:{cameraFrame:{bounds}},updateCamera:b=>{actualBounds=[...b];},setScaleVisual(){},setTerrainLod(){},
   renderFrame:p=>{calls.push(p);return{glError:0};}},
  project:p=>[(p[0]-actualBounds[0])/(actualBounds[2]-actualBounds[0])*1080,(actualBounds[3]-p[1])/(actualBounds[3]-actualBounds[1])*1920],
  drawNative:frame=>{actualBounds=[...bounds];return{frame,primaryMaterial:1,camera:{flatBounds:[...bounds]},cameraLocked:parentLocked,settle:{locked:parentLocked},
   reveal:{primary:1,marker:1},layoutItems:[marker],gpu:{}};}};
 const line={type:'LineString',coordinates:[[2,0],[6,3]]},raw={geometries:[{id:'G',geometry:line}],areas:[{id:'A',geometry_ref:'G'}],front_lines:[{id:'F',geometry_ref:'G'}],
  time_steps:[{id:'S',area_ids:['A'],front_line_ids:['F']}]},plan={totalFrames:300,legacyScenePlan:raw,productionV3:{
  eventChapters:[{chapterId:'C1',startFrame:0,endFrame:150},{chapterId:'C2',startFrame:150,endFrame:300}],
  geometrySchedule:[{chapterId:'C1',sourceStateId:'S'},{chapterId:'C2',sourceStateId:'S'}]}},
  camera=createProductionNativeCamera({native,plans,plan,request:{timing:{eventStartFrame:60},origin:[0,0]},cameraStartFrame:0,heightSource:null,contextTerrain:null,profile:{cameraApproachFrames:48}});
 for(const frame of [60,61,119,149]){const n=camera.drawNative(frame);assert.deepEqual(n.camera.flatBounds,bounds);assert.equal(n.cameraLocked,true);assert.equal(n.layoutItems[0].box[2],32);}
 const moved=camera.drawNative(180);assert.ok(calls.length>0);assert.equal(moved.layoutItems[0].box[2],32);
 for(const params of calls){for(const [key,value]of Object.entries(material))assert.deepEqual(params[key],value);assert.equal(params.graphics,false);assert.equal(params.primaryMaterial,1);}
 assert.deepEqual(native.evidence.frozenMaterialParameters,material);assert.equal(camera.evidence.originalMarkerArtAndAnchorUnchanged,true);
 assert.deepEqual(moved.gpu.actualCamera,native.factory.evidence.cameraFrame);assert.equal(moved.gpu.cameraDiagnosticOwner,'ACTUAL_EXTENSION_FACTORY_AND_LAYOUT');
 parentLocked=false;assert.throws(()=>camera.drawNative(60),/PRODUCTION_EVENT_REQUIRES_ACTUAL_PARENT_DETAIL_LOCK/);
});
