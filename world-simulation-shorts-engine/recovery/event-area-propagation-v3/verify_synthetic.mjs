import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {openAreaRuntime,root,json} from './area_runtime.mjs';
import {evaluateAreaFrame} from '../../web/map_infographic_v1/area_core_v3.mjs';
const evidence={schema:1,status:'STARTED',productionEligible:false,physicalSimulation:false,
 evidenceScope:'AUTHORED_CPU_AND_ACTUAL_NATIVE_GPU_SYNTHETIC_NOT_PRODUCTION_ADMISSION',A:null,B:null,C:null};
await mkdir(path.join(root,'evidence/synthetic'),{recursive:true});
try{
 for(const key of ['a','b','c']){
  const fixtureFile=path.join(root,'fixtures/synthetic-'+key+'.json'),fixture=await json(fixtureFile);
  const original=JSON.stringify(fixture.areaPlan),controls=[];
  for(let frame=0;frame<fixture.areaPlan.totalFrames;frame++){
   const c=evaluateAreaFrame(fixture.areaPlan,frame);assert.equal(c.physicalSimulation,false);controls.push(c);
  }
  assert.equal(JSON.stringify(fixture.areaPlan),original);
  assert.deepEqual(evaluateAreaFrame(fixture.areaPlan,0),controls[0]);
  const session=await openAreaRuntime({fixtureFile});const rows=[];
  try{
   for(const frame of [0,15,35,60,89]){
    const row=await session.page.evaluate(f=>window.areaProof.capture(f,{protect:true,png:true}),frame);
    const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
    assert.equal(row.diagnostic.glError,0);assert.equal(row.diagnostic.camera.cameraLocked,true);
    for(const name of ['protectedChangedPixels','markerChangedPixels','outsideRoiChangedPixels','safeAreaChangedPixels'])
     assert.equal(row.diagnostic.area.protection[name],0,name);
    assert.equal(row.diagnostic.area.graphics.nativeStateRestored,true);
    await writeFile(path.join(root,'evidence/synthetic',key+'-'+String(frame).padStart(3,'0')+'.png'),bytes);
    rows.push(row);console.log(JSON.stringify({phase:'AREA_SYNTHETIC',key,frame,status:'PASS'}));
   }
   assert.equal(session.errors.length,0);
  }finally{await session.close();}
  if(key==='a'){assert.equal(controls.at(-1).areas[0].coverage,0);assert.ok(controls[35].areas[0].coverage>.95);}
  if(key==='b')assert.equal(controls.at(-1).stateId,'C');
  if(key==='c'){
   assert.equal(controls[0].stateId,'INITIAL');assert.equal(controls.at(-1).stateId,'HOLD');
   assert.notDeepEqual(controls[15].fronts[0].geometry,controls[60].fronts[0].geometry);
   assert.notDeepEqual(controls[0].areas[0].geometry,controls[60].areas[0].geometry);
   assert.equal(controls.at(-1).timeLabel,'DAY 3');
  }
  evidence[key.toUpperCase()]={status:'PASS',cpuFrames:controls.length,nativeFrames:rows,
   features:fixture.areaPlan.operations.map(o=>o.type),geometryUnchanged:true,randomAccessDeterministic:true,
   timeStates:[...new Set(controls.map(c=>c.stateId).filter(Boolean))],hold:controls.at(-1).hold};
 }
 evidence.status='PASS';
}catch(error){evidence.status='FAIL';evidence.error=error.stack;throw error;}
finally{await writeFile(path.join(root,'evidence/SYNTHETIC.json'),JSON.stringify(evidence,null,2)+'\n');}
console.log(JSON.stringify({status:evidence.status,A:evidence.A?.status,B:evidence.B?.status,C:evidence.C?.status}));
