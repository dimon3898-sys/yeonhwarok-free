/** Synthetic CPU readback arrays validate measurement math, not GPU execution. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {measureUnitPixels,evidenceNames} from '../software_probe_ref2.mjs';
function fixture({outside=false,overlap=false}={}){
 const width=16,height=16,on=new Uint8Array(width*height*4),off=new Uint8Array(width*height*4);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const i=((height-1-y)*width+x)*4;on[i]=off[i]=40;on[i+1]=off[i+1]=50;on[i+2]=off[i+2]=60;on[i+3]=off[i+3]=255;
  if(x>=5&&x<=10&&y>=5&&y<=10){on[i]=200;on[i+2]=80;}
 }
 if(outside)on[0]=200;
 const full={frame:75,camera:{bounds:[0,0,1,1]},units:{units:[{id:'generic',profile_id:'ROLE',size_px:12,bounds:[4,4,12,12]}]}};
 if(overlap)full.units.units.push({id:'other',profile_id:'ROLE',size_px:12,bounds:[7,7,14,14]});
 let disabled=false;
 globalThis.window={referenceProof:{pipeline:{diagnostic:full,readPixels:()=>disabled?off:on},
  capture:async(frame,options)=>{assert.equal(options.combatEnabled,false);disabled=true;return {diagnostic:{...full,frame,units:{units:[]}}};}}};
 return {width,height};
}
test('unit width comes from actual on/off pixels rather than supplied geometry bounds',async()=>{
 const dimensions=fixture();try{const result=await measureUnitPixels({frame:75,...dimensions});
  assert.equal(result.status,'PASS');assert.equal(result.units[0].actualVisibleDifferenceWidth,6);
  assert.equal(result.units[0].actualVisibleDifferenceHeight,6);assert.equal(result.units[0].nominalSizePx,12);
  assert.deepEqual(result.units[0].measuredRGBDifferenceBounds,[5,5,11,11]);
  assert.equal(result.mobileReadabilityApproved,false);assert.equal(result.physicalNvidiaExecuted,false);
 }finally{delete globalThis.window;}
});
test('ablation cannot silently attribute background changes to the icon',async()=>{
 const dimensions=fixture({outside:true});try{await assert.rejects(()=>measureUnitPixels({frame:75,...dimensions}),/REFERENCE_UNIT_ABLATION_CHANGED_OUTSIDE_UNITS/);}
 finally{delete globalThis.window;}
});
test('ambiguous overlapping measurement rectangles produce explicit SKIP, not pixel-width PASS',async()=>{
 const dimensions=fixture({overlap:true});try{const result=await measureUnitPixels({frame:75,...dimensions});
  assert.equal(result.status,'SKIP');assert.equal(result.renderedPixelWidthClaimed,false);
 }finally{delete globalThis.window;}
});
test('exact ten test-only PNG checkpoints preserve five integrated information stages',()=>{
 assert.equal(new Set(evidenceNames).size,10);assert.ok(evidenceNames.every(name=>/^[A-F]_\d{3}\.png$/.test(name)));
 for(const frame of ['000','038','075','112','149'])assert.ok(evidenceNames.includes('F_'+frame+'.png'));
});
