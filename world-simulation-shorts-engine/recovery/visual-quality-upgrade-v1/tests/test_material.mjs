import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {buildSupportDistance,supportDistanceAt,featherWeight,oldRectangleWeight,supportMaskForRole}
 from '../distance_support.mjs';
import {validateBoundaryProfile,effectiveFeather,buildQualityFragment} from '../quality_material_core.mjs';
import {supportMaskFragment} from '../support_gpu.mjs';
const close=(a,b,eps=1e-6)=>assert.ok(Math.abs(a-b)<=eps,`${a} != ${b}`);
test('old rectangular feather numerically leaves full contrast beside internal NoData',()=>{
 const w=129,h=129,mask=new Uint8Array(w*h).fill(1);mask[64*w+64]=0;
 const result=buildSupportDistance(mask,w,h),at=[65.5,64.5];
 const old=oldRectangleWeight(w,h,at),distance=supportDistanceAt(result.distances,w,h,at),quality=featherWeight(distance,32);
 assert.equal(old,1);close(distance,.5);assert.ok(quality<.001);
 // A native invalid neighbour is exact baseline (weight0). Boundary B reduces
 // this numerical cell-to-cell material jump >99%; not NVIDIA visual proof.
 assert.ok(quality/old<.01);
});
test('distance transform matches brute-force Euclidean unsupported/border distances',()=>{
 for(const [w,h] of [[1,1],[4,3],[9,7]]){
  const mask=Uint8Array.from({length:w*h},(_,k)=>k%7===3?0:1),copy=mask.slice();
  const {distances}=buildSupportDistance(mask,w,h);
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
   if(!mask[y*w+x]){assert.equal(distances[y*w+x],-.5);continue;}
   let nearest=Infinity;
   for(let j=-1;j<=h;j++)for(let i=-1;i<=w;i++)if(i<0||j<0||i>=w||j>=h||!mask[j*w+i])
    nearest=Math.min(nearest,Math.hypot(i-x,j-y));
   close(distances[y*w+x],nearest-.5);
  }
  assert.deepEqual(mask,copy);
 }
});
test('all-invalid and all-valid supports remain explicit and bounded',()=>{
 const invalid=buildSupportDistance(new Uint8Array(25),5,5);assert.equal(invalid.statistics.supported,0);
 assert.ok(invalid.distances.every(x=>x===-.5));
 const valid=buildSupportDistance(new Uint8Array(25).fill(1),5,5);assert.equal(valid.statistics.supported,25);
 assert.equal(valid.distances[0],.5);assert.equal(valid.distances[12],2.5);
 assert.equal(valid.statistics.geographicSupportExpanded,false);
 assert.equal(valid.statistics.sourceValuesChanged,false);
});
test('cell-center alignment and manual interpolation fade to zero at true outer cell edges',()=>{
 const {distances}=buildSupportDistance(new Uint8Array(100).fill(1),10,10);
 close(supportDistanceAt(distances,10,10,[.5,5.5]),.5);
 close(supportDistanceAt(distances,10,10,[0,5.5]),0);
 close(supportDistanceAt(distances,10,10,[10,5.5]),0);
 assert.equal(featherWeight(-.2,32),0);assert.equal(featherWeight(35,32),1);
});
test('DEM support includes the actual finite derivative-neighbour footprint',()=>{
 const w=9,h=9,valid=new Uint8Array(w*h).fill(1),values=new Float32Array(w*h).fill(120);
 valid[40]=0;values[40]=NaN;const vb=valid.slice(),raw=values.slice();
 const mask=supportMaskForRole('terrain',w,h,valid,values);
 for(const k of [40,39,41,31,49,0,8,72,80])assert.equal(mask[k],0);
 assert.equal(mask[20],1);assert.deepEqual(valid,vb);assert.deepEqual(values,raw);
 const field=buildSupportDistance(mask,w,h);assert.equal(field.distances[39],-.5);
 const polar=supportMaskForRole('terrain',w,h,valid,values,{transform:[0,.0001,0,90.00045,0,-.0001]});
 assert.equal(polar[20],0);
});
test('surface support respects alpha independently; bathymetry sign never becomes native ocean mask',()=>{
 const valid=new Uint8Array(9).fill(1),rgb=new Uint8Array(36).fill(255),depth=Int16Array.from([-2,5,-3,0,-300,-1,-4,-5,-6]);
 rgb[4*4+3]=0;valid[8]=0;
 const surface=supportMaskForRole('surfaceTexture',3,3,valid,rgb),bathy=supportMaskForRole('bathymetry',3,3,valid,depth);
 assert.deepEqual([...surface],[1,1,1,1,0,1,1,1,0]);
 assert.deepEqual([...bathy],[1,0,1,0,1,1,1,1,0]);
 // Actual GIS land/ocean remains a separate SAME-FRAME shader gate, not here.
 assert.match(buildQualityFragment('bathymetry'),/depthMix\*\(1.-land\)\*support/);
});
test('desired feather is 32 OUTPUT pixels separately from each native grid density',()=>{
 const bounds=[-4,-2,4,2],dem={transform:[-4,.0003,0,2,0,-.0003]},depth={transform:[-4,.004,0,2,0,-.004]};
 const a=effectiveFeather(dem,bounds,1080,1920,32),b=effectiveFeather(depth,bounds,1080,1920,32);
 assert.notEqual(a.sourceFeatherPixels,b.sourceFeatherPixels);
 assert.equal(a.minimumScreenFeatherPixels,32);assert.equal(b.minimumScreenFeatherPixels,32);
 close(a.sourceFeatherPixels/a.sourcePixelsPerScreenPixel[0],32);
 assert.ok(a.maximumScreenFeatherPixels>=32);
});
test('boundary off is explicit and quality widths are bounded instead of one source pixel',()=>{
 assert.deepEqual(validateBoundaryProfile({boundary:false}),{boundary:false,screenFeatherPixels:32});
 assert.throws(()=>validateBoundaryProfile({screenFeatherPixels:0}));
 assert.throws(()=>validateBoundaryProfile({screenFeatherPixels:1000}));
 assert.throws(()=>validateBoundaryProfile({boundary:'yes'}));
});
test('derived support texture blends weights only; raw value texture remains exact texelFetch',()=>{
 for(const role of ['terrain','surfaceTexture','bathymetry']){
  const glsl=buildQualityFragment(role);
  assert.match(glsl,/texelFetch\(valuesTexture,p,0\)|texelFetch\(valuesTexture,q,0\)/);
  assert.doesNotMatch(glsl,/texture\(valuesTexture|texture\(coverageTexture,[^v]/);
  assert.match(glsl,/sourcePerScreenPixel=abs/);assert.match(glsl,/support=smoothstep\(0.,screenFeatherPixels/);
  assert.match(glsl,/float land=clamp\(texture\(coverageTexture,vUv\).r/);
  assert.match(glsl,/texelFetch\(validTexture,p,0\).r!=1u/);
 }
});
test('GPU boolean mask definitions match independent CPU support contracts',()=>{
 assert.match(supportMaskFragment('terrain'),/offsets\[5\]/);
 assert.match(supportMaskFragment('terrain'),/!isnan\(value\)&&!isinf\(value\)/);
 assert.match(supportMaskFragment('bathymetry'),/texelFetch\(valuesTexture,p,0\).r<0/);
 assert.match(supportMaskFragment('surfaceTexture'),/texelFetch\(valuesTexture,p,0\).a>0/);
 for(const role of ['terrain','bathymetry','surfaceTexture'])assert.doesNotMatch(supportMaskFragment(role),/coverageTexture/);
});
test('authentic-upload mask readback is bounded, restored and leaves original source textures unchanged',async()=>{
 const source=await readFile(new URL('../support_gpu.mjs',import.meta.url),'utf8');
 assert.match(source,/width\*height>MAX_SUPPORT_PIXELS/);assert.match(source,/restore\(gl,before\)/);
 assert.match(source,/gl.readPixels/);assert.match(source,/new Uint8Array\(width\*height\*4\)/);
 assert.doesNotMatch(source,/fetch\(|texImage2D\([^\n]*entry.values/);
});
test('factory baseline A delegates exact old ASTRA; B output snapshot feeds original downstream passes',async()=>{
 const wrapper=await readFile(new URL('../quality_material.mjs',import.meta.url),'utf8'),
 core=await readFile(new URL('../quality_material_core.mjs',import.meta.url),'utf8');
 assert.match(wrapper,/from '\/astra\/astra_material.mjs\?baseline'/);
 assert.match(wrapper,/if\(!c.qualityProfile.boundary\)return createOldAstra\(options\)/);
 assert.match(wrapper,/setQualityMaterialProfile/);assert.match(wrapper,/QUALITY_PROFILE_ALREADY_SELECTED/);
 assert.match(core,/const native=baseline.draw\(args\)/);
 assert.match(core,/get outputTexture\(\).*return snapshotTexture/);
 assert.match(core,/combinedOutputTexture:true/);assert.match(core,/sourceMaterialBeforeTerritory:true/);
 assert.match(core,/nativeCoastCoverageFiltered:false/);
});
