/** Proposed camera/source window preparation only. Does not create a runtime/context. */
import path from 'node:path';
import {createHash} from 'node:crypto';
import {readPinnedServerFile} from './candidate_asset_snapshot.mjs';
import {prepareRegisteredBinaryLayerV3,BINARY_REQUEST_SCHEMA} from './candidate_binary_preparation_v3.mjs';
export const FRAME_WINDOW_SCHEMA='WORLD_ENGINE_PROPOSED_FRAME_WINDOW_PREPARATION_V1';
export const WINDOWS=Object.freeze([
 Object.freeze({id:'segment1_overview_0_54',segment:1,layerId:'segment1_overview',first:0,last:54}),
 Object.freeze({id:'segment1_regional_55_149',segment:1,layerId:'segment1_regional',first:55,last:149}),
 ...[2,3,4].map(segment=>Object.freeze({id:`segment${segment}_overview_0_149`,segment,layerId:`segment${segment}_overview`,first:0,last:149}))]);
const check=(v,c)=>{if(!v)throw Error(c);},sha=b=>createHash('sha256').update(b).digest('hex');
const freeze=v=>{if(v&&typeof v==='object'){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
export const isFrameWindowRequest=request=>request?.schema===FRAME_WINDOW_SCHEMA;
export function assertCandidateContextAdmission(){throw Error('UP2_CANDIDATE_CONTEXT_NOT_ADMITTED');}
export async function prepareRegisteredFrameWindow({request,registry,expectedSourceQualificationSHA256}={}){
 check(request&&Object.keys(request).sort().join(',')==='camera,first,frames,last,layerId,registrationId,schema,windowId','UP2_WINDOW_REQUEST_KEYS');
 const input=freeze(structuredClone(request));check(isFrameWindowRequest(input),'UP2_WINDOW_SCHEMA');
 check(registry instanceof Map&&registry.has(input.registrationId),'UP2_WINDOW_SERVER_REGISTRATION_REQUIRED');
 const registration=freeze(structuredClone(registry.get(input.registrationId)));
 const selected=WINDOWS.find(w=>w.id===input.windowId);check(selected&&selected.layerId===input.layerId&&selected.first===input.first&&selected.last===input.last,'UP2_WINDOW_EXPLICIT_LAYER_SCHEDULE');
 const count=input.last-input.first+1;check(Number.isSafeInteger(count)&&count>=2&&count<=240&&Array.isArray(input.frames)&&input.frames.length===count,'UP2_WINDOW_LIMIT');
 const expectedCamera={projection:'REGIONAL_EQUIRECTANGULAR',projectionMode:null,updateMethod:'updateCamera',width:1080,height:1920};
 check(input.camera&&Object.keys(input.camera).length===5&&Object.entries(expectedCamera).every(([k,v])=>input.camera[k]===v),'UP2_WINDOW_CONTROLLED_CAMERA');
 check(registration&&Object.keys(registration).sort().join(',')==='binary,camera','UP2_WINDOW_REGISTRATION');
 const c=registration.camera,b=await readPinnedServerFile(c.root,c.localFile,c),contract=JSON.parse(b.toString('utf8'));
 check(contract.schema==='WORLD_ENGINE_PROPOSED_CONTROLLED_FLAT_CAMERA_V1'&&contract.renderAllowed===false&&contract.productionAdmitted===false&&contract.proposedExecution===false&&contract.frames?.length===600,'UP2_WINDOW_PROPOSED_CONTRACT');
 check(JSON.stringify(contract.camera)===JSON.stringify(input.camera)||Object.entries(expectedCamera).every(([k,v])=>contract.camera?.[k]===v),'UP2_WINDOW_CAMERA_BINDING');
 const frames=contract.frames.filter(f=>f.segment===selected.segment&&f.segmentFrame>=input.first&&f.segmentFrame<=input.last);
 check(frames.length===count,'UP2_WINDOW_FRAME_COUNT');
 const role=input.layerId.endsWith('_regional')?'regional':'overview',gridId=input.layerId+'_rgb';
 for(let i=0;i<frames.length;i++){
  const f=frames[i],provided=input.frames[i];check(f.segmentFrame===input.first+i&&f.part===Math.ceil(selected.segment/2)&&f.frame===(selected.segment%2===0?150:0)+f.segmentFrame,'UP2_WINDOW_FRAME_ASSOCIATION');
  check(f.sourceRole===role&&f.sourceGridId===gridId&&f.sourceCoverageTwoPixelGutter===true&&f.sourceSamplingAtLeast1x===true&&f.proposedLod?.blend===false&&f.proposedLod.overviewWeight===(role==='overview'?1:0)&&f.proposedLod.regionalWeight===(role==='regional'?1:0),'UP2_WINDOW_SOURCE_SCHEDULE_UNQUALIFIED');
  check(provided&&Object.keys(provided).sort().join(',')==='bounds,frame,part,segmentFrame'&&provided.part===f.part&&provided.frame===f.frame&&provided.segmentFrame===f.segmentFrame&&Array.isArray(provided.bounds)&&provided.bounds.length===4&&provided.bounds.every((v,j)=>Number.isFinite(v)&&v===f.bounds[j]),'UP2_WINDOW_BOUNDS_MISMATCH');
 }
 const bd=registration.binary.descriptor,descriptor=JSON.parse((await readPinnedServerFile(registration.binary.root,bd.localFile,bd)).toString('utf8'));
 const ep=descriptor.eligibilityReceipt;check(ep&&typeof ep.sourcePath==='string'&&path.isAbsolute(ep.sourcePath),'UP2_WINDOW_ELIGIBILITY_RECEIPT_REQUIRED');
 const eligibility=JSON.parse((await readPinnedServerFile(path.dirname(ep.sourcePath),path.basename(ep.sourcePath),ep)).toString('utf8'));
 check(eligibility.proposedCameraContractSha256===sha(b),'UP2_WINDOW_CAMERA_SOURCE_UNBOUND');
 const binary=await prepareRegisteredBinaryLayerV3({request:{schema:BINARY_REQUEST_SCHEMA,registrationId:'bound',layerId:input.layerId,camera:input.camera},registry:new Map([['bound',registration.binary]])});
 const identity={schema:FRAME_WINDOW_SCHEMA,registrationId:input.registrationId,windowId:selected.id,layerId:input.layerId,first:input.first,last:input.last,cameraContractSha256:sha(b),binaryQualificationSha256:binary.sourceQualificationSHA256,camera:input.camera,frames:input.frames};
 const qualification=sha(Buffer.from(JSON.stringify(identity)));if(expectedSourceQualificationSHA256!==undefined)check(typeof expectedSourceQualificationSHA256==='string'&&expectedSourceQualificationSHA256===qualification,'UP2_WINDOW_EXPECTED_QUALIFICATION_MISMATCH');
 const result={schema:'WORLD_ENGINE_PREPARED_PROPOSED_FRAME_WINDOW_V1',status:'CPU_WINDOW_PREPARATION_ONLY',sourceQualificationSHA256:qualification,dataIdentity:freeze(identity),frameCount:count,maximumRuntimeFrames:240,singleLayer:true,crossfadeSupported:false,layerTransition:'REQUIRES_EXPLICIT_EVICTION_BETWEEN_WINDOWS',historicalModeVerified:false,currentRuntimeCameraEquivalent:false,proposedExecution:false,renderAllowed:false,productionAdmitted:false,imageBuildAllowed:false,cacheReuseAllowed:false,executingCodeIdentity:'UNVERIFIED',binaryAssets:binary.dataIdentity.assets,binarySnapshotBytes:binary.snapshotBytes};
 Object.defineProperty(result,'binarySnapshot',{value:binary.binarySnapshot,enumerable:false});return Object.freeze(result);
}
