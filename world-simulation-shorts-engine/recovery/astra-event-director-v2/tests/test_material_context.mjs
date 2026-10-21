/** Mock-context CPU identity tests, never NVIDIA/render verification. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {trackDirectorMaterialPass,readDirectorMaterialFrame,clearDirectorMaterialFrame,
 publishDirectorMaterialFrame} from '../material_context.mjs';
function fixture(){
 const textures=new Set(),texture={},gl={isTexture:x=>textures.has(x)},canvas={getContext:id=>id==='webgl2'?gl:null};
 textures.add(texture);let disposed=false,fail=false;
 const pass={evidence:{preserved:true},outputTexture:texture,snapshotFrame:null,
  draw(args){if(fail)throw Error('PRESERVED_DRAW_FAILED');this.snapshotFrame={frame:args.frame};return{preserved:true,frame:args.frame};},
  dispose(){disposed=true;textures.delete(texture);}};
 return{pass,canvas,gl,texture,textures,args:{frame:600,bounds:[1,2,3,4]},
  disposed:()=>disposed,fail:()=>{fail=true;}};
}
test('actual owner texture identity is preserved, not serialized or copied',()=>{
 const f=fixture(),tracked=trackDirectorMaterialPass(f);
 const result=tracked.draw(f.args),record=readDirectorMaterialFrame(f.canvas,f.args);
 assert.equal(record.texture,f.texture);assert.equal(record.originalMaterialOwner,f.pass);
 assert.equal(tracked.outputTexture,f.texture);assert.deepEqual(tracked.snapshotFrame,{frame:600});
 assert.equal(result.eventDirectorMaterial.actualCombinedTexture,true);
 assert.equal(result.eventDirectorMaterial.historicalLightV3Connected,false);
 assert.equal(result.eventDirectorMaterial.historicalLightV3DrawCount,0);
 assert.equal(result.eventDirectorMaterial.nvidiaHardwareVerified,false);
 assert.equal(tracked.evidence.preserved,true);tracked.dispose();
});
test('before draw and after dispose cannot supply a texture',()=>{
 const f=fixture(),tracked=trackDirectorMaterialPass(f);
 assert.throws(()=>readDirectorMaterialFrame(f.canvas,f.args),/UNAVAILABLE/);
 tracked.draw(f.args);tracked.dispose();tracked.dispose();assert.equal(f.disposed(),true);
 assert.equal(readDirectorMaterialFrame(f.canvas,{...f.args,required:false}),null);
 assert.throws(()=>tracked.draw(f.args),/DISPOSED/);
 assert.throws(()=>tracked.outputTexture,/DISPOSED/);
});
test('stale global frame or another camera bounds are rejected',()=>{
 const f=fixture(),tracked=trackDirectorMaterialPass(f);tracked.draw(f.args);
 assert.throws(()=>readDirectorMaterialFrame(f.canvas,{...f.args,frame:601}),/STALE_FRAME/);
 assert.throws(()=>readDirectorMaterialFrame(f.canvas,{...f.args,bounds:[0,2,3,4]}),/BOUNDS_MISMATCH/);
 tracked.draw({...f.args,frame:601});assert.equal(readDirectorMaterialFrame(f.canvas,{...f.args,frame:601}).frame,601);
 tracked.dispose();
});
test('texture from another canvas and invalid/deleted texture are rejected',()=>{
 const f=fixture(),g=fixture(),tracked=trackDirectorMaterialPass(f);
 assert.throws(()=>publishDirectorMaterialFrame(f.canvas,{owner:f.pass,gl:g.gl,texture:g.texture,...f.args}),/OWNER_MISMATCH/);
 f.pass.outputTexture=g.texture;assert.throws(()=>tracked.draw(f.args),/ACTUAL_WEBGL_TEXTURE/);
 f.pass.outputTexture=f.texture;tracked.draw(f.args);f.textures.delete(f.texture);
 assert.throws(()=>readDirectorMaterialFrame(f.canvas,f.args),/TEXTURE_INVALID/);tracked.dispose();
});
test('failed original draw clears prior result and propagates original failure',()=>{
 const f=fixture(),tracked=trackDirectorMaterialPass(f);tracked.draw(f.args);f.fail();
 assert.throws(()=>tracked.draw({...f.args,frame:601}),/PRESERVED_DRAW_FAILED/);
 assert.equal(readDirectorMaterialFrame(f.canvas,{...f.args,required:false}),null);tracked.dispose();
});
test('duplicate owners and forged clearing cannot steal the registered source',()=>{
 const f=fixture(),tracked=trackDirectorMaterialPass(f);tracked.draw(f.args);
 assert.throws(()=>trackDirectorMaterialPass(f),/ALREADY_BOUND/);
 assert.throws(()=>clearDirectorMaterialFrame(f.canvas,{}),/OWNER_MISMATCH/);tracked.dispose();
});
test('returned frame and camera bounds are immutable',()=>{
 const f=fixture(),tracked=trackDirectorMaterialPass(f);tracked.draw(f.args);
 const r=readDirectorMaterialFrame(f.canvas,f.args);
 assert.equal(Object.isFrozen(r),true);assert.equal(Object.isFrozen(r.bounds),true);
 assert.throws(()=>{r.frame=12;},TypeError);tracked.dispose();
});
test('browser bridge keeps settings on the exact preserved module instance',async()=>{
 const raw=await readFile(new URL('../material_bridge.mjs',import.meta.url),'utf8');
 for(const symbol of ['setReferenceSourceProfile','setQualityMaterialProfile','configureAstraMaterialForCanvas',
  'clearAstraMaterialForCanvas','createNativeDomainBinding','describeNativeDomainBinding','getNativeDomainCoverage',
  'REFERENCE_TERRAIN_MATERIAL_V4_VERSION','DEFAULT_REFERENCE_TERRAIN_PROFILE_V4','validateReferenceTerrainProfileV4'])assert.ok(raw.includes(symbol));
 assert.ok(raw.includes("from '/reference/director_parent_source_material.mjs'"));
 assert.ok(raw.includes('createMapTerrainMaterialPassV4=createReferenceTerrainMaterialPassV4'));
 assert.ok(!raw.includes('FRAGMENT_SHADER'));assert.ok(!raw.includes('drawArrays'));
});
