/** Actual native static probes; technical PASS cannot grant visual parity. */
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile,rename,stat} from 'node:fs/promises';
import path from 'node:path';
import {openQualityRuntime,assertQualityDiagnostic,root,sha} from './reference_runtime.mjs';
const args=process.argv.slice(2);
if(args.length>1||args.some(arg=>!/^--output=[A-Za-z0-9_/-]+$/.test(arg)))throw Error('QUALITY_PROBE_UNKNOWN_ARGUMENT');
const suffix=args[0]?.slice('--output='.length)??'evidence/native_probe';
if(suffix.split('/').some(part=>part==='..'||part==='.')||path.isAbsolute(suffix))throw Error('QUALITY_PROBE_OUTPUT_CONTAINMENT_REQUIRED');
const out=path.join(root,suffix);await mkdir(out,{recursive:true});
const exists=async file=>stat(file).then(()=>true,()=>false);
const save=async(file,bytes)=>{
 if(await exists(file)){assert.deepEqual(await readFile(file),Buffer.from(bytes),'PRESERVE_EXISTING_NATIVE_PROBE '+file);return;}
 const pending=file+'.pending';await writeFile(pending,bytes);await rename(pending,file);
};
let session,failure=null;const samples=[];
try{
 session=await openQualityRuntime({mode:'STATIC_VISUAL_PROBE'});
 assert.equal(session.info.cameraMotion.status,'PASS');assert.equal(session.info.cameraMotion.positionContinuous,true);
 assert.equal(session.info.cameraMotion.velocityContinuous,true);assert.equal(session.info.cameraMotion.fakeLockCount,0);
 for(const frame of [0,74,149]){
  const result=await session.page.evaluate(async frame=>await window.referenceProof.capture(frame,{png:true}),frame);
  const d=assertQualityDiagnostic(result.diagnostic,{frame});
  const bytes=Buffer.from(result.png.split(',')[1],'base64'),name=String(frame).padStart(3,'0')+'.png';
  assert.equal(sha(bytes),result.png_sha256);assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  await save(path.join(out,name),bytes);delete result.png;
  samples.push({frame,name,visual:'NOT_REVIEWED',technical:'PASS',pngSha256:result.png_sha256,
   sourceSignature:session.sourceSignature,...result});
  console.log(JSON.stringify({phase:'QUALITY_ACTUAL_NATIVE_STATIC_PROBE',frame,technical:'PASS',visual:'NOT_REVIEWED',
   glError:d.gpu.glError,cornerSamplesInside:d.presentation.cornerSamplesInside,
   criticalCollisions:Array.isArray(d.units.criticalCollisions)?d.units.criticalCollisions.length:d.units.criticalCollisions}));
 }
 assert.equal(session.errors.length,0);await session.assertSourceUnchanged();
}catch(error){failure=error;
}finally{
 try{await session?.close();}catch(error){failure??=error;}
 const report={schema:'MAP_VISUAL_NATIVE_STATIC_PROBE_V3',status:failure?'BLOCKED':'TECHNICAL_PASS',
  evidenceKind:'ACTUAL_NATIVE_STATIC_PROBE',mode:'STATIC_VISUAL_PROBE',output:[1080,1920],visual:'NOT_REVIEWED',
  visualAdmission:'NOT_GRANTED',productionEligible:false,fullVideoRendered:false,fullVisualReviewClaimed:false,
  referenceParityClaimed:false,actualCameraLocked:false,surveyAdmissionModified:false,
  sourceSignature:session?.sourceSignature??null,sourceBindings:session?.sourceBindings??[],
  cameraKeyframeBinding:session?.info.cameraKeyframeBinding??null,
  domainGeometryBinding:session?.info.domainGeometryBinding??null,boundaryKeyframeBinding:session?.info.boundaryKeyframeBinding??null,
  runtime:session?.info??null,samples,requiredTempOnlyFiles:0,
  optionalNativeForegroundExcludedByNewScene:true,oldNativeForegroundPixelIdentityClaimed:false,
  next:failure?'REPAIR_NEW_EXTENSION_ONLY_THEN_RESUME_PROBE':'ACTUAL_VISUAL_REVIEW_REQUIRED_BEFORE_RENDER_ADMISSION',
  ...(failure?{error:failure.message}:{}),userVideoReview:'REQUIRED',finalPromotion:false};
 const reportFile=path.join(out,'REPORT.json'),pending=reportFile+'.pending';
 await writeFile(pending,JSON.stringify(report,null,2)+'\n');await rename(pending,reportFile);
}
if(failure)throw failure;
console.log(JSON.stringify({status:'TECHNICAL_PASS',samples:samples.length,visual:'NOT_REVIEWED',report:suffix+'/REPORT.json'}));
