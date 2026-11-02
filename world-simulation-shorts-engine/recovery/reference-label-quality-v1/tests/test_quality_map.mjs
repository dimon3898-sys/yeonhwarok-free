import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validatePresentation,presentationNativeMapOptions,presentationBoundarySegments,presentationReplacesHighlightMarker,resolvePresentationMarkerLayout} from '../../universal-presentation-v2/presentation_plan.mjs';

const scene={event_type:'WAR',timing:{fps:30,total_frames:150,event_start_frame:0},locations:[],time_steps:[{id:'A'}]},
 legacy={camera:{mode:'KEYFRAMES',keyframes:[{frame:0,center:[18,-23],zoom:.8},{frame:149,center:[18,-23],zoom:1}]}},
 original=structuredClone(legacy),tests=[];
function check(name,fn){fn();tests.push(name);}
check('Existing absent-mapStyle draw contract remains unchanged',()=>{
 assert.deepEqual(presentationNativeMapOptions(validatePresentation(legacy,{scene}),73),{mode:1,graphics:false,boundaries:false,glow:false,dem:false,primaryMaterial:0,reveal:{primary:0,marker:0,location:0,country:0,title:0,disclosure:0}});
 assert.deepEqual(legacy,original);
 assert.equal(Object.hasOwn(validatePresentation(legacy,{scene}),'mapStyle'),false);
 assert.deepEqual(presentationBoundarySegments({presentation:legacy}),[]);
});
check('Only an active matching opt-in pin replaces the native highlight target',()=>{
 const h={id:'EVENT',locationId:'CITY'},item={id:'LABEL',style:'REFERENCE_V1',pin:'HERO',eventId:'EVENT',locationId:'CITY',startFrame:10,endFrame:40},p={labels:{enabled:true,items:[item]}};
 assert.equal(presentationReplacesHighlightMarker(p,h,9),false);assert.equal(presentationReplacesHighlightMarker(p,h,10),true);assert.equal(presentationReplacesHighlightMarker(p,h,40),false);
 for(const patch of [{style:undefined},{pin:'NONE'},{eventId:undefined},{locationId:'OTHER'}])assert.equal(presentationReplacesHighlightMarker({labels:{enabled:true,items:[{...item,...patch}]}},h,20),false);
 assert.equal(presentationReplacesHighlightMarker({labels:{enabled:false,items:[item]}},h,20),false);
});
check('Native fallback uses actual drawable pins and monotonically protected markers',()=>{
 const ordinary={id:'SOURCE'},a={id:'A',locationId:'X',qualityPinCandidate:true},b={id:'B',locationId:'Y',qualityPinCandidate:true},calls=[];
 const result=resolvePresentationMarkerLayout([ordinary,a,b],rows=>{calls.push(rows.map(x=>x.id));return{drawn:rows.includes(b)?[]:[{eventId:'A',locationId:'X',pinDrawn:true}]};});
 assert.deepEqual(calls,[['SOURCE'],['SOURCE','B'],['SOURCE','B','A']]);assert.deepEqual(result.markerRows,[ordinary,b,a]);assert.deepEqual(result.layout.drawn,[]);
 const kept=resolvePresentationMarkerLayout([ordinary,a],()=>({drawn:[{eventId:'A',locationId:'X',pinDrawn:true}]}));assert.deepEqual(kept.markerRows,[ordinary]);
 assert.deepEqual(resolvePresentationMarkerLayout([ordinary],()=>{throw Error('legacy must not prepare');}),{markerRows:[ordinary],layout:null});
});
const quality=validatePresentation({...legacy,mapStyle:{preset:'COUNTRY_FOCUS_V1',revealFrames:18,countryFill:false}},{scene});
check('Authored ribbon/glow reveal reaches full visibility on the same frame clock',()=>{
 for(const f of [0,8,17,18,149]){
  const actual=presentationNativeMapOptions(quality,f);
  assert.equal(actual.reveal.primary,Math.min(1,(f+1)/18));
  assert.equal(actual.boundaries,true);assert.equal(actual.glow,true);
  assert.equal(actual.mode,1);assert.equal(actual.primaryMaterial,0);
  assert.equal(actual.graphics,false);assert.equal(actual.dem,false);
 }
});
check('Opt-in native country material does not enable fixed native labels',()=>{
 const actual=presentationNativeMapOptions({...quality,mapStyle:{...quality.mapStyle,countryFill:true}},17);
 assert.equal(actual.mode,0);assert.equal(actual.primaryMaterial,1);assert.equal(actual.graphics,false);
 assert.equal(actual.reveal.country,0);assert.equal(actual.reveal.location,0);
});
check('Unsupported/unconsumed map controls are rejected',()=>{
 for(const mapStyle of [{preset:'UNKNOWN'},{preset:'COUNTRY_FOCUS_V1',revealFrames:0},{preset:'COUNTRY_FOCUS_V1',revealFrames:151},{preset:'COUNTRY_FOCUS_V1',countryFill:1},{preset:'COUNTRY_FOCUS_V1',shader:'arbitrary'}])assert.throws(()=>validatePresentation({...legacy,mapStyle},{scene}));
});
const outer=[[0,0],[4,0],[4,4],[0,4],[0,0]],hole=[[1,1],[1,2],[2,2],[2,1],[1,1]],
 nativePlan={primary:'COUNTRY_A',secondary:[],theme:{primaryWidth:3,secondaryWidth:2,glowRadius:4},geometries:[{id:'COUNTRY_A',geometry_type:'Polygon',coordinates:[outer,hole]},{id:'UNSELECTED',geometry_type:'Polygon',coordinates:[outer]}]},
 before=structuredClone(nativePlan),first=presentationBoundarySegments({presentation:quality,nativePlan,project:p=>p.map(v=>v*10)});
