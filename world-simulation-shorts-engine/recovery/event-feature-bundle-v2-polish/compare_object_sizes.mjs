import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {compileFlowVisualProfile,FLOW_OBJECT_SCALE_CANDIDATES} from '../../web/map_infographic_v1/flow_visual_profile_v2.mjs';
import {openPolishRuntime,root,sha} from './polish_runtime.mjs';
const out=path.join(root,'evidence/object-size');await mkdir(out,{recursive:false});
const session=await openPolishRuntime({visualProfile:compileFlowVisualProfile({objectScale:1})});
const report={schema:1,status:'STARTED',basis:'Same native view, authored vector, exact original motion and presentation policy; scale candidates only',candidates:[]};
try{
 for(const scale of FLOW_OBJECT_SCALE_CANDIDATES){
  const profile=compileFlowVisualProfile({objectScale:scale});await session.page.evaluate(p=>window.flowProof.setProfile(p),profile);
  const candidate={scale,size:[52*scale,30*scale],frames:[]};
  for(const frame of [80,120,196]){
   const row=await session.page.evaluate(f=>window.flowProof.capture(f,{protect:true,png:true}),frame);
   const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
   assert.equal(sha(bytes),row.png_sha256);assert.equal(row.diagnostic.glError,0);
   const protection=row.diagnostic.flow.protection;assert.equal(protection.protectedChangedPixels,0);
   assert.equal(protection.markerChangedPixels,0);assert.equal(protection.outsideRoiChangedPixels,0);
   assert.equal(row.diagnostic.native.gpu.layout.some(x=>x.role==='SCENARIO_DISCLOSURE'),false);
   const file='scale-'+String(scale).replace('.','_')+'-'+frame+'.png';
   await writeFile(path.join(out,file),bytes,{flag:'wx'});
   candidate.frames.push({frame,file,sha256:sha(bytes),diagnostic:row.diagnostic});
  }
  report.candidates.push(candidate);console.log(JSON.stringify({phase:'OBJECT_SIZE_COMPARE',scale,size:candidate.size}));
 }
 assert.equal(session.errors.length,0);report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.message;throw error;}
finally{await writeFile(path.join(root,'evidence/OBJECT_SIZE_COMPARISON.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});await session.close();}
console.log(JSON.stringify({status:report.status,candidates:report.candidates.length}));
