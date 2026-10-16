import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateReferenceSourceProfile,sourceGradeIsNeutral,gradeSourceRgb,SOURCE_GRADE_FRAGMENT} from '../source_grade_core.mjs';
import {createNativeDomainBinding,describeNativeDomainBinding,publishNativeDomainCoverage,getNativeDomainCoverage,clearNativeDomainCoverage}
 from '../native_domain_coverage.mjs';
const close=(a,b)=>a.forEach((v,i)=>assert.ok(Math.abs(v-b[i])<1e-12));
const tint=[.13,.35,.41],rgb=[.16,.21,.24],selected={enabled:true,terrainLocalContrast:1.2,landExposure:1.04,oceanExposure:1.2,oceanTealMix:.12};
const geometry=(id,left,right)=>({id,geometry_type:'Polygon',coordinates:[[[left,0],[right,0],[right,1],[left,1],[left,0]]]});
function bindingInput(){
 const geometries=[geometry('ROLE_A',0,1),geometry('ROLE_B',1,2),geometry('CONTEXT',2,3)];
 return {primary:'ROLE_A',secondary:['ROLE_B'],geometries,
  domain:geometries.slice(0,2).map(g=>({id:g.id,geometry:{type:g.geometry_type,coordinates:structuredClone(g.coordinates)}})),eventStartFrame:10};
}
const coverage=()=>new Uint8Array([255,0,255,255,255,255,0,255,255,0,0,255,128,64,64,255]);
test('source profile is generic, bounded, explicit and disabled by default',()=>{
 assert.equal(validateReferenceSourceProfile().enabled,false);assert.equal(validateReferenceSourceProfile().registerDomainCoverage,false);
 for(const input of [{enabled:'yes'},{oceanExposure:2},{terrainLocalContrast:.9},{screenFeatherPixels:1},
  {country:'TEST'},{fakeHeight:2},{ignoreNoData:true}])assert.throws(()=>validateReferenceSourceProfile(input));
 assert.equal(sourceGradeIsNeutral({enabled:false}),true);
});
test('disabled and neutral source grading preserve every original RGB value exactly',()=>{
 for(const color of [[1,1,1],[0,0,0],rgb]){
  assert.deepEqual(gradeSourceRgb(color,{coverage:.3}),color);
  assert.deepEqual(gradeSourceRgb(color,{coverage:.3,landSupport:1,oceanSupport:1},
   {enabled:true,terrainLocalContrast:1,landExposure:1,oceanExposure:1,oceanTealMix:0}),color);
 }
});
test('zero actual source support preserves full white and baseline bytes without clipping',()=>{
 assert.deepEqual(gradeSourceRgb([1,1,1],{coverage:.2,landSupport:0,oceanSupport:0},selected),[1,1,1]);
 assert.deepEqual(gradeSourceRgb(rgb,{coverage:.2,landSupport:0,oceanSupport:0},selected),rgb);
 // Negative-depth availability over native land grants no ocean grade.
 assert.deepEqual(gradeSourceRgb([1,1,1],{coverage:1,landSupport:0,oceanSupport:1},selected),[1,1,1]);
});
test('NoData/support and native land/ocean gates remain independent, fractional and finite',()=>{
 const all=gradeSourceRgb(rgb,{coverage:0,oceanSupport:1,oceanTint:tint},selected),
  half=gradeSourceRgb(rgb,{coverage:0,oceanSupport:.5,oceanTint:tint},selected);
 close(half,rgb.map((v,i)=>(v+all[i])/2));
 assert.deepEqual(gradeSourceRgb(rgb,{coverage:0,landSupport:1,oceanSupport:0},selected),rgb);
 assert.throws(()=>gradeSourceRgb(rgb,{coverage:.5,landSupport:NaN,oceanSupport:0},selected));
 assert.throws(()=>gradeSourceRgb(rgb,{coverage:2},selected));
});
test('land contrast never borrows a sea or unsupported neighbour at a coast/source edge',()=>{
 const args={coverage:1,landSupport:1,localAverage:.01,oceanTint:tint},contrast={...selected,landExposure:1};
 const neutral=gradeSourceRgb(rgb,args,{...contrast,terrainLocalContrast:1});
 close(gradeSourceRgb(rgb,{...args,interiorLand:false},contrast),neutral);
 close(gradeSourceRgb(rgb,{...args,interiorSupport:false},contrast),neutral);
 assert.ok(gradeSourceRgb(rgb,args,contrast).some((value,i)=>value>neutral[i]));
});
test('ocean exposure/teal preserves actual depth tone order and never mutates source RGB',()=>{
 const before=[...rgb],dark=gradeSourceRgb(rgb,{coverage:0,oceanSupport:1,oceanTint:tint},selected),
  bright=gradeSourceRgb(rgb.map(x=>x*1.5),{coverage:0,oceanSupport:1,oceanTint:tint},selected);
 assert.ok(bright.every((v,i)=>v>dark[i]));close(bright,dark.map(x=>x*1.5));assert.deepEqual(rgb,before);
});
test('domain token is computed from exact role IDs, geometry types and every coordinate',async()=>{
 const input=bindingInput(),before=structuredClone(input),handle=await createNativeDomainBinding(input),meta=describeNativeDomainBinding(handle);
 assert.match(meta.domainSHA256,/^[a-f0-9]{64}$/);assert.match(meta.sourceGeometrySHA256,/^[a-f0-9]{64}$/);
 assert.equal(meta.geometryCoordinatesExactlyMatched,true);assert.deepEqual(meta.coverageChannels,{land:0,secondary:1,primary:2});
 assert.deepEqual(input,before);assert.throws(()=>describeNativeDomainBinding({domainSHA256:handle.domainSHA256}));
 const wrong=bindingInput();wrong.domain[1].geometry.coordinates[0][0][0]+=.1;
 await assert.rejects(createNativeDomainBinding(wrong),/COORDINATE_MISMATCH/);
 const extra=bindingInput();extra.secondary.push('CONTEXT');await assert.rejects(createNativeDomainBinding(extra),/ID_MISMATCH/);
});
test('same-frame native G+B union excludes unrelated land and preserves fractional role coverage',async()=>{
 const canvas={},token=await createNativeDomainBinding(bindingInput()),bytes=coverage(),before=bytes.slice(),bounds=[0,0,2,2];
 const record=publishNativeDomainCoverage(canvas,token,{coverage:bytes,bounds,frame:3,width:2,height:2});
 assert.equal(record.frame,13);assert.equal(record.nativeFrame,3);
 const read=getNativeDomainCoverage(canvas,{frame:13,domainSHA256:token.domainSHA256,bounds});
 assert.deepEqual([...read.domainCoverage],[255,255,0,128]);assert.equal(read.rowZero,'SOUTH');
 assert.equal(read.nativeCoastCoverageFiltered,false);assert.equal(read.sourceColourThresholdUsed,false);
 assert.deepEqual(bytes,before);read.domainCoverage.fill(0);
 assert.deepEqual([...getNativeDomainCoverage(canvas,{frame:13,domainSHA256:token.domainSHA256}).domainCoverage],[255,255,0,128]);
});
test('stale frame, wrong domain/bounds and impossible native role/land masks fail closed',async()=>{
 const canvas={},token=await createNativeDomainBinding(bindingInput()),args={coverage:coverage(),bounds:[0,0,2,2],frame:0,width:2,height:2};
 publishNativeDomainCoverage(canvas,token,args);
 assert.throws(()=>getNativeDomainCoverage(canvas,{frame:0,domainSHA256:token.domainSHA256}),/FRAME_MISMATCH/);
 assert.throws(()=>getNativeDomainCoverage(canvas,{frame:10,domainSHA256:'0'.repeat(64)}),/SHA_MISMATCH/);
 assert.throws(()=>getNativeDomainCoverage(canvas,{frame:10,domainSHA256:token.domainSHA256,bounds:[0,0,3,3]}),/BOUNDS_MISMATCH/);
 const corrupt=coverage();corrupt[0]=0;assert.throws(()=>publishNativeDomainCoverage(canvas,token,{...args,coverage:corrupt}),/COVERAGE_INCONSISTENT/);
 clearNativeDomainCoverage(canvas);assert.throws(()=>getNativeDomainCoverage(canvas,{frame:10,domainSHA256:token.domainSHA256}),/UNAVAILABLE/);
});
test('shader clips candidates before support mix and protects coast AND unsupported contrast neighbours',()=>{
 assert.match(SOURCE_GRADE_FRAGMENT,/supportedInterior>.999/);assert.match(SOURCE_GRADE_FRAGMENT,/interior>.999/);
 assert.match(SOURCE_GRADE_FRAGMENT,/land\*support.r\*\(gradedLand-source\)/);
 assert.match(SOURCE_GRADE_FRAGMENT,/\(1.-land\)\*support.g\*\(gradedOcean-source\)/);
 assert.match(SOURCE_GRADE_FRAGMENT,/clamp\(graded,0.,1.\)/);
 assert.doesNotMatch(SOURCE_GRADE_FRAGMENT,/clamp\(graded,0.,.98\)|depthTexture|heightTexture|coastGlow/);
});
test('new wrapper reuses original F pass and one optional additional authenticated upload pack',async()=>{
 const source=await readFile(new URL('../reference_source_material.mjs',import.meta.url),'utf8'),
 pass=await readFile(new URL('../source_grade_pass.mjs',import.meta.url),'utf8');
 assert.match(source,/from '\/quality\/quality_material.mjs\?baseline'/);
 assert.match(source,/if\(!selected.enabled&&!selected.registerDomainCoverage\)return original/);
 assert.equal((source.match(/createUploadTextures\(/g)??[]).length,1);
 assert.match(pass,/createSupportDistanceTextures\(gl,uploads.resources/);
 assert.match(pass,/additionalUploadPacks:1/);assert.match(pass,/budget=256\*1024\*1024/);
 assert.match(pass,/baseline.outputTexture,'actualSource'/);assert.match(pass,/get outputTexture\(\).*return snapshotTexture/);
 assert.match(pass,/snapshotFormat:'RGB8'/);assert.match(pass,/sourceMaterialBeforeTerritory:true/);
 assert.match(pass,/gl.RASTERIZER_DISCARD,gl.DITHER\]\)gl.disable\(cap\)/);
 assert.match(pass,/const native=baseline.draw\(args\),state=capture\(gl\)/);assert.match(pass,/restore\(gl,state\)/);
 assert.doesNotMatch(source+pass,/fetch\(|ffmpeg|controls.boundaryLatitudes\s*=|camera.position/);
});