check('Boundary protection retains actual country outer and hole rings only',()=>{
 const support=3+Math.SQRT2*3.230769*4+2;
 assert.equal(first.length,8);assert.deepEqual(first[0],{a:[0,0],b:[40,0],radiusPx:support});
 assert.deepEqual(first[4],{a:[10,10],b:[10,20],radiusPx:support});assert.deepEqual(nativePlan,before);
});
check('Boundary protection follows current camera projection without stale screen points',()=>{
 const moved=presentationBoundarySegments({presentation:quality,nativePlan,project:p=>[p[0]*20+50,p[1]*20-30]});
 assert.deepEqual(moved[0].a,[50,-30]);assert.deepEqual(moved[0].b,[130,-30]);assert.notDeepEqual(moved[4],first[4]);
});
check('MultiPolygon source parts and holes remain intact',()=>{
 const multi=structuredClone(nativePlan);multi.geometries[0]={id:'COUNTRY_A',geometry_type:'MultiPolygon',coordinates:[[outer,hole],[outer]]};
 assert.equal(presentationBoundarySegments({presentation:quality,nativePlan:multi,project:p=>[...p]}).length,12);
});
check('Invalid projected geometry/support is blocked before area composition',()=>{
 assert.throws(()=>presentationBoundarySegments({presentation:quality,nativePlan,project:()=>[NaN,0]}),/PROJECTION_INVALID/);
 const huge=structuredClone(nativePlan);huge.theme.glowRadius=100;
 assert.throws(()=>presentationBoundarySegments({presentation:quality,nativePlan:huge,project:p=>p}),/SUPPORT_INVALID/);
});
for(const filename of ['../../universal-presentation-v2/presentation_runtime.mjs','../../codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs']){
 const source=await readFile(new URL(filename,import.meta.url),'utf8');
 check(`${filename}: both consumers connect validated map and protection in the existing draw path`,()=>{
  assert.match(source,/mapOptions=presentationNativeMapOptions\(p,frame\),native=factory\.renderFrame\(mapOptions\),boundarySegments=presentationBoundarySegments\(\{presentation:p,nativePlan,project\}\)/);
  assert.match(source,/protectedGraphics:markerRows,primaryMaterialColor:nativePlan\.theme\.primary,boundarySegments\}/);
  assert.match(source,/UP2_AREA_SOURCE_FOOTPRINT_OUTSIDE_SAFE/);
  assert.match(source,/UP2_CURRENT_SOURCE_COVERAGE_FAILED/);
 });
}
console.log(JSON.stringify({scope:'NEW_OPT_IN_COUNTRY_MAP_CONNECTION_ONLY',status:'PASS',tests,oldPASSSuitesRerun:0,gpuExecuted:false,visualQualityApproved:false},null,2));
