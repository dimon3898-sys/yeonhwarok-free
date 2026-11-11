import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {validateFactDataset,compileScenePlan,validateScenePlan} from '../../../web/map_infographic_v1/planner_scene_v1.mjs';
import {validateControlTimelineReference,canonicalControlTimelineState} from '../../../web/map_infographic_v1/control_timeline_contract_v1.mjs';
import {validatePresentation,compilePresentationEnginePlan,assertPresentationBoundaryContinuity} from '../presentation_plan.mjs';
import {analyzePrompt,canonicalJSON,validateLegacyScene} from '../../universal-data-pipeline-v1/prompt_pipeline.mjs';
import {analyzePresentationPrompt} from '../presentation_prompt.mjs';

// All shapes, source IDs, dates and hashes in this fixture are explicitly synthetic contract data.
const SHA='a'.repeat(64),SOURCE='b'.repeat(64),ADMISSION='c'.repeat(64),STATE='d'.repeat(64);
const red=[.85,.12,.12,.28],blue=[.1,.35,.95,.28];
const ref=()=>({schema:'WORLD_ENGINE_SOURCE_CONTROL_TIMELINE_REF_V1',url:'/qualified-control/'+SHA+'.json',
 sha256:SHA,bytes:1234,firstFrame:0,lastFrame:29,totalFrames:600,ownerIds:['SIDE_A','SIDE_B'],
 sourceId:'TEST_SOURCE',sourceSHA256:SOURCE,admissionSHA256:ADMISSION,firstStateSHA256:STATE,lastStateSHA256:STATE});
function facts(){return{version:'PLANNER_FACTS_V1',data_mode:'SYNTHETIC_TEST',semantic_mode:'ILLUSTRATIVE_FACT_BASED_VISUAL',
 subject:{id:'TEST_WAR',label:'Test war',aliases:['Test war'],event_family:'WAR'},
 locations:[{id:'ANCHOR',label:'Fixture anchor',anchor:[.5,.5]}],
 time_range:{start:'2000-01-01',end:'2000-01-02'},
 source_notes:[{id:'TEST_SOURCE',source_type:'SYNTHETIC_TEST',source_reference:'CONTRACT_TEST_ONLY_NO_HISTORY',
  verification_status:'SYNTHETIC_TEST',original_sha256:SOURCE}],
 geometries:[{id:'CONTEXT',source_id:'TEST_SOURCE',geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}},
  {id:'CONTEXT_LINE',source_id:'TEST_SOURCE',geometry:{type:'LineString',coordinates:[[0,0],[1,0]]}}],
 stages:[{id:'START',date:'2000-01-01',label:'Synthetic start',area_refs:['CONTEXT'],front_refs:['CONTEXT_LINE']},
  {id:'END',date:'2000-01-02',label:'Synthetic end',area_refs:['CONTEXT'],front_refs:['CONTEXT_LINE']}],
 camera:{anchor:[.5,.5],target_geometry_refs:['CONTEXT'],minimum_context_geometry_refs:['CONTEXT']},scale:{preferred:'REGIONAL'},
 scene_timing:{fps:30,total_frames:30,duration_seconds:1,camera_lock_frame:0,event_start_frame:0,
  initial_reveal_frames:4,state_transition_frames:20,final_hold_frames:6,action_frames:24,frame_policy:'INTEGER_DETERMINISTIC',blank_interstage_frames:0},
 control_timeline_ref:ref()};}
const scene=f=>compileScenePlan({topic:'Test war',facts:f??facts(),output:{width:1080,height:1920,fps:30}});
const presentation=()=>({camera:{mode:'KEYFRAMES',keyframes:[{frame:0,center:[.5,.5],zoom:1},{frame:29,center:[.5,.5],zoom:1}]},
 initialStateVisibility:'PRESERVE_PROVIDED',areaColors:{SIDE_A:red,SIDE_B:blue}});
const input=f=>({schema:'WORLD_ENGINE_DATA_PROMPT_V1',topic:'Test war',simulationType:'FICTIONAL',durationSeconds:1,
 fps:30,resolution:{width:1080,height:1920},renderSettings:{sourceRegionId:'korean_peninsula'},scenes:[{sceneId:'TEST',startFrame:0,endFrame:30,facts:f??facts()}]});
const hash=x=>createHash('sha256').update(canonicalJSON(x)).digest('hex');

