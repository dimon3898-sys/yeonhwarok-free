/** Focused execution of this WAR input through unchanged public engine contracts.
 * No renderer, browser, GPU, image, map provider, or historical test suite is run.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const args=process.argv.slice(2), option=name=>{const i=args.indexOf(name);return i<0?null:args[i+1];};
const inputPath=option('--input'), outPath=option('--out'), resume=args.includes('--resume');
if(!inputPath||!outPath)throw Error('Usage: node validate_war_contract.mjs --input FILE --out DIRECTORY [--resume]');
const out=path.resolve(outPath),inputBytes=fs.readFileSync(inputPath),input=JSON.parse(inputBytes),sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const inputSHA256=sha(inputBytes),scriptSHA256=sha(fs.readFileSync(fileURLToPath(import.meta.url)));
fs.mkdirSync(out,{recursive:true});
const resultPath=path.join(out,'VALIDATION_RESULT.json'), existed=fs.existsSync(resultPath);
if(existed&&!resume)throw Error('EXISTING_EXECUTION_REQUIRES_RESUME_OR_NEW_OUTPUT_DIRECTORY');
let result=existed?JSON.parse(fs.readFileSync(resultPath,'utf8')):null;
if(result&&result.inputSHA256!==inputSHA256)throw Error('RESUME_INPUT_CHANGED_USE_SEPARATE_OUTPUT_DIRECTORY');
const json=x=>JSON.stringify(x,null,2)+'\n';
const write=(name,value)=>{const body=typeof value==='string'?value:json(value);fs.writeFileSync(path.join(out,name),body);return{path:name,sha256:sha(body),bytes:Buffer.byteLength(body)};};
const log=value=>{const line=JSON.stringify(value)+'\n';fs.appendFileSync(path.join(out,'EXECUTION_STDOUT.log'),line);process.stdout.write(line);};
const errorLog=value=>{const line=String(value)+'\n';fs.appendFileSync(path.join(out,'EXECUTION_STDERR.log'),line);process.stderr.write(line);};
const load=name=>JSON.parse(fs.readFileSync(path.join(out,name),'utf8'));
const save=()=>write('VALIDATION_RESULT.json',result);
const check=(condition,code)=>{if(!condition)throw Object.assign(Error(code),{code});};
if(!result){
 fs.writeFileSync(path.join(out,'EXECUTION_STDOUT.log'),'');fs.writeFileSync(path.join(out,'EXECUTION_STDERR.log'),'');
 fs.writeFileSync(path.join(out,'INPUT_SCENE.json'),inputBytes);
 result={schema:'WORLD_ENGINE_WAR_RUNTIME_CONTRACT_RESULT_V1',status:'RUNNING',inputSHA256,
  inputFile:path.basename(inputPath),createdAt:new Date().toISOString(),node:process.version,platform:process.platform,architecture:process.arch,
  sourceIdentity:'../../SOURCE_IDENTITY.json',steps:{},checks:{},scope:{
   newInputOnly:true,priorPassInvalidation:[],priorPassRerun:false,staticAuditRerun:false,
   engineFilesChanged:false,rendererChanged:false,imageBuilt:false,imagePulled:false,gpuExecuted:false,renderedFrames:0,
   execution:'Existing public facts-to-scene compiler, validator, existing Area adapter, presentation input validator, and CPU frame evaluator',
   envelopeSchema:input.schema,fullAnalyzePresentationPrompt:'NOT_RUN_NOT_CLAIMED',
   mapSourceQualification:'NOT_RUN_NOT_CLAIMED',nativeCameraProjectionAdmission:'NOT_RUN_NOT_CLAIMED',cameraVisualQuality:'NOT_RUN_NOT_CLAIMED',
   envelopeFieldsNotConsumedByTheseContracts:['prompt','region','data.simulationType','data.scenes[].dependsOn','data.scenes[].historicalEvidence'],
   envelopeFieldsBoundByHarness:['data.durationSeconds','data.fps','data.resolution','data.scenes[0].startFrame','data.scenes[0].endFrame'],
   cameraContract:'validatePresentation keyframes and state palette binding; no invented native camera plan',
   staticSourceIdentity:'Reuses SOURCE_IDENTITY.json; no prior 353-file or engine test suite rerun'}};
 save();
}
log({event:'EXECUTION_START',resume,inputSHA256,scriptSHA256,node:process.version});
const stage=async(name,fn)=>{
 if(result.steps[name]?.status==='PASS'){log({event:'SKIP_EXISTING_PASS',step:name,source:result.steps[name].report});return;}
 const startedAt=new Date().toISOString();log({event:'STEP_START',step:name});
 try{
  const value=await fn(),artifacts=[];
  for(const [filename,body]of Object.entries(value.artifacts??{}))artifacts.push(write(filename,body));
  const report={step:name,status:'PASS',startedAt,completedAt:new Date().toISOString(),inputSHA256,scriptSHA256,
   summary:value.summary??{},artifacts};
  const reportName='STEP_'+name+'.json';write(reportName,report);result.steps[name]={...report,report:reportName};
  result.status='RUNNING';delete result.failure;save();log({event:'STEP_PASS',step:name,summary:report.summary});
 }catch(error){
  const failure={name:error.name,code:error.code??error.message,message:error.message,stack:error.stack};
  const report={step:name,status:'FAIL',startedAt,completedAt:new Date().toISOString(),inputSHA256,scriptSHA256,error:failure};
  const reportName='STEP_'+name+'.json';write(reportName,report);result.steps[name]={...report,report:reportName};
  result.status='FAIL';result.failure={step:name,...failure};save();
  errorLog(error.stack??String(error));log({event:'STEP_FAIL',step:name,error:failure});throw error;
 }
};

try{
 await stage('COMPILE_SCENE_PLAN',async()=>{
  check(input.data?.scenes?.length===1,'FOCUSED_SINGLE_SCENE_REQUIRED');
  const {compileScenePlan}=await import('../../web/map_infographic_v1/planner_scene_v1.mjs');
  const scene=compileScenePlan({topic:input.data.topic,facts:input.data.scenes[0].facts,
   output:{fps:input.data.fps,width:input.data.resolution.width,height:input.data.resolution.height}});
  check(scene.event_type==='WAR','WAR_COMPILED_FAMILY_REQUIRED');
  return{summary:{schema:scene.metadata.schema,eventType:scene.event_type,totalFrames:scene.timing.total_frames,
   factsNativeContextBinding:'facts.native_context -> scene.camera_intent.native_context',
   factsCameraBinding:'facts.camera -> scene.camera_intent; presentation.camera remains separate',
   sourceGeometryCount:scene.geometries.length},artifacts:{'COMPILED_SCENE.json':scene}};
 });
 await stage('VALIDATE_SCENE_PLAN',async()=>{
  const {validateScenePlan}=await import('../../web/map_infographic_v1/planner_scene_v1.mjs');
  const response=validateScenePlan(load('COMPILED_SCENE.json'));
  check(response.valid===true,'SCENE_VALIDATOR_DID_NOT_ACCEPT');
  return{summary:response,artifacts:{'SCENE_VALIDATION.json':response}};
 });
 await stage('COMPILE_EXISTING_ENGINE_PLAN',async()=>{
  const {compileExistingEnginePlan}=await import('../../web/map_infographic_v1/planner_engine_adapter_v1.mjs');
  const engine=compileExistingEnginePlan(load('COMPILED_SCENE.json'));
  check(engine.newEngine===false&&engine.newRenderer===false,'EXISTING_ENGINE_OWNERS_REQUIRED');
  check(engine.plans.length===1&&engine.plans[0].engine==='EXISTING_AREA_V3','EXPECTED_EXISTING_AREA_BINDING_REQUIRED');
  const plan=engine.plans[0].plan;
  return{summary:{family:engine.family,engine:engine.plans[0].engine,totalFrames:engine.totalFrames,
   newEngine:engine.newEngine,newRenderer:engine.newRenderer},artifacts:{'EXISTING_ENGINE_PLAN.json':engine,
   'ENGINE_SUMMARY.json':{version:engine.version,family:engine.family,totalFrames:engine.totalFrames,
    globalEventStartFrame:engine.globalEventStartFrame,engine:engine.plans[0].engine,states:plan.intent.states.map(s=>({id:s.state_id,date:s.time_label,areaIds:s.areas.map(a=>a.id),frontIds:s.fronts.map(f=>f.id)})),
    operations:plan.operations,timeline:plan.timeline,sourceGeometryBinding:engine.sourceGeometryBinding,
    newEngine:engine.newEngine,newRenderer:engine.newRenderer,physicalSimulation:engine.physicalSimulation}}};
 });
 await stage('COMPILE_PRESENTATION_ENGINE_PLAN',async()=>{
  const {compilePresentationEnginePlan}=await import('../universal-presentation-v2/presentation_plan.mjs');
  const engine=compilePresentationEnginePlan({scene:load('COMPILED_SCENE.json'),presentation:input.presentation});
  if((input.presentation.initialStateVisibility??'REVEAL')==='REVEAL')assert.deepEqual(engine,load('EXISTING_ENGINE_PLAN.json'));
  return{summary:{initialStateVisibility:input.presentation.initialStateVisibility??'REVEAL',engine:engine.plans[0].engine,
   originalTimelinePreserved:true},artifacts:{'PRESENTATION_ENGINE_PLAN.json':engine}};
 });
 await stage('VALIDATE_PRESENTATION',async()=>{
  const {validatePresentation}=await import('../universal-presentation-v2/presentation_plan.mjs');
  const presentation=validatePresentation(input.presentation,{scene:load('COMPILED_SCENE.json'),region:input.region});
  assert.deepEqual(presentation.camera,input.presentation.camera);
  assert.deepEqual(presentation.territoryColors,input.presentation.territoryColors);
  return{summary:{cameraMode:presentation.camera.mode,keyframeFrames:presentation.camera.keyframes.map(k=>k.frame),
   keyframeCount:presentation.camera.keyframes.length,paletteStateIds:Object.keys(presentation.territoryColors),
   cameraInputContract:'PASS',nativeCameraAdmission:'NOT_RUN_NOT_CLAIMED',visualOutput:'NOT_RUN_NOT_CLAIMED'},
   artifacts:{'VALIDATED_PRESENTATION.json':presentation}};
 });
 await stage('EVALUATE_AREA_FRAMES',async()=>{
  const {evaluateAreaFrame}=await import('../../web/map_infographic_v1/area_core_v3.mjs');
  const scene=load('COMPILED_SCENE.json'),engine=load('PRESENTATION_ENGINE_PLAN.json'),plan=engine.plans[0].plan;
  check(scene.timing.total_frames===180&&scene.timing.fps===30&&scene.timing.duration_seconds===6,'EXPECTED_6S_180_FRAME_SCENE_REQUIRED');
  check(input.data.durationSeconds===6&&input.data.fps===30&&input.data.scenes[0].startFrame===0&&input.data.scenes[0].endFrame===180,'ENVELOPE_TO_COMPILED_TIMELINE_BINDING');
  check(plan.totalFrames===180&&plan.startFrame===0&&plan.endFrame===180&&engine.globalEventStartFrame===0,'AREA_RUNTIME_FRAME_RANGE_BINDING');
  assert.deepEqual(scene.metadata.output,{width:1080,height:1920,fps:30,audio:false});
  assert.deepEqual(scene.time_steps.map(s=>({id:s.id,start:s.start_frame,length:s.transition_frames})),[
   {id:'S0',start:0,length:30},{id:'S1',start:30,length:45},{id:'S2',start:75,length:45}]);
  const supplied=new Map(input.data.scenes[0].facts.geometries.map(g=>[g.id,g.geometry]));
  const areaRows=new Map(scene.areas.map(a=>[a.id,a])),frontRows=new Map(scene.front_lines.map(f=>[f.id,f]));
  const frames=[],counts={S0:0,S1:0,S2:0},beforeScene=JSON.stringify(scene),beforePlan=JSON.stringify(plan);
  for(let f=0;f<180;f++){
   const frame=evaluateAreaFrame(plan,f);
   check(frame.frame===f&&frame.localFrame===f&&frame.timeSeconds===f/30,'RUNTIME_FRAME_CLOCK_BINDING_'+f);
   check(frame.hold===(f>=120),'RUNTIME_FINAL_HOLD_RANGE_'+f);
   check(frame.areas.length>0&&frame.fronts.length>0,'RUNTIME_AREA_FRONT_REQUIRED_'+f);
   check(frame.impacts.length===0&&frame.propagations.length===0,'WAR_UNREQUESTED_EFFECTS_'+f);
   const areaStates=[...new Set(frame.areas.map(x=>x.state_id))].sort(),frontStates=[...new Set(frame.fronts.map(x=>x.state_id))].sort();
   assert.deepEqual(areaStates,frontStates,'Runtime area/front state sets differ at frame '+f);
   check(areaStates.includes(frame.stateId),'RUNTIME_SELECTED_STATE_NOT_PRESENT_'+f);
   check(['S0','S1','S2'].includes(frame.stateId),'RUNTIME_UNKNOWN_STATE_'+f);counts[frame.stateId]++;
   const stage=scene.time_steps.find(s=>s.id===frame.stateId);
   check(frame.timeLabel===stage.date&&frame.timeLabelVisible===true,'RUNTIME_STATE_DATE_BINDING_'+f);
   for(const area of frame.areas){
    const row=areaRows.get(area.id);check(row&&row.stage_id===area.state_id,'RUNTIME_AREA_STAGE_BINDING_'+f);
    assert.deepEqual(area.geometry,supplied.get(row.geometry_ref),'Area geometry differs from supplied input at '+f);
    assert.deepEqual(area.sourceGeometry,supplied.get(row.geometry_ref));
    check(Number.isFinite(area.alpha)&&area.alpha>=0&&area.alpha<=1,'RUNTIME_AREA_ALPHA_'+f);
    check(area.coverage===1&&area.transform.translation.every(v=>v===0),'RUNTIME_UNREQUESTED_AREA_DEFORMATION_'+f);
   }
   for(const front of frame.fronts){
    const row=frontRows.get(front.id);check(row&&row.stage_id===front.state_id,'RUNTIME_FRONT_STAGE_BINDING_'+f);
    assert.deepEqual(front.geometry,supplied.get(row.geometry_ref),'Front geometry differs from supplied input at '+f);
    check(Number.isFinite(front.alpha)&&front.alpha>=0&&front.alpha<=1&&Number.isFinite(front.revealFraction)&&front.revealFraction>=0&&front.revealFraction<=1,'RUNTIME_FRONT_REVEAL_RANGE_'+f);
    const area=frame.areas.find(a=>a.state_id===front.state_id);check(area,'RUNTIME_FRONT_WITHOUT_AREA_'+f);
    check(Math.abs(area.alpha-front.alpha*front.revealFraction)<1e-12,'RUNTIME_AREA_FRONT_OPACITY_BINDING_'+f);
   }
   const frontAlpha=frame.fronts.reduce((n,x)=>n+x.alpha,0);check(Math.abs(frontAlpha-1)<1e-12,'RUNTIME_STATE_ALPHA_TOTAL_'+f);
   if(f<=30)check(frame.stateId==='S0','RUNTIME_INITIAL_STATE_'+f);
   if(f===74||f===75)check(frame.stateId==='S1','RUNTIME_MIDDLE_STATE_ENDPOINT_'+f);
   if(f>=119)check(frame.stateId==='S2','RUNTIME_FINAL_STATE_'+f);
   if(f>=120)check(frame.areas.length===1&&frame.areas[0].alpha===1&&frame.fronts.length===1&&frame.fronts[0].revealFraction===1,'RUNTIME_FINAL_HOLD_CONTENT_'+f);
   frames.push({frame:f,stateId:frame.stateId,timeLabel:frame.timeLabel,hold:frame.hold,
    activeFeatures:frame.activeFeatures,areas:frame.areas.map(a=>({id:a.id,stateId:a.state_id,geometryRef:areaRows.get(a.id).geometry_ref,alpha:a.alpha,geometrySHA256:sha(JSON.stringify(a.geometry))})),
    fronts:frame.fronts.map(a=>({id:a.id,stateId:a.state_id,geometryRef:frontRows.get(a.id).geometry_ref,alpha:a.alpha,revealFraction:a.revealFraction,geometrySHA256:sha(JSON.stringify(a.geometry))}))});
  }
  check(JSON.stringify(scene)===beforeScene&&JSON.stringify(plan)===beforePlan,'RUNTIME_SOURCE_MUTATION');
  return{summary:{evaluatedFrames:frames.length,rangeInclusive:[0,179],exclusiveEndFrame:180,fps:30,durationSeconds:6,
   stateFrameCounts:counts,holdFrames:frames.filter(f=>f.hold).length,areaFrontSourceBinding:'PASS',sourceGeometryPreserved:true,
   sourcePlanMutated:false,renderedFrames:0,projectionEvaluated:false},artifacts:{'FRAME_EVIDENCE.json':{schema:'WORLD_ENGINE_WAR_FRAME_EVIDENCE_V1',frames}}};
 });
 result.status='PASS';result.completedAt=new Date().toISOString();
 result.checks={actualNodeEngineContract:'PASS',territoryStateAndFrontBinding:'PASS',timeline180Frames:'PASS',
  cameraInputContract:'PASS',sceneDataErrors:'NONE_IN_EXECUTED_CONTRACT_SCOPE',localExecutionEvidence:'PRESERVED',githubBackup:'PENDING_ROOT_PUBLICATION'};
 result.nextAction='Preserve evidence and final input on existing recovery branch; no GPU or next rendering stage authorized.';
 save();log({event:'EXECUTION_PASS',inputSHA256,checks:result.checks});
}catch{process.exitCode=1;}
