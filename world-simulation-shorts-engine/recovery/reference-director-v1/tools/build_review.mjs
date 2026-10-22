/** Build an honest, explicitly non-executable handoff from supplied evidence.
 * This tool never instantiates a renderer, creates a claim or starts a worker.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {createWindowContract,mapWindowFrame,RENDERER_CONNECTION} from '../director_camera.mjs';
import {compileUnboundReferenceSchedule,evaluateReferenceEvents} from '../director_events.mjs';

const here=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';
const fail=code=>{throw Error(code);};
export function buildReview({target,input,sourceAudit,targetSHA256}) {
 if(input?.schema!=='WORLD_ENGINE_REFERENCE_DIRECTOR_INPUT_V1'||input.gate?.renderAllowed!==false)
  fail('RD_REVIEW_EXPLICIT_PARTIAL_INPUT_REQUIRED');
 if(sourceAudit?.decodedFrames!==635||sourceAudit.decodedPixelHashComparison?.matched!==635||
    sourceAudit.decodedPixelHashComparison?.mismatchedFrames?.length||sourceAudit.planContractErrors?.length)
  fail('RD_REVIEW_ACTUAL_SOURCE_AUDIT_REQUIRED');
 if(!/^[a-f0-9]{64}$/.test(targetSHA256))fail('RD_REVIEW_TARGET_HASH_REQUIRED');
 const contract=createWindowContract(target),schedule=compileUnboundReferenceSchedule(target);
 const frames=contract.windows.flatMap(window=>Array.from({length:window.outputFrames},(_,localFrame)=>{
  const mapping=mapWindowFrame(contract,window.id,localFrame);
  return {...mapping,camera:null,cameraStatus:RENDERER_CONNECTION,
   eventAuthoringState:evaluateReferenceEvents(schedule,mapping.referenceFrame),
   sourceEnvelope:null,actualDraw:null,renderAllowed:false};
 }));
 const trace=[['referenceFrame','coreFrame','windowId','localFrame','bindingKey','inputId',
  'sidecarField','intendedState','actualDrawStatus','pixelBBox','sourceHash']];
 const records=Object.values(input.dataRecords??{}).flat();
 const binding=key=>{
  const indexed=/^([A-Za-z]+)\[(\d+)\]$/.exec(key);
  return indexed?input.dataBindings?.[indexed[1]]?.[Number(indexed[2])]:input.dataBindings?.[key];
 };
 const add=(row,key,field,state,hash='')=>{
  const id=binding(key),record=records.find(r=>r.id===id);
  trace.push([row.referenceFrame,row.coreFrame,row.windowId,row.localFrame,
   key,id??'',field,state,'NOT_EXECUTED_BLOCKED','',hash||record?.source?.sha256||'']);
 };
 for(const row of frames){const s=row.eventAuthoringState;
  add(row,'primaryCountryGeometryId','staticArea','SUPPLIED_GEOMETRY_UNCHANGED');
  add(row,'contextRegionGeometryId','contextArea.opacityFraction',s.contextArea.opacityFraction);
  for(let i=0;i<2;i++){
   add(row,`contextLocationIds[${i}]`,`contextPins[${i}].scale`,s.contextPins[i].scale);
   add(row,`contextLocationIds[${i}]`,`labels[${i}].glyphOpacity`,JSON.stringify(s.labels[i].glyphs.map(g=>g.opacity)));
  }
  add(row,'detailLocationId','heroPin.scale',s.heroPin.scale);
  add(row,'detailBoundaryGeometryId','boundary.revealFraction',s.boundary.revealFraction);
  add(row,'metricValueId','metric.glyphOpacity',JSON.stringify(s.metric.glyphs.map(g=>g.opacity)),target.reference.sha256);
 }
 const requests=contract.windows.map(window=>({
  request:{schema:'WORLD_ENGINE_REFERENCE_DIRECTOR_STUDIO_REQUEST_V1',windowId:window.id,targetSHA256},
  outputFrames:window.outputFrames,globalSourceRange:window.sourceFrameRange,
  output:{width:1080,height:1920,fps:30,audio:false,codec:'H264'},
  executable:false,renderAllowed:false,reason:['CAPABILITY_EXTENSION_REQUIRED','DATA_DETAIL_BLOCKED'],
 }));
 return {track:{schema:'WORLD_ENGINE_REFERENCE_DIRECTOR_PARTIAL_TRACK_V1',
  status:'AUTHORING_EVENTS_COMPILED_CAMERA_AND_PIXELS_BLOCKED',notAnExecutableScene:true,
  targetSHA256,globalFrameContract:contract,frameCount:frames.length,frames,
  actualRenderedFrames:0,actualMapPixelVerified:false,nvidiaVerified:false,
  sourceEnvelopeVerified:false,cameraLocked:false,settleLocked:false,
  rendererConnection:RENDERER_CONNECTION,renderAllowed:false,historicalG3:'BLOCKED'},
  requests,traceCSV:trace.map(row=>row.map(quote).join(',')).join('\n')+'\n',
  gates:{schema:'WORLD_ENGINE_REFERENCE_DIRECTOR_GATE_DECISION_V1',
   phaseA:'PASS_SOURCE_BASELINE_TESTS_ARE_SEPARATE_RECEIPTS',
   phaseB:'PARTIAL_CAPABILITY_EXTENSION_REQUIRED',phaseC:'DATA_DETAIL_BLOCKED',
   phaseD:'BLOCKED_PRE_RENDER_GATES_NOT_PASSED',phaseE:'NOT_EXECUTED_NO_RENDER_OUTPUT',
   DIRECTOR_IMPLEMENTATION:'PARTIAL_CONTRACTS_ONLY_NOT_NATIVE_MAP_DRAW',
   GEO_AND_SOURCE_READY:'DATA_DETAIL_BLOCKED',REFERENCE_VISUAL_MATCH:'NOT_EVALUATED',
   HISTORICAL_G3:'BLOCKED',renderAllowed:false,paidGpuExecuted:false,paidApiUsed:false,
   deploymentExecuted:false,finalPromoted:false,
   omittedArtifacts:[
    'REF64306_A_CONTEXT_6S.mp4','REF64306_B_FOCUS_6S.mp4','REF64306_C_BOUNDARY_METRIC_6P2S.mp4',
    'REFERENCE_VS_RENDER_CONTACT_SHEET.png','ALL_RENDERED_FRAME_AUDIT'],
   omittedArtifactReason:'Native common rotated projection hook and source-detail prerequisites are missing. No placeholder images or movies generated.'}};
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const targetFile=path.join(here,'supplied/REFERENCE_DIRECTOR_TARGET_V1.json');
 const out=buildReview({target:read(targetFile),input:read(path.join(here,'REFERENCE_DIRECTOR_INPUT.json')),
  sourceAudit:read(path.join(here,'reports/REFERENCE_INPUT_AUDIT.json')),targetSHA256:sha(fs.readFileSync(targetFile))});
 const writes={
  'COMPILED_DIRECTOR_TRACK.json':JSON.stringify(out.track,null,2)+'\n',
  'INPUT_TO_PIXEL_TRACE.csv':out.traceCSV,
  'reports/BLOCKED_STUDIO_WINDOW_REQUESTS.json':JSON.stringify(out.requests,null,2)+'\n',
  'reports/GATE_DECISION.json':JSON.stringify(out.gates,null,2)+'\n',
 };
 for(const [name,bytes]of Object.entries(writes))fs.writeFileSync(path.join(here,name),bytes,{flag:'wx'});
 console.log(JSON.stringify({authoringFrames:out.track.frameCount,actualDrawnFrames:0,renderAllowed:false,
  windowFrames:out.requests.map(w=>w.outputFrames),traceRows:out.traceCSV.trim().split('\n').length-1}));
}
