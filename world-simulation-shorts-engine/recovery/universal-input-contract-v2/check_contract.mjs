/** New external-history/window contract only. Never launches a browser or GPU. */
import fs from 'node:fs/promises';import path from 'node:path';import assert from 'node:assert/strict';import {fileURLToPath} from 'node:url';
import {compileHistoryInputV2,verifyHistoryInputV2Runtime} from '../universal-presentation-v2/history_input_v2.mjs';
import {compileAuthoredHistory} from '../universal-presentation-v2/history_authored_v1.mjs';
import {loadExternalHistoryDataset,dataHash} from '../universal-presentation-v2/external_history_data.mjs';
import {sourceFrameForWindow,validateTimelineWindow,WINDOW_RUNTIME_PROFILE} from '../universal-presentation-v2/timeline_window.mjs';
import {continuousTerritoryAt} from '../universal-presentation-v2/continuous_territory_runtime.mjs';
import {runtimeDurationContract} from '../codex-to-gcube-handoff-v1/backend/profile_contract.mjs';
import {verifyGeneratedSources} from '../codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs';
import {validateRuntimeRequest} from '../codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs';
const D=path.dirname(fileURLToPath(import.meta.url)),E=path.resolve(D,'../..'),P=E+'/production/mongol-three-6s-20261114',O=E+'/production/reference-reconstruction-20s-20261114';
const read=async f=>JSON.parse(await fs.readFile(f));const config=await read(process.argv[2]);const checks=[];
async function pass(name,fn){await fn();checks.push({name,status:'PASS'});}
async function reject(name,fn,code){await assert.rejects(fn,e=>typeof e.message==='string'&&e.message.includes(code));checks.push({name,status:'PASS_REJECTED',expectedCode:code});}
const original=await read(O+'/FINAL_20S_INPUT.json'),prior=await read(O+'/CONTROLLER_TRANSPORT_TESTS.json');
// This exact changed helper comparison replaces, and does not repeat, the old full PASS suite.
const legacy=await compileAuthoredHistory(original.prompt);
await pass('CHANGED_SHARED_DISPLAY_HELPER_MATCHES_RETAINED_V1_HASH',()=>assert.equal(legacy.historicalAdmission.runtimeSegmentSHA256,prior.historicalAdmission.runtimeSegmentSHA256));
const compiled=[],inputs=[],reports=[];
for(let i=1;i<=3;i++){
 const name=`MONGOL_6S_PART_0${i}.json`,file=P+'/'+name,raw=await fs.readFile(file),input=JSON.parse(raw);inputs.push(input);
 const c=await compileHistoryInputV2(input.prompt,config),s=c.renderRequests[0];
 const runtime={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',profile:WINDOW_RUNTIME_PROFILE,simulationType:'HISTORICAL',durationSeconds:6,totalFrames:180,sourceInputSHA256:c.inputSHA256,historicalAdmission:c.historicalAdmission,segments:[s],transitions:[],inputTrace:c.inputTrace};
 await pass(name+'_COMPILE_AND_SOURCE_REVERIFY',async()=>{await verifyHistoryInputV2Runtime(runtime,config);assert.equal(runtimeDurationContract(runtime).profile,'GCUBE_NVIDIA_HISTORICAL_V2');assert.equal(validateRuntimeRequest(runtime),true);});
 await pass(name+'_UNCHANGED_GLOBAL_DISPLAY_AND_GEOMETRY',()=>{assert.deepEqual(s.scene,legacy.renderRequests[0].scene);assert.deepEqual(s.presentation,legacy.renderRequests[0].presentation);assert.deepEqual(s.region,legacy.renderRequests[0].region);assert.equal(s.presentation.territoryChanges.items[0].continuous.frames.length,106);});
 compiled.push(runtime);reports.push({file:name,sha256:dataHash(raw),schema:input.prompt.schema,status:'PASS_NEW_SOURCE_CONTRACT',totalFrames:180,durationSeconds:6,fps:30,resolution:[1080,1920],window:s.timelineWindow,sourceFrames:600,sourceGeometryCount:106,authoredInputSHA256:c.inputSHA256,runtimeSegmentSHA256:c.historicalAdmission.runtimeSegmentSHA256,GPU_RENDER:'PENDING_GPU',IMAGE_INCLUDED:'PENDING_IMAGE',outputIsolation:'Existing private job ID / output/VIDEO.mp4; distinct input hashes and job IDs'});
}
const state=(s,f)=>({camera:s.presentation.camera.frames[f],territory:continuousTerritoryAt(s.presentation.territoryChanges,f),labels:s.presentation.labels.items.filter(x=>f>=x.startFrame&&f<x.endFrame).map(x=>({id:x.id,text:x.text,alpha:Math.min(1,(f-x.startFrame+1)/x.revealFrames,(x.endFrame-f)/x.exitFrames)})),map:s.presentation.mapStyle});
const baseline=legacy.renderRequests[0];const frameHashes=[];
await pass('ALL_540_SELECTED_FRAMES_EXACT_SOURCE_STATE',()=>{for(let part=0;part<3;part++){const s=compiled[part].segments[0];for(let local=0;local<180;local++){const global=sourceFrameForWindow(local,s.timelineWindow,600);assert.equal(global,part*180+local);const actual=state(s,global),expected=state(baseline,global);assert.deepEqual(actual,expected);frameHashes.push(dataHash(actual));}}});
await pass('BOUNDARY_MUTATION_IS_DETECTED',()=>{for(const part of [1,2]){const s=compiled[part].segments[0],correct=state(s,part*180),reset=state(s,0);assert.notDeepEqual(correct,reset);}});
await pass('LOCAL_OUT_OF_RANGE_REJECTED',()=>{for(const frame of [-1,180,1.5,true])assert.throws(()=>sourceFrameForWindow(frame,{startFrame:180,endFrame:360},600),/UP2_WINDOW_LOCAL_FRAME/);});
const mutations=[
 ['DURATION',p=>p.output.durationSeconds=10,'OUTPUT_CONTRACT'],['FPS',p=>p.output.fps=24,'OUTPUT_CONTRACT'],['RESOLUTION',p=>p.output.width=1920,'OUTPUT_CONTRACT'],['FALSE_HISTORY',p=>p.simulationType='GENERAL','EXPLICIT_PROFILE'],
 ['INPUT_PATH',p=>p.source.path='/etc/passwd','UP2_DATA_REFERENCE'],['INPUT_URL',p=>p.source.url='https://example.invalid/data','UP2_DATA_REFERENCE'],['INPUT_CODE',p=>p.module='evil.mjs','INPUT_FIELDS'],
 ['MISSING_SOURCE',p=>delete p.source,'INPUT_FIELDS'],['WRONG_HASH',p=>p.source.sha256='0'.repeat(64),'UP2_DATA_CATALOG_RECORD'],['UNREVIEWED_ID',p=>p.source.id='UNREVIEWED','UP2_DATA_UNREGISTERED_OR_DUPLICATE'],
 ['WINDOW_LENGTH',p=>p.timeline.window.endFrame=179,'OUTPUT_LENGTH'],['WINDOW_RANGE',p=>p.timeline.window={startFrame:500,endFrame:680},'RANGE'],['WINDOW_FLOAT',p=>p.timeline.window.startFrame=.5,'RANGE'],['MISSING_CAMERA',p=>delete p.presentation.camera,'PRESENTATION_FIELDS'],['MISSING_MAP',p=>delete p.presentation.mapStyle,'PRESENTATION_FIELDS'],['RETIME_106_SHAPES',p=>p.timeline.timing.territoryEndFrame=282,'REUSED_GEOMETRY_TIME_BINDING']];
for(const[name,change,code]of mutations){const p=structuredClone(inputs[0].prompt);change(p);await reject(name,()=>compileHistoryInputV2(p,config),code);}
await reject('OPERATOR_PIN_REQUIRED',()=>loadExternalHistoryDataset(inputs[0].prompt.source,{...config,catalogSHA256:''}),'OPERATOR_CATALOG_PIN_REQUIRED');
await reject('WRONG_OPERATOR_PIN',()=>loadExternalHistoryDataset(inputs[0].prompt.source,{...config,catalogSHA256:'0'.repeat(64)}),'HASH_MISMATCH');
const unsafe=config.dataRoot+'-unsafe';await fs.mkdir(unsafe,{mode:0o777});await fs.chmod(unsafe,0o777);
try{await reject('WORLD_WRITABLE_ANCESTOR',()=>loadExternalHistoryDataset(inputs[0].prompt.source,{...config,dataRoot:unsafe}),'ROOT_PERMISSIONS');}finally{await fs.rmdir(unsafe);}
const link=config.dataRoot+'-symlink';await fs.symlink(config.dataRoot,link);
try{await reject('SYMLINK_ROOT',()=>loadExternalHistoryDataset(inputs[0].prompt.source,{...config,dataRoot:link}),'ROOT_PERMISSIONS');}finally{await fs.unlink(link);}
const catalogFile=config.dataRoot+'/catalog.json',stat=await fs.stat(catalogFile);await fs.chmod(catalogFile,0o666);
try{await reject('WRITABLE_CATALOG',()=>loadExternalHistoryDataset(inputs[0].prompt.source,config),'FILE_POLICY');}finally{await fs.chmod(catalogFile,stat.mode&0o777);}
const pkgFile=config.dataRoot+'/'+inputs[0].prompt.source.sha256+'.json',pkgStat=await fs.stat(pkgFile);await fs.chmod(pkgFile,0o666);
try{await reject('WRITABLE_PACKAGE',()=>loadExternalHistoryDataset(inputs[0].prompt.source,config),'FILE_POLICY');}finally{await fs.chmod(pkgFile,pkgStat.mode&0o777);}
const changed=structuredClone(compiled[1]);changed.segments[0].timelineWindow={startFrame:0,endFrame:180};await reject('POST_ADMISSION_WINDOW_TAMPER',()=>verifyHistoryInputV2Runtime(changed,config),'RUNTIME_SOURCE_OR_DISPLAY_CHANGED');
const downgrade=structuredClone(compiled[0]);delete downgrade.profile;await pass('PROFILE_DOWNGRADE_REJECTED',()=>assert.throws(()=>runtimeDurationContract(downgrade),/HANDOFF_LEGACY_PROFILE_FIELDS_CHANGED/));
await pass('LEGACY_6_AND_10_SELECTOR_DEFAULTS_UNCHANGED',()=>{for(const n of [6,10]){const r={totalFrames:n*30,...(n===10?{durationSeconds:10}:{})};assert.deepEqual(runtimeDurationContract(r),{durationSeconds:n,totalFrames:n*30,profile:'GCUBE_NVIDIA_SIX_SECOND_REVIEW_V1'});}});
await pass('GENERATED_ORIGINAL_SHA_BINDINGS',verifyGeneratedSources);
const boundaries=[179,180,359,360].map(f=>({globalFrame:f,part:Math.floor(f/180)+1,localFrame:f%180,stateSHA256:frameHashes[f],continuousIndex:continuousTerritoryAt(baseline.presentation.territoryChanges,f).index,camera:baseline.presentation.camera.frames[f],visibleLabels:state(baseline,f).labels}));
const continuity={schema:'WORLD_ENGINE_THREE_PART_CONTINUITY_V2',status:'PASS_DATA_AND_FRAME_MAPPING_ONLY',framesCompared:540,sourceFrames:600,trimmedFrames:[540,599],timeCompression:false,geometryRegenerated:false,boundaries,frameStateHashes:frameHashes,actualDraws:0,visualQuality:'PENDING_GPU_MP4_REVIEW'};
await fs.writeFile(P+'/THREE_PART_CONTINUITY_REPORT.json',JSON.stringify(continuity,null,2)+'\n');
await fs.writeFile(D+'/CONTRACT_VALIDATION.json',JSON.stringify({schema:'WORLD_ENGINE_EXTERNAL_HISTORY_CONTRACT_CHECK_V2',status:'PASS_CHANGED_SCOPE_ONLY',checks,checkCount:checks.length,inputs:reports,paidGPUStarts:0,rendererExecutions:0,oldSuitesRerun:0,currentNodeWebGL:'UNCONFIRMED',legacy6sGPU:'PRESERVED_NOT_REEXECUTED'},null,2)+'\n');
console.log(JSON.stringify({status:'PASS_CHANGED_SCOPE_ONLY',checks:checks.length,inputs:3,framesCompared:540,actualDraws:0}));
