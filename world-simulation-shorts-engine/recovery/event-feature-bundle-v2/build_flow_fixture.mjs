/** Data-only, deterministic Flow V2 fixture build; frozen V1 files are read-only. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {compileEventIntent} from '../../web/map_infographic_v1/event_contract_v1.mjs';
import {compileEventPlan} from '../../web/map_infographic_v1/event_timeline_v1.mjs';
import {compileCameraDetailApproach,assessCameraDetailMotion} from '../../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs';
import {compileFlowIntent,compileFlowPlan} from '../../web/map_infographic_v1/flow_core_v2.mjs';

const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..'),repo=path.dirname(engine);
const output=path.join(root,'fixtures'),verify=process.argv.includes('--verify');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const relative=file=>path.relative(repo,file).split(path.sep).join('/');
const load=async relativePath=>JSON.parse(await readFile(path.join(engine,relativePath),'utf8'));
const clone=value=>JSON.parse(JSON.stringify(value));
const record=async relativePath=>{const file=path.join(engine,relativePath),bytes=await readFile(file);
 return {path:relative(file),sha256:sha(bytes),bytes:bytes.length};};
const write=async(name,data)=>{
 const bytes=Buffer.from(JSON.stringify(data,null,2)+'\n'),file=path.join(output,name);
 if(verify){assert.deepEqual(await readFile(file),bytes,'Fixture build differs: '+name);return;}
 try{await writeFile(file,bytes,{flag:'wx'});}catch(error){if(error.code!=='EEXIST')throw error;
  assert.deepEqual(await readFile(file),bytes,'Refuse to replace different saved fixture: '+name);}
};

const data='recovery/event-data/suez-full-canal-20261012',previous='recovery/event-v1-v3-visual-detail';
const original=await load(data+'/fixture.json'),axis=await load(data+'/FULL_CANAL_MAIN_AXIS.geojson');
const provenance=await load(data+'/GEOMETRY_PROVENANCE.json'),routeFacts=await load(data+'/sources/sca/OFFICIAL_ROUTE_EXCERPTS.json');
const geometry=clone(original.intent.line.geometry);
assert.deepEqual(geometry,axis.geometry);assert.deepEqual(geometry,provenance.geometry);
assert.equal(geometry.coordinates.length,92);assert.equal(provenance.segment_count,91);
assert.equal(provenance.changed_coordinates,false);assert.equal(provenance.gap_interpolation,false);
const request=await load(previous+'/fixtures/DETAIL_REQUEST.json'),previousAdapter=await load(previous+'/fixtures/DETAIL_ADAPTER_PLAN.json');
assert.equal(request.certificate.status,'VISUAL_DETAIL_ADMITTED');
assert.deepEqual(request.targetFraming.bounds,previousAdapter.targetBounds);
const official=routeFacts.records.find(item=>item.source_key==='about');
assert.ok(official.verified_exact_visible_quotes.some(quote=>quote.includes('Port Said harbor and the Gulf of Suez')));

// Fixture vectors only. The Flow engine consumes these polygons without ship-specific simulation.
// Local +X is forward. Length 52px along motion, beam 30px: recognisable at native portrait output.
const objectGraphic={width_px:52,height_px:30,polygons:[
 {points:[[-.5,-.30],[.19,-.42],[.50,0],[.19,.42],[-.5,.30]],color:[.93,.99,1,1]},
 {points:[[-.35,-.25],[-.08,-.25],[-.08,.25],[-.35,.25]],color:[.055,.11,.15,1]},
 {points:[[-.01,-.18],[.21,-.18],[.29,0],[.21,.18],[-.01,.18]],color:[.15,.68,.70,1]},
 {points:[[-.29,-.15],[-.19,-.15],[-.19,.15],[-.29,.15]],color:[.92,.97,.99,1]}
]};
const timing={fps:30,start_frame:0,reveal_frames:32,direction_start_frame:12,object_start_frame:20,
 travel_frames:108,departure_pulse_frames:18,arrival_pulse_frames:18,hold_frames:34};
const makeIntent=(route,mode='PRODUCTION',role='ship')=>({data_mode:mode,route_geometry:clone(route),
 route_source:mode==='PRODUCTION'?clone(original.intent.line.source):{source_type:'SYNTHETIC_TEST',
  source_reference:'fixture://event-feature-bundle-v2/explicit-synthetic',verification_status:'SYNTHETIC_TEST'},
 start_anchor:clone(route.coordinates[0]),end_anchor:clone(route.coordinates.at(-1)),direction:'FORWARD',
 object_role:role,object_graphic:clone(objectGraphic)});
const eventIntent=compileEventIntent({data_mode:'PRODUCTION',line:clone(original.intent.line),metric:null});
// The old Event plan is a native geometry/Camera binding; Flow V2 owns movement beats separately.
const nativeEventPlan=compileEventPlan(eventIntent,{fps:30,seed:0,profile:{ready_frames:1,line_reveal_frames:32,
 line_hold_frames:113,metric_reveal_frames:2,information_hold_frames:34}});
assert.equal(nativeEventPlan.totalFrames,180);
const detailAdapter=compileCameraDetailApproach({currentCamera:{flatBounds:previousAdapter.startBounds},
 framingRequest:request,eventPlan:nativeEventPlan,eventGeometry:geometry,safeArea:request.safeArea});
const cameraContinuity=assessCameraDetailMotion(detailAdapter);assert.equal(cameraContinuity.status,'PASS');
assert.equal(detailAdapter.detailLockFrame,60);assert.equal(detailAdapter.totalFrames,240);

const sourcePaths=[data+'/fixture.json',data+'/FULL_CANAL_MAIN_AXIS.geojson',data+'/GEOMETRY_PROVENANCE.json',
 data+'/sources/osm/OSM_LICENSE.json',data+'/sources/osm/relation-7719838-full.osm',
 data+'/sources/sca/OFFICIAL_ROUTE_EXCERPTS.json',previous+'/fixtures/DETAIL_REQUEST.json',
 previous+'/fixtures/DETAIL_ADAPTER_PLAN.json','recovery/v4/equivalent-plans/REGIONAL-plan.json',
 'recovery/v4/equivalent-plans/CONTINENT-plan.json','recovery/v5/inputs/scene.json'];
const sources=await Promise.all(sourcePaths.map(record));
const real={schema:1,id:'SUEZ_CANAL_SOUTHBOUND_ILLUSTRATIVE_FLOW',scope:'FACT_BASED_FLOW_VISUAL_CANDIDATE',
 parent_baseline:{name:'EVENT_SYSTEM_V1_FINAL_BASELINE',commit:'f79f3d55d945ef0e53b03ac2ed666f48f28b5881',
  manifest_sha256:'52d4f5f5e034079a58a6227deff71d36bf4b775af0df600daf689eec4f7701a1'},
 subject:{title:'수에즈 운하 항로',geographic_relationship:'Port Said Mediterranean entrance → Bitter Lakes → Suez Gulf outlet',
  presentation:'Illustrative southbound transit on an existing verified navigation display axis',
  object_is_generic:true,no_actual_ship_identity:true,no_actual_departure_or_arrival_claim:true,
  travel_time_compressed_for_visual_explanation:true,no_historical_closure_claim:true,
  not_a_claim_of_one_way_navigation:true,not_a_complete_parallel_channel_network:true},
 intent:makeIntent(geometry),timeline:timing,native_event_plan:nativeEventPlan,
 detail_adapter_plan:'DETAIL_ADAPTER_PLAN.json',detail_framing_request:'DETAIL_REQUEST.json',
 detail_admission_reuse:{basis:'Approved V1 Final same geography, same full source geometry and native Terrain',
  certificate_source:sources.find(item=>item.path.endsWith('DETAIL_REQUEST.json')),
  target_unchanged:true,camera_motion_unchanged:true,new_title_layout_requires_native_protection_check:true,
  survey_admission_record_unchanged:true},
 geometry:{crs:'EPSG:4326',coordinates:92,segments:91,unchanged:true,
  source_relation:7719838,source_relation_version:17,main_axis_ways:[5038117,925360882],
  start_node:provenance.start_node,end_node:provenance.end_node,extent:provenance.extent},
 fact_evidence:{source:'Suez Canal Authority',url:official.url,original_response_sha256:official.sha256,
  retrieved_utc:official.retrieved_utc,quotes:official.verified_exact_visible_quotes,
  reuse:'Existing verified public excerpts; no new data research',fact_integrity:'Same physical waterway and endpoint relationship'},
 license:{spdx:'ODbL-1.0',name:'Open Database License 1.0',attribution:'© OpenStreetMap contributors',
  url:'https://www.openstreetmap.org/copyright',license_url:'https://opendatacommons.org/licenses/odbl/1-0/'},
 sources,metric:null,metric_reason:'Flow demonstration has no length annotation; approved V1 metric meaning/source remain unchanged'};
const flowPlan=compileFlowPlan(compileFlowIntent(real.intent),timing);
assert.equal(flowPlan.totalFrames,180);

const syntheticRoute=coordinates=>({type:'LineString',coordinates});
const camera=(bounds)=>({scale:'REGIONAL',projection:'FLAT_GEOGRAPHIC',camera:{flatBounds:bounds},
 cameraLocked:true,settle:{locked:true},admission:{status:'LOCAL_NOT_ADMITTED',effectiveScale:'REGIONAL',localUsed:false}});
const synthetic=(id,coordinates,bounds,graphics,description)=>({schema:1,id,
 scope:'EXPLICIT_SYNTHETIC_REGRESSION_NOT_FACTUAL_PRODUCTION',provenance:'SYNTHETIC_TEST',description,
 intent:makeIntent(syntheticRoute(coordinates),'SYNTHETIC_TEST','generic_transport'),timeline:clone(timing),
 context:{cameraState:camera(bounds),output:[1080,1920],safeArea:[48,72,1032,1848],protectedGraphics:graphics,
  protectedBoxes:graphics.filter(item=>item.kind!=='MARKER').map(item=>item.box)},
 expected:{route_geometry_unchanged:true,deterministic_arc_length_motion:true,
  single_departure_pulse:true,single_arrival_pulse:true,endpoint_hold:true}});
const a=synthetic('FLOW_SYNTHETIC_A_SHORT',[[4,6],[5,5.6],[6,5]],[0,0,10,10],[],
 'Short readable synthetic route: reveal, direction, object travel, one endpoint pulse and hold.');
a.expected.detail_decision='USE_CURRENT_VIEW';
const b=synthetic('FLOW_SYNTHETIC_B_LONG_CURVE',[[-8,1],[-7,2.3],[-5,3.2],[-3,2.8],[-1,1.4],[1,.9]],[-80,-60,80,60],[],
 'Long curved synthetic route is initially small: existing detail framing must preserve every source vertex.');
b.expected.detail_decision='DETAIL_APPROACH_REQUIRED';
b.expected.smooth_heading=true;b.expected.whole_route_visible=true;
const c=synthetic('FLOW_SYNTHETIC_C_PROTECTED',[[3,5],[5,5],[7,5]],[0,0,10,10],[
 {kind:'MARKER',box:[518,938,562,982]},
 {kind:'TEXT',box:[390,865,505,915]},
 {kind:'PANEL',box:[600,760,820,834]}
], 'The route crosses a protected Marker and passes below nearby Label/Title; native graphics remain unchanged.');
c.expected.marker_occlusion_allowed=true;c.expected.text_collision_allowed=false;
c.negative_cases=[{id:'TEXT_CROSSING_MUST_NOT_DRAW_OVER_TEXT',route_geometry:syntheticRoute([[3.5,5.36],[5,5.36]])},
 {id:'SAFE_AREA_OBJECT_CROP_MUST_REJECT',route_geometry:syntheticRoute([[.45,5],[2,5]])}];

for(const fixture of [a,b,c])assert.equal(compileFlowPlan(compileFlowIntent(fixture.intent),fixture.timeline).totalFrames,180);
await mkdir(output,{recursive:true});
for(const [name,value] of [['ROUTE_FLOW_REAL.json',real],['FLOW_PLAN.json',flowPlan],['synthetic-a.json',a],['synthetic-b.json',b],['synthetic-c.json',c],
 ['DETAIL_REQUEST.json',request],['DETAIL_ADAPTER_PLAN.json',detailAdapter],['NATIVE_EVENT_PLAN.json',nativeEventPlan],
 ['MOTION_CONTINUITY.json',cameraContinuity]])await write(name,value);
// New scene/plan data use the frozen Glyph and Layout systems; no original file is changed.
for(const [name,source] of [['REGIONAL-plan.json','recovery/v4/equivalent-plans/REGIONAL-plan.json'],
 ['CONTINENT-plan.json','recovery/v4/equivalent-plans/CONTINENT-plan.json']]){
 const plan=await load(source),old=clone(plan);plan.text.eventTitle=real.subject.title;plan.text.watermark='이동 예시';
 const restored=clone(plan);restored.text=old.text;assert.deepEqual(restored,old);
 await write(name,plan);
}
const scene=await load('recovery/v5/inputs/scene.json'),oldScene=clone(scene);scene.event_title=real.subject.title;
const restoredScene=clone(scene);restoredScene.event_title=oldScene.event_title;assert.deepEqual(restoredScene,oldScene);
await write('scene.json',scene);
console.log(JSON.stringify({status:verify?'FIXTURES_REPRODUCIBLE':'FIXTURES_PERSISTABLE',fixture:'fixtures/ROUTE_FLOW_REAL.json',
 routeVertices:geometry.coordinates.length,routeSegments:geometry.coordinates.length-1,geometryUnchanged:true,
 cameraContinuity:cameraContinuity.status,cameraLockFrame:detailAdapter.detailLockFrame,totalFrames:detailAdapter.totalFrames,
 durationSeconds:detailAdapter.durationSeconds,newTitle:scene.event_title,synthetic:['A','B','C']}));
