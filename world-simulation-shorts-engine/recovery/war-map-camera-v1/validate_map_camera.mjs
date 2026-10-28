/** New WAR map/camera gate in the immutable existing image. CPU only. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {gzipSync,gunzipSync} from 'node:zlib';

const argv=process.argv.slice(2),arg=name=>{const i=argv.indexOf(name);return i<0?null:argv[i+1];};
const root=arg('--root'),inputPath=arg('--input'),scenePath=arg('--scene'),out=arg('--out'),privateRoot=arg('--private-root'),publicRoot=arg('--public-root');
const resume=argv.includes('--resume'),stateDir=arg('--state-dir')??(privateRoot&&path.join(privateRoot,'contract-state'));
if(![root,inputPath,scenePath,out,privateRoot,publicRoot,stateDir].every(x=>typeof x==='string'&&path.isAbsolute(x)))throw Error('ABSOLUTE_ROOT_INPUT_SCENE_OUT_PRIVATE_PUBLIC_PATHS_REQUIRED');
const EXPECTED_ROOT='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo';
const IMAGE_DIGEST='sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da';
const INPUT_SHA='b845bc57e2c47363608880320cc63ef4289b2528e2d7e4a0af6d4c9290ca1751';
const SCENE_SHA='cbdd4f42548294157ea5cb2728819220ef2b089f81713352f7e374083b663d95';
const REGION_SHA='4aea5991c945ee2091644e1f782e024c1a0567ac10b0afa6bc7c54893bbec94e';
const PRESENTATION_SHA='8773a5651649eb47dc080f21c7718a7b2e126576626a0bdd22c22de7ef62c70b';
const regionModule=path.join(root,'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/region_source_vulkan.generated.mjs');
const presentationModule=path.join(root,'world-simulation-shorts-engine/recovery/universal-presentation-v2/presentation_plan.mjs');
const sha=b=>createHash('sha256').update(b).digest('hex'),json=v=>JSON.stringify(v,null,2)+'\n';
const check=(v,code,detail)=>{if(!v)throw Object.assign(Error(code),{code,detail});};
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),contains=(a,b)=>a[0]<=b[0]+1e-10&&a[1]<=b[1]+1e-10&&a[2]>=b[2]-1e-10&&a[3]>=b[3]-1e-10;
fs.mkdirSync(out,{recursive:true});
const resultFile=path.join(out,'RESULT.json');
if(fs.existsSync(resultFile)&&!resume)throw Error('EXISTING_EXECUTION_DO_NOT_RERUN_USE_REVIEWED_RESUME');
let result=fs.existsSync(resultFile)?JSON.parse(fs.readFileSync(resultFile,'utf8')):null;
if(result?.status==='PASS')throw Error('COMPLETED_MAP_CAMERA_PASS_MUST_BE_SKIPPED');
const log=row=>{const s=JSON.stringify(row)+'\n';fs.appendFileSync(path.join(out,'stdout.log'),s);process.stdout.write(s);};
const write=(name,value)=>{const raw=typeof value==='string'?value:json(value);fs.writeFileSync(path.join(out,name),raw);return{file:name,sha256:sha(raw),bytes:Buffer.byteLength(raw)};};
const save=()=>write('RESULT.json',result);
if(!result){
 fs.writeFileSync(path.join(out,'stdout.log'),'');fs.writeFileSync(path.join(out,'stderr.log'),'');
 result={schema:'WORLD_ENGINE_WAR_MAP_CAMERA_RESULT_V1',status:'RUNNING',createdAt:new Date().toISOString(),imageDigest:IMAGE_DIGEST,inputSHA256:INPUT_SHA,compiledSceneSHA256:SCENE_SHA,steps:{},scope:{
  firstIncompleteGate:'WAR_MAP_CAMERA',existingPassSkipped:['G0','G1','G2','WAR_SCENE_CONTRACT'],existingPassInvalidated:[],
  explicitOldSceneValidatorCalls:0,explicitOldEngineCompilerCalls:0,areaFrameTestsRerun:0,rendererModified:false,imageRebuilt:false,
  gpuExecuted:false,renderedFrames:0,browserStarted:false,networkRequired:false,nativeFactoryProjection:'NOT_RUN_NOT_CLAIMED',
  internalCalls:'Existing resolveRegionPlan internally invokes qualifyRegion; compilePresentationCameraPlan internally invokes validatePresentation and compileExistingEnginePlan. These are unchanged required API internals, not separately rerun prior suites.',
  cameraProof:'CPU existing camera plan, regional geographic-to-pixel projection and actual source/crop coverage; no GPU visual quality claim.'}};
 save();
}
let input,scene,regionAPI,presentationAPI,sourceText;
const failInfo=error=>({name:error.name,code:error.code??error.message,message:error.message,stack:error.stack,
 detail:error.detail??null,engineReturnedIssues:error.engineReturnedIssues??null,
 sourceCodeOccurrences:sourceText&&typeof error.message==='string'&&/^[A-Z][A-Z0-9_]+$/.test(error.message)?sourceText.split('\n').flatMap((s,i)=>s.includes(error.message)?[{file:regionModule,line:i+1}]:[]):[]});
const saveCache=(name,value)=>{
 const raw=Buffer.from(json(value)),compressed=gzipSync(raw,{level:9}),file=name+'.json.gz';
 fs.writeFileSync(path.join(stateDir,file),compressed,{mode:0o600});
 return{file,sha256:sha(compressed),uncompressedSHA256:sha(raw),bytes:compressed.length,uncompressedBytes:raw.length};
};
const restoreCache=record=>{
 check(record&&typeof record.file==='string','RESUME_STATE_RECEIPT_REQUIRED');
 const bytes=fs.readFileSync(path.join(stateDir,record.file));check(sha(bytes)===record.sha256,'RESUME_STATE_COMPRESSED_SHA_MISMATCH');
 const raw=gunzipSync(bytes);check(sha(raw)===record.uncompressedSHA256,'RESUME_STATE_SHA_MISMATCH');return JSON.parse(raw);
};
const step=async(name,fn)=>{
 if(result.steps[name]?.status==='PASS'){log({event:'SKIP_EXISTING_NEW_GATE_STEP_PASS',step:name});return restoreCache(result.steps[name].privateState);}
 const attempt=(result.steps[name]?.attempt??0)+1,startedAt=new Date().toISOString();log({event:'STEP_START',step:name,attempt});
 try{
  const {value,summary,evidence={}}=await fn(),artifacts=[];
  for(const [file,content]of Object.entries(evidence))artifacts.push(write(file,content));
  const privateState=saveCache(name+'_'+attempt,value),record={step:name,status:'PASS',attempt,startedAt,completedAt:new Date().toISOString(),summary,artifacts,privateState};
  const report='STEP_'+name+'_'+attempt+'.json';write(report,record);result.steps[name]={...record,report};result.status='RUNNING';delete result.failure;save();
  log({event:'STEP_PASS',step:name,summary});return value;
 }catch(error){
  const failure=failInfo(error),record={step:name,status:'FAIL',attempt,startedAt,completedAt:new Date().toISOString(),error:failure},report='STEP_'+name+'_'+attempt+'.json';
  write(report,record);result.steps[name]={...record,report};result.status='BLOCKED';result.failure={step:name,...failure};save();
  fs.appendFileSync(path.join(out,'stderr.log'),String(error.stack??error)+'\n');process.stderr.write(String(error.stack??error)+'\n');log({event:'STEP_FAIL',step:name,error:failure});throw error;
 }
};
try{
 check(root===EXPECTED_ROOT,'EXACT_INSTALLED_IMAGE_ROOT_REQUIRED');
 const inputBytes=fs.readFileSync(inputPath),sceneBytes=fs.readFileSync(scenePath),regionBytes=fs.readFileSync(regionModule),presentationBytes=fs.readFileSync(presentationModule);
 check(sha(inputBytes)===INPUT_SHA,'PINNED_WAR_INPUT_SHA_MISMATCH');check(sha(sceneBytes)===SCENE_SHA,'REUSED_COMPILED_SCENE_SHA_MISMATCH');
 check(sha(regionBytes)===REGION_SHA,'PINNED_GENERATED_REGION_MODULE_SHA_MISMATCH');check(sha(presentationBytes)===PRESENTATION_SHA,'PINNED_PRESENTATION_MODULE_SHA_MISMATCH');
 check(result.inputSHA256===INPUT_SHA&&result.compiledSceneSHA256===SCENE_SHA&&result.imageDigest===IMAGE_DIGEST,'RESUME_INPUT_OR_IMAGE_CHANGED');
 input=JSON.parse(inputBytes);scene=JSON.parse(sceneBytes);sourceText=regionBytes.toString('utf8');
 check(stateDir.startsWith(privateRoot+path.sep),'STATE_MUST_REMAIN_INSIDE_PRIVATE_ROOT');fs.mkdirSync(stateDir,{recursive:true,mode:0o700});
 write('RUN_CONTEXT.json',{schema:'WORLD_ENGINE_WAR_MAP_CAMERA_CONTEXT_V1',nodeVersion:process.version,uid:process.getuid(),imageDigest:IMAGE_DIGEST,
  imageIdentityAuthority:'External runner docker pull/inspect by exact digest; see IMAGE_IDENTITY.json',installedRoot:root,inputSHA256:sha(inputBytes),compiledSceneSHA256:sha(sceneBytes),
  harnessSHA256:sha(fs.readFileSync(fileURLToPath(import.meta.url))),modules:[{path:regionModule,sha256:sha(regionBytes)},{path:presentationModule,sha256:sha(presentationBytes)}],
  privateStateDirectory:stateDir,privateWorkspaceRoot:privateRoot,publicExportRoot:publicRoot,resume,oldValidationRerun:false});
 regionAPI=await import(pathToFileURL(regionModule).href);presentationAPI=await import(pathToFileURL(presentationModule).href);
 log({event:'EXECUTION_START',node:process.version,inputSHA256:INPUT_SHA,imageDigest:IMAGE_DIGEST,resume});
 const qualified=await step('QUALIFY_REGION',async()=>{
  const value=await regionAPI.qualifyRegion({region:input.region,facts:input.data.scenes[0].facts});
  write('QUALIFY_REGION_RETURN_'+((result.steps.QUALIFY_REGION?.attempt??0)+1)+'.json',value);
  if(value.status!=='PASS')throw Object.assign(Error(value.issues?.[0]?.code??'QUALIFY_REGION_NOT_PASS'),{code:value.issues?.[0]?.code,engineReturnedIssues:value.issues});
  check(value.regionEvidence.sourceBytesActuallyVerified===true,'ACTUAL_REGION_SOURCE_BYTES_REQUIRED');
  return{value,summary:{status:value.status,phase:value.phase,regionGateSHA256:value.regionGateSHA256,contextCountryId:value.regionEvidence.contextCountryId,
   sourceId:value.regionEvidence.sourceId,sourceSHA256:value.regionEvidence.sourceSHA256,gisSHA256:value.regionEvidence.gisSHA256,fittedBounds:value.regionEvidence.fittedBounds,
   sourceBytesActuallyVerified:true,trajectoryCoverageRequiredBeforeStart:true},evidence:{'REGION_QUALIFICATION.json':value}};
 });
 const resolved=await step('RESOLVE_REGION_PLAN',async()=>{
  const value=await regionAPI.resolveRegionPlan({scene,region:input.region});
  check(value.regionGateSHA256===qualified.regionGateSHA256,'REGION_QUALIFICATION_CHANGED');
  return{value,summary:{status:'PASS',regionGateSHA256:value.regionGateSHA256,sourceCatalogSHA256:value.sourceCatalogSHA256,
   nativeProjection:value.nativePlan.framing.projection,approvedBounds:value.nativePlan.framing.bounds,nativePrimary:value.nativePlan.primary,
   baseCameraDirector:value.baseCameraPlan.directorVersion,baseCameraFrames:value.baseCameraPlan.totalFrames},evidence:{'RESOLVED_REGION_SUMMARY.json':{
    region:value.region,regionEvidence:value.regionEvidence,nativeFraming:value.nativePlan.framing,nativeScale:value.nativePlan.scale,
    nativeSafeArea:value.nativePlan.layout.safe,baseCameraDirector:value.baseCameraPlan.directorVersion,baseCameraFrames:value.baseCameraPlan.totalFrames}}};
 });
 const camera=await step('COMPILE_PRESENTATION_CAMERA',async()=>{
  const value=presentationAPI.compilePresentationCameraPlan({scene,region:resolved.region,nativePlan:resolved.nativePlan,baseCameraPlan:resolved.baseCameraPlan,presentation:input.presentation});
  check(value.cpuFrameBounds.length===180&&value.track.totalFrames===180,'CAMERA_180_FRAMES_REQUIRED');
  check(same(value.keyframes,input.presentation.camera.keyframes),'CAMERA_KEYFRAME_INPUT_CHANGED');
  check(value.sameAspect===true&&value.actualMovingCameraLockForged===false&&value.sourceGeometryMutated===false,'CAMERA_OWNERSHIP_CONTRACT');
  return{value,summary:{status:'PASS',frames:value.cpuFrameBounds.length,keyframeFrames:value.keyframes.map(k=>k.frame),coverageBounds:value.coverageBounds,
   approvedClosestBounds:value.closestBounds,analysisSourceFrame:value.analysisSourceFrame,modelCameraLocked:value.analysisCamera.cameraLocked,
   sameAspect:value.sameAspect,movingCameraOwner:value.movingCameraOwner,sourceGeometryMutated:false},evidence:{'CAMERA_PLAN_SUMMARY.json':{
    mode:value.mode,keyframes:value.keyframes,cpuFrameBounds:value.cpuFrameBounds,coverageBounds:value.coverageBounds,closestBounds:value.closestBounds,
    analysisBounds:value.analysisBounds,analysisSourceFrame:value.analysisSourceFrame,modelTimingOwner:value.modelTimingOwner,movingCameraOwner:value.movingCameraOwner,
    sameAspect:value.sameAspect,actualMovingCameraLockForged:value.actualMovingCameraLockForged,sourceGeometryMutated:value.sourceGeometryMutated,
    trackAdmission:value.track.admission,nativeFactoryProjection:'NOT_RUN_NOT_CLAIMED'}}};
 });
 const prepared=await step('PREPARE_REGION_TERRAIN',async()=>{
  const value=await regionAPI.prepareRegionTerrain({regionPlan:resolved,bounds:camera.coverageBounds,outputRoot:path.join(privateRoot,'region-cache'),privateWorkspaceRoot:privateRoot,publicExportRoot:publicRoot});
  check(same(value.nativePlan.framing.bounds,camera.closestBounds),'CLOSEST_APPROVED_EXTENT_CHANGED');
  check(value.regionEvidence.phase==='FULL_CAMERA_ENVELOPE'&&value.regionEvidence.trajectoryCoverageRequiredBeforeStart===false,'FULL_CAMERA_SOURCE_COVERAGE_REQUIRED');
  return{value,summary:{status:'PASS',fullCoverageSHA256:value.fullCoverageSHA256,sourceId:value.regionEvidence.sourceId,
   sourceSHA256:value.regionEvidence.sourceSHA256,cropSHA256:value.regionEvidence.cropSHA256,cropBounds:value.regionEvidence.actualCropBounds,
   requiredBounds:value.regionEvidence.sourceRequiredBounds,gutterPixels:value.regionEvidence.minimumSourceGutterPixels,
   rasterCoverage:value.nativePlan.scale.lod.rasterCoverage,resampling:value.regionEvidence.resampling},evidence:{'FULL_SOURCE_COVERAGE.json':{
    fullCoverageSHA256:value.fullCoverageSHA256,regionEvidence:value.regionEvidence,sourceBindings:value.sourceBindings,sourceStyle:value.sourceStyle,
    nativeRasterCoverage:value.nativePlan.scale.lod.rasterCoverage,terrainPath:value.terrainPath,cacheRecordPath:value.cacheRecordPath}}};
 });
 const verified=await step('VERIFY_SOURCE_CROP',async()=>{
  const value=await regionAPI.verifyRegionQualification({prepared,privateWorkspaceRoot:privateRoot,publicExportRoot:publicRoot});
  write('VERIFY_SOURCE_RETURN_'+((result.steps.VERIFY_SOURCE_CROP?.attempt??0)+1)+'.json',value);
  if(value.status!=='PASS')throw Object.assign(Error(value.issues?.[0]?.code??'SOURCE_CROP_VERIFICATION_NOT_PASS'),{engineReturnedIssues:value.issues});
  check(value.actualSourceAndCropBytesVerified===true&&value.trajectoryCoverageRequiredBeforeStart===false,'ACTUAL_SOURCE_CROP_VERIFICATION_REQUIRED');
  return{value,summary:value,evidence:{'SOURCE_CROP_VERIFICATION.json':value}};
 });
 await step('CAMERA_PROJECTION_180',async()=>{
  const points=[];
  const visit=(v,id)=>{if(Array.isArray(v)&&v.length===2&&v.every(Number.isFinite))points.push({geometryId:id,geographic:[...v]});else if(Array.isArray(v))v.forEach(x=>visit(x,id));};
  for(const row of scene.geometries)visit(row.geometry.coordinates,row.id);
  check(points.length>0,'SUPPLIED_GEOGRAPHIC_POINTS_REQUIRED');
  const crop=prepared.regionEvidence.actualCropBounds,source=prepared.regionEvidence.sourceBounds,safe=prepared.nativePlan.layout.safe,frames=[];
  check(Array.isArray(safe)&&safe.length===4&&safe.every(Number.isFinite),'EXISTING_NATIVE_SAFE_AREA_REQUIRED');
  check(contains(crop,camera.coverageBounds)&&contains(crop,resolved.nativePlan.framing.bounds),'CROP_MUST_COVER_CAMERA_AND_INITIALIZATION');
  check(contains(source,crop),'CROP_OUTSIDE_ACTUAL_SOURCE');
  for(let frame=0;frame<180;frame++){
   const b=camera.cpuFrameBounds[frame];check(Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3],'CAMERA_NONFINITE_OR_EMPTY_BOUNDS_'+frame);
   check(contains(crop,b)&&contains(source,b),'FRAME_OUTSIDE_VERIFIED_SOURCE_'+frame);
   const pixels=points.map(p=>{
    const pixel=presentationAPI.projectBounds(b,p.geographic),inverse=presentationAPI.unprojectBounds(b,pixel);
    check(pixel.every(Number.isFinite)&&inverse.every(Number.isFinite),'CAMERA_PROJECTION_NONFINITE_'+frame);
    check(Math.max(...inverse.map((v,i)=>Math.abs(v-p.geographic[i])))<1e-9,'CAMERA_PROJECTION_ROUNDTRIP_'+frame);
    check(pixel[0]>=-1e-6&&pixel[0]<=1080+1e-6&&pixel[1]>=-1e-6&&pixel[1]<=1920+1e-6,'SUPPLIED_WAR_GEOMETRY_OUTSIDE_VIEWPORT_'+frame);
    check(pixel[0]>=safe[0]-1e-6&&pixel[0]<=safe[2]+1e-6&&pixel[1]>=safe[1]-1e-6&&pixel[1]<=safe[3]+1e-6,'SUPPLIED_WAR_GEOMETRY_OUTSIDE_NATIVE_SAFE_AREA_'+frame);
    return pixel;
   });
   const key=input.presentation.camera.keyframes.find(k=>k.frame===frame);
   if(key)check(Math.max(Math.abs((b[0]+b[2])/2-key.center[0]),Math.abs((b[1]+b[3])/2-key.center[1]))<1e-9,'CAMERA_KEYFRAME_CENTER_MISMATCH_'+frame);
   frames.push({frame,bounds:b,projectedVertexCount:pixels.length,projectedExtent:[Math.min(...pixels.map(p=>p[0])),Math.min(...pixels.map(p=>p[1])),Math.max(...pixels.map(p=>p[0])),Math.max(...pixels.map(p=>p[1]))],
    allSuppliedGeometryVerticesInsideViewport:true,allSuppliedGeometryVerticesInsideNativeSafeArea:true,sourceCovered:true,projectionRoundtripMaxErrorLessThan:1e-9,keyframe:key??null});
  }
  const value={schema:'WORLD_ENGINE_WAR_CAMERA_PROJECTION_EVIDENCE_V1',status:'PASS',frames,geographicPoints:points,output:[1080,1920],fps:30,rangeInclusive:[0,179],
   cameraBoundsOwner:'compilePresentationCameraPlan.cpuFrameBounds (180 actual reference-camera evaluations inside existing compiler)',
   projectionOwner:'Existing presentation_plan.projectBounds/unprojectBounds',nativeSafeArea:safe,nativeFactoryProjection:'NOT_RUN_NOT_CLAIMED',
   trackAdmission:camera.track.admission,sourceVerification:verified,sourceCropBounds:crop,sourceBounds:source,renderedFrames:0};
  return{value,summary:{status:'PASS',frames:180,geographicVerticesPerFrame:points.length,allFramesSourceCovered:true,allSuppliedGeometryVerticesInsideViewport:true,
   finiteProjectionAndRoundtrip:true,renderedFrames:0},evidence:{'FRAME_PROJECTION_EVIDENCE.json':value}};
 });
 result.status='PASS';result.completedAt=new Date().toISOString();result.checks={actualQualifyRegion:'PASS',actualResolveRegionPlan:'PASS',actualPresentationCameraPlan:'PASS',
  cameraProjection180Frames:'PASS',actualSourceAndCropCoverage:'PASS',fixedImageAndInput:'PASS',gpuExecuted:false,githubBackup:'PENDING_RUNNER_PUBLICATION'};
 save();log({event:'EXECUTION_PASS',checks:result.checks});
}catch(error){
 if(result.status!=='BLOCKED'){result.status='BLOCKED';result.failure={step:'CONTEXT_OR_IMPORT',...failInfo(error)};save();fs.appendFileSync(path.join(out,'stderr.log'),String(error.stack??error)+'\n');process.stderr.write(String(error.stack??error)+'\n');}
 process.exitCode=1;
}