test('facts and compiled Scene preserve the exact source reference without inline source data',()=>{
 const f=facts(),before=structuredClone(f),normalized=validateFactDataset(f),compiled=scene(f);
 assert.deepEqual(normalized.control_timeline_ref,f.control_timeline_ref);
 assert.deepEqual(compiled.control_timeline_ref,f.control_timeline_ref);assert.deepEqual(f,before);
 assert.equal(validateScenePlan(compiled).valid,true);
 const plan=compilePresentationEnginePlan({scene:compiled,presentation:presentation()});
 assert.equal(plan.globalEventStartFrame,0);assert.equal(plan.plans.length,1);
 assert.equal(plan.plans[0].engine,'SOURCE_CONTROL_TIMELINE_V1');
 assert.deepEqual(plan.plans[0].plan.controlTimelineRef,ref());
 assert.equal(plan.plans[0].presentationOperationBinding.sourceAdmissionPending,true);
 assert.equal(plan.plans[0].presentationOperationBinding.sourceGeometryGenerated,false);
});

test('source ref rejects remote paths, unpinned/private fields, unknown fields and missing hashes',()=>{
 for(const patch of [{url:'https://example.invalid/data.json'},{url:'/qualified-control/other.json'},
  {sourcePath:'/private/source.json'},{productionReady:true},{sha256:'x'.repeat(64)},{firstStateSHA256:undefined}])
  assert.throws(()=>validateControlTimelineReference({...ref(),...patch}),/CONTROL_TIMELINE_/);
 const f=facts();f.source_notes[0].original_sha256='f'.repeat(64);
 assert.throws(()=>validateFactDataset(f),/PLANNER_CONTROL_TIMELINE_SOURCE_BINDING_REQUIRED/);
});

test('source interval must exactly cover the scene and use the original zero-based 30fps clock',()=>{
 for(const patch of [{firstFrame:1},{lastFrame:30},{firstFrame:30,lastFrame:29},{lastFrame:600}]){
  const f=facts();Object.assign(f.control_timeline_ref,patch);
  assert.throws(()=>scene(f),/CONTROL_TIMELINE_.*(?:FRAME|RANGE)/);
 }
 const f=facts();f.scene_timing.event_start_frame=1;f.scene_timing.camera_lock_frame=1;
 assert.throws(()=>validateFactDataset(f),/PLANNER_CONTROL_TIMELINE_SCENE_FRAME_BINDING_REQUIRED/);
});

test('control mode requires one explicit translucent color per owner and forbids radial reveal',()=>{
 const s=scene();assert.deepEqual(validatePresentation(presentation(),{scene:s}).areaColors,presentation().areaColors);
 for(const colors of [undefined,{SIDE_A:red},{SIDE_A:red,SIDE_B:blue,OTHER:red},{SIDE_A:[1,0,0,1],SIDE_B:blue}])
  assert.throws(()=>validatePresentation({...presentation(),areaColors:colors},{scene:s}),/PRESENTATION_CONTROL_OWNER_COLORS_REQUIRED/);
 assert.throws(()=>validatePresentation({...presentation(),initialStateVisibility:'REVEAL'},{scene:s}),/PRESENTATION_CONTROL_TIMELINE_FULL_COVERAGE_REQUIRED/);
 assert.throws(()=>validatePresentation({...presentation(),territoryColors:{START:red}},{scene:s}),/PRESENTATION_CONTROL_TIMELINE_STATE_PALETTE_CONFLICT/);
});

test('PART reference continuity awaits actual bytes and rejects false adjacent-frame equivalence',()=>{
 const before={scene:scene(),presentation:presentation()},f=facts();
 f.time_range={start:'2000-01-02',end:'2000-01-03'};f.stages[0].date='2000-01-02';f.stages[1].date='2000-01-03';
 f.control_timeline_ref.firstFrame=30;f.control_timeline_ref.lastFrame=59;
 const after={scene:scene(f),presentation:presentation()};
 let result=assertPresentationBoundaryContinuity(before,after);
 assert.equal(result.status,'SOURCE_REFERENCE_CONTINUITY_BOUND_PENDING_BYTES');assert.equal(result.geometryMatched,null);
 assert.equal(result.sourceAdmissionClaimed,false);
 after.scene=structuredClone(after.scene);after.scene.control_timeline_ref.firstStateSHA256='e'.repeat(64);
 assert.throws(()=>assertPresentationBoundaryContinuity(before,after),/PRESENTATION_CUT_CONTROL_STATE_DISCONTINUITY/);
 after.scene.control_timeline_ref.firstStateSHA256=STATE;after.presentation.areaColors.SIDE_B=red;
 assert.throws(()=>assertPresentationBoundaryContinuity(before,after),/PRESENTATION_CUT_PROVIDED_STATE_DISCONTINUITY/);
});

