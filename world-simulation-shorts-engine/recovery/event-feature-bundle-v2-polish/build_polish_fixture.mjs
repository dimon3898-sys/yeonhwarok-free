/** Data-only visual polish fixture. The accepted Flow engine and geographic data are read-only. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {assertFlowPlan,compileFlowIntent,compileFlowPlan} from '../../web/map_infographic_v1/flow_core_v2.mjs';
import {assertCameraDetailApproachPlan} from '../../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs';

const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..'),repo=path.dirname(engine);
const accepted=path.join(engine,'recovery/event-feature-bundle-v2/fixtures'),output=path.join(root,'fixtures');
const verify=process.argv.includes('--verify'),hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const clone=value=>structuredClone(value),encode=value=>Buffer.from(JSON.stringify(value,null,2)+'\n');
const relative=file=>path.relative(repo,file).split(path.sep).join('/');
const sources=new Map();
async function load(name){const file=path.join(accepted,name),bytes=await readFile(file),value=JSON.parse(bytes);
 sources.set(name,{path:relative(file),sha256:hash(bytes),bytes:bytes.length,value,raw:bytes});return value;}
async function save(name,value,{copyBytes=false}={}){
 const bytes=copyBytes?sources.get(name).raw:encode(value),file=path.join(output,name);
 if(verify){assert.deepEqual(await readFile(file),bytes,'Fixture differs from deterministic build: '+name);return bytes;}
 try{await writeFile(file,bytes,{flag:'wx'});}catch(error){if(error.code!=='EEXIST')throw error;
  assert.deepEqual(await readFile(file),bytes,'Refuse to replace a different saved fixture: '+name);}
 return bytes;
}

const real=await load('ROUTE_FLOW_REAL.json'),flow=assertFlowPlan(await load('FLOW_PLAN.json'));
assert.deepEqual(compileFlowPlan(compileFlowIntent(real.intent),real.timeline),flow);
assert.equal(flow.intent.object_graphic.width_px,52);assert.equal(flow.intent.object_graphic.height_px,30);
const detail=assertCameraDetailApproachPlan(await load('DETAIL_ADAPTER_PLAN.json'));
assert.deepEqual(flow.intent.route_geometry,detail.eventGeometry);
assert.equal(flow.totalFrames,detail.eventPlan.totalFrames);
assert.equal(flow.totalFrames,180);assert.equal(detail.totalFrames,240);assert.equal(detail.detailLockFrame,60);
assert.equal(flow.timing.hold_frames,34);

await mkdir(output,{recursive:true});
const records=[];
const record=(name,bytes,changes=[])=>{
 const source=sources.get(name);records.push({name,source:{path:source.path,sha256:source.sha256,bytes:source.bytes},
  derivative:{path:relative(path.join(output,name)),sha256:hash(bytes),bytes:bytes.length},
  byteIdentical:hash(bytes)===source.sha256,allowedChanges:changes});
};

// Object display profile is a caller input. Core dimensions remain unchanged so
// the accepted arc-length sampling and tangent heading use exactly the same values.
for(const name of ['FLOW_PLAN.json','DETAIL_ADAPTER_PLAN.json','DETAIL_REQUEST.json','NATIVE_EVENT_PLAN.json',
 'MOTION_CONTINUITY.json','synthetic-a.json','synthetic-b.json','synthetic-c.json','scene.json']){
 const value=sources.has(name)?sources.get(name).value:await load(name);
 record(name,await save(name,value,{copyBytes:true}));
}
const polishedReal=clone(real);
polishedReal.scope='FACT_BASED_FLOW_VISUAL_POLISH_CANDIDATE';
polishedReal.visual_polish={accepted_candidate_commit:'12715730f0d93cecf450bd51099be9e99fbdb71c',
 core_motion_unchanged:true,route_geometry_unchanged:true,camera_detail_unchanged:true,
 object_presentation_profile:'CALLER_SUPPLIED_ROLE_PROFILE',
 public_test_disclosure_removed:true,not_a_specific_vessel_or_real_duration_claim:true};
assert.deepEqual(polishedReal.intent,real.intent);assert.deepEqual(polishedReal.timeline,real.timeline);
record('ROUTE_FLOW_REAL.json',await save('ROUTE_FLOW_REAL.json',polishedReal),
 ['scope','visual_polish (private fixture metadata only)']);

// Existing priority-5 auxiliary-text data contract removes the disclosure without
// changing renderer, glyph, layout, reveal, or occlusion code. Higher-priority text
// is unchanged: route title and geographical location label have distinct roles.
for(const name of ['REGIONAL-plan.json','CONTINENT-plan.json']){
 const previous=await load(name),next=clone(previous);
 assert.equal(previous.text.watermark,'이동 예시');next.text.watermark='';
 const restored=clone(next);restored.text.watermark=previous.text.watermark;
 assert.deepEqual(restored,previous,'Only the auxiliary text may change');
 assert.equal(next.text.eventTitle,real.subject.title);assert.equal(next.text.locationLabel,previous.text.locationLabel);
 record(name,await save(name,next),[{field:'text.watermark',before:previous.text.watermark,after:''}]);
}

const protection={schema:1,scope:'FLOW_MOVEMENT_VISUAL_POLISH_FIXTURE_DATA',
 accepted_candidate_commit:'12715730f0d93cecf450bd51099be9e99fbdb71c',
 parent_final_baseline:clone(real.parent_baseline),
 protection:{route_geometry:'BYTE_IDENTICAL_ACCEPTED_FLOW_PLAN',arc_length_motion:'UNCHANGED_CORE_INTENT_AND_TIMING',
  heading:'UNCHANGED_CORE_DIMENSIONS_AND_ROUTE_TANGENT',camera:'BYTE_IDENTICAL_APPROVED_DETAIL_ADAPTER',
  timeline:'BYTE_IDENTICAL_180_EVENT_FRAMES_240_COMPOSITE_FRAMES',hold_frames:34,
  object_core_dimensions_px:[52,30],projection:'UNCHANGED_CORE',native_graphic_styles:'UNCHANGED_PLAN_DATA',
  glyph_layout_and_occlusion_sources:'UNCHANGED'},
 text_cleanup:{method:'Existing plan.text.watermark empty-string optional disclosure contract',
  public_removed:['이동 예시'],remaining:{title:real.subject.title,location:sources.get('REGIONAL-plan.json').value.text.locationLabel},
  no_other_text_removed:true,no_existing_graphic_repositioned:true,
  renderer_contract:'renderer.mjs truthy text.watermark controls SCENARIO_DISCLOSURE creation',
  layout_contract:'graphic_layout.mjs priority-5 disclosure is optional and does not relocate higher priorities'},
 records};
await save('FIXTURE_PROTECTION.json',protection);
console.log(JSON.stringify({status:verify?'POLISH_FIXTURES_REPRODUCIBLE':'POLISH_FIXTURES_PERSISTABLE',
 geometryUnchanged:true,cameraUnchanged:true,coreMotionUnchanged:true,coreObjectDimensions:[52,30],
 publicTextRemoved:['이동 예시'],remaining:protection.text_cleanup.remaining,
 cameraLockFrame:detail.detailLockFrame,totalFrames:detail.totalFrames,holdFrames:34,
 files:records.length+1,requiredTempOnlyFiles:0}));
