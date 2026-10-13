/** Three actual native static samples. Technical checks do not declare visual admission. */
import assert from 'node:assert/strict';
import {mkdir,writeFile,rename} from 'node:fs/promises';
import path from 'node:path';
import {openReferenceRuntime,assertReferenceDiagnostic,root,sha} from './reference_runtime.mjs';

const out=path.join(root,'evidence/native_probe');
await mkdir(out,{recursive:true});
const save=async(file,bytes)=>{const pending=file+'.pending';await writeFile(pending,bytes);await rename(pending,file);};
let session,failure=null;
const samples=[];
try{
 session=await openReferenceRuntime({mode:'STATIC_VISUAL_PROBE'});
 const frames=[0,Math.floor((session.fixture.totalFrames-1)/2),session.fixture.totalFrames-1];
 assert.equal(session.info.cameraMotion.status,'PASS');
 assert.equal(session.info.cameraMotion.positionContinuous,true);
 assert.equal(session.info.cameraMotion.velocityContinuous,true);
 assert.equal(session.info.cameraMotion.fakeLockCount,0);
 assert.equal(session.info.evidence.factoryCount,1);
 assert.equal(session.info.evidence.arrivalReadinessForged,false);
 for(const frame of frames){
  const result=await session.page.evaluate(frame=>window.referenceProof.capture(frame,{protect:true,png:true}),frame),
   diagnostic=assertReferenceDiagnostic(result.diagnostic,{frame,protect:true});
  assert.equal(diagnostic.visualAdmission.productionEligible,false);
  const bytes=Buffer.from(result.png.split(',')[1],'base64'),name=String(frame).padStart(3,'0')+'.png';
  assert.equal(sha(bytes),result.png_sha256);
  await save(path.join(out,name),bytes);
  delete result.png;
  samples.push({frame,name,visual:'NOT_REVIEWED',technical:'PASS',pngSha256:result.png_sha256,
   sourceSignature:session.sourceSignature,...result});
  console.log(JSON.stringify({phase:'ACTUAL_NATIVE_STATIC_PROBE',frame,technical:'PASS',visual:'NOT_REVIEWED',
   glError:diagnostic.gpu.glError,protectedChangedPixels:diagnostic.protection.protectedChangedPixels}));
 }
 assert.equal(session.errors.length,0);
 await session.assertSourceUnchanged();
}catch(error){failure=error;
}finally{
 try{await session?.close();}catch(error){failure??=error;}
 const report={schema:'REFERENCE_NATIVE_STATIC_PROBE_V1',status:failure?'BLOCKED':'TECHNICAL_PASS',
  evidenceKind:'ACTUAL_NATIVE_STATIC_PROBE',mode:'STATIC_VISUAL_PROBE',output:[1080,1920],
  visual:'NOT_REVIEWED',visualAdmission:'NOT_GRANTED',productionEligible:false,
  fullVideoRendered:false,fullVisualReviewClaimed:false,referenceParityClaimed:false,
  actualCameraLocked:false,surveyAdmissionModified:false,sourceSignature:session?.sourceSignature??null,
  protectionSemantic:'BACKGROUND_MATERIAL_BEFORE_UNCHANGED_FOREGROUND',
  translucentEdgePixelIdentityClaimed:false,backgroundOutsideSafeAreaIsExpected:true,
  protectedBoundaryCounterScope:'OUTER_UNSHARED_NATIVE_BOUNDARY_ONLY',allNativeBoundaryPixelEqualityClaimed:false,
  sharedInternalBoundaryMaterialReplacementIsExpected:true,
  sourceBindings:session?.sourceBindings??[],cameraKeyframeBinding:session?.info.cameraKeyframeBinding??null,
  domainGeometryBinding:session?.info.domainGeometryBinding??null,boundaryKeyframeBinding:session?.info.boundaryKeyframeBinding??null,
  runtime:session?.info??null,samples,requiredTempOnlyFiles:0,
  next:failure?'REPAIR_CHANGED_EXTENSION_ONLY_THEN_RESUME_PROBE':'ROOT_VISUAL_REVIEW_REQUIRED_BEFORE_VISUAL_REFERENCE_ADMISSION',
  ...(failure?{error:failure.message,frame:failure.frame??null,failures:failure.failures??null,protection:failure.protection??null}:{}),
  userVideoReview:'REQUIRED',finalPromotion:false};
 await save(path.join(out,'REPORT.json'),JSON.stringify(report,null,2)+'\n');
}
if(failure)throw failure;
console.log(JSON.stringify({status:'TECHNICAL_PASS',samples:samples.length,visual:'NOT_REVIEWED',
 report:'evidence/native_probe/REPORT.json'}));