test('legacy direct preview fails closed instead of silently rendering unchanged context geometry',()=>{
 assert.throws(()=>validateLegacyScene(scene()),/SOURCE_CONTROL_PRESENTATION_CONSUMER_REQUIRED/);
 const result=analyzePrompt(input());
 assert.ok(result.issues.some(x=>x.code==='SOURCE_CONTROL_PRESENTATION_CONSUMER_REQUIRED'));
 assert.equal(result.renderRequests.length,0);
 const connected=analyzePrompt(input(),{allowSourceControlReference:true});
 assert.equal(connected.status,'PASS',JSON.stringify(connected.issues));
 assert.deepEqual(connected.renderRequests[0].scene.control_timeline_ref,ref());
});

test('formal presentation compiler retains the typed binding and reports pending source-byte admission',async()=>{
 const envelope={schema:'WORLD_ENGINE_PRESENTATION_PROMPT_V2',prompt:'Test war, 1초 30fps',data:input(),
  region:{center:[.5,.5],bbox:[-1,-1,2,2],legacyProfileId:'korean_peninsula'},presentation:presentation()};
 const result=await analyzePresentationPrompt(envelope,{qualifyRegion:async()=>({status:'PASS',
  evidence:{scope:'SYNTHETIC_COMPILER_TEST_ONLY_NO_GEOGRAPHIC_SOURCE_ADMISSION'}})});
 assert.equal(result.status,'PASS',JSON.stringify(result.issues));
 const request=result.renderRequests[0];
 assert.equal(request.enginePlan.plans[0].engine,'SOURCE_CONTROL_TIMELINE_V1');
 assert.equal(request.controlTimelineGate.status,'REFERENCE_STRUCTURALLY_BOUND_RUNTIME_ADMISSION_PENDING');
 assert.equal(request.controlTimelineGate.sourceAdmissionClaimed,false);
 assert.deepEqual(request.scene.control_timeline_ref,ref());
 assert.equal(result.historicalRenderAllowed,false);assert.equal(result.paidExecutionAllowed,false);
});

test('old geographic or full-territory evidence cannot admit a new external control dataset',()=>{
 const f=facts();f.data_mode='PRODUCTION';f.source_notes[0].source_type='TEST_REVIEW_METADATA_ONLY';f.source_notes[0].verification_status='VERIFIED';
 const p=input(f);p.simulationType='HISTORICAL';
 p.scenes[0].historicalEvidence=[{recordId:'CONTEXT_REVIEW',sourceId:'TEST_SOURCE',claimId:'CONTEXT',geometryIds:['CONTEXT','CONTEXT_LINE'],stageIds:['START','END']}];
 const record={id:'CONTEXT_REVIEW',sourceId:'TEST_SOURCE',claimId:'CONTEXT',reviewStatus:'VERIFIED',
  sourceSHA256:SOURCE,sourceReference:f.source_notes[0].source_reference,canonicalFactsSHA256:hash(f),scope:'FULL_TERRITORY',
  geometrySHA256ById:Object.fromEntries(f.geometries.map(g=>[g.id,hash(g.geometry)])),applicableDates:f.time_range};
 const blocked=analyzePrompt(p,{evidenceRegistry:[record],allowSourceControlReference:true});
 assert.ok(blocked.issues.some(x=>x.code==='UNREVIEWED_CONTROL_TIMELINE'));
 const approved={...record,id:'CONTROL_REVIEW',claimId:'CONTROL',scope:'SOURCE_NATIVE_DATED_CONTROL',
  controlTimelineSHA256:SHA,controlTimelineAdmissionSHA256:ADMISSION};
 p.scenes[0].historicalEvidence.push({recordId:approved.id,sourceId:'TEST_SOURCE',claimId:approved.claimId,geometryIds:[],stageIds:[]});
 const bound=analyzePrompt(p,{evidenceRegistry:[record,approved],allowSourceControlReference:true});
 assert.equal(bound.status,'PASS',JSON.stringify(bound.issues));
 approved.controlTimelineAdmissionSHA256='f'.repeat(64);
 assert.ok(analyzePrompt(p,{evidenceRegistry:[record,approved],allowSourceControlReference:true}).issues.some(x=>x.code==='UNREVIEWED_CONTROL_TIMELINE'));
});

test('boundary-state canonicalization ignores object-key order but preserves owner and paint order',()=>{
 const a={areas:[{id:'a',ownerId:'SIDE_A',geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[0,1],[0,0]]]}}],fronts:[],frame:0};
 const b={frame:99,fronts:[],areas:[{geometry:a.areas[0].geometry,ownerId:'SIDE_A',id:'a'}]};
 assert.equal(canonicalControlTimelineState(a),canonicalControlTimelineState(b));
 b.areas[0].ownerId='SIDE_B';assert.notEqual(canonicalControlTimelineState(a),canonicalControlTimelineState(b));
 assert.throws(()=>canonicalControlTimelineState({areas:[{bad:NaN}],fronts:[]}),/CONTROL_TIMELINE_STATE_JSON_VALUE_REQUIRED/);
});
