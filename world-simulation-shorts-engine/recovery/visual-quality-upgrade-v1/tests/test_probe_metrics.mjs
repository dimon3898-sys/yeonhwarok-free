/** Synthetic CPU inputs test metric math only; actual browser evidence comes from CI. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import path from 'node:path';
import {captureSoftwareFrame,sourceEdgeSamples,evidenceNames} from '../software_probe.mjs';
test('actual-readback metric collector uses pixels and keeps PNG optional',async()=>{
 const width=16,height=16,pixels=new Uint8Array(width*height*4);
 for(let j=0;j<height;j++)for(let i=0;i<width;i++){const k=(j*width+i)*4;
  pixels[k]=pixels[k+1]=pixels[k+2]=i<8?50:200;pixels[k+3]=255;}
 const calls=[];globalThis.window={referenceProof:{capture:async(frame,options)=>{calls.push({frame,options});return {diagnostic:{frame},raw_rgba_sha256:'a'.repeat(64)};},
  pipeline:{readPixels:()=>pixels,project:geo=>geo}}};
 try{
  const result=await captureSoftwareFrame({frame:75,width,height,png:false,
   samples:[{role:'terrain',kind:'RECTANGLE',geo:[7.5,8],inside:[9,8]}]});
  assert.equal(calls[0].options.png,false);assert.equal(result.actualReadPixelsExecuted,true);
  assert.ok(Math.abs(result.metrics.luminanceMean-125/255)<1e-10);
  assert.ok(result.metrics.sourceEdgeJumps['terrain:RECTANGLE:1'].meanRGBJump>.5);
  assert.equal(result.metrics.sourceEdgeJumps['terrain:RECTANGLE:1'].samples,1);
 }finally{delete globalThis.window;}
});
test('native support sampling preserves signed values and original validity bytes',async()=>{
 const root=await mkdtemp('/workspace/test-only-quality-edge-');
 try{
  const valid=Buffer.from([1,1,1,1]),values=Buffer.alloc(8);[-30,20,-10,5].forEach((v,i)=>values.writeInt16LE(v,i*2));
  await writeFile(path.join(root,'valid.bin'),valid);await writeFile(path.join(root,'values.bin'),values);
  const manifest={sources:{bathymetry:{parts:[{dimensions:[2,2],bbox:[0,0,2,2],transform:[0,1,0,2,0,-1],
   valid:{file:'valid.bin'},values:{file:'values.bin'}}]}}};
  const file=path.join(root,'UPLOAD_MANIFEST.json');await writeFile(file,JSON.stringify(manifest));
  const samples=await sourceEdgeSamples(file);
  assert.ok(samples.some(s=>s.kind==='VALIDITY_OR_SIGN'&&s.role==='bathymetry'));
  assert.deepEqual(await readFile(path.join(root,'valid.bin')),valid);assert.deepEqual(await readFile(path.join(root,'values.bin')),values);
  assert.ok(samples.length<=192);
 }finally{await rm(root,{recursive:true,force:true});}
});
test('software evidence exact eight images remain distinct from production proof',()=>{
 assert.equal(new Set(evidenceNames).size,8);assert.ok(evidenceNames.every(name=>/^[A-F]_\d{3}\.png$/.test(name)));
 assert.ok(evidenceNames.includes('A_075.png'));assert.ok(evidenceNames.includes('F_149.png'));
});
