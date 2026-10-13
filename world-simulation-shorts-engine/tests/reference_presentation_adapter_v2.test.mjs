import test from 'node:test';
import assert from 'node:assert/strict';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,
 projectNativePoint,unprojectPresentationPoint,geoToPresentationScreen,presentationScreenToGeo,
 referenceScreenToGeo,presentationSourceUVBounds} from '../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';

const keys=[{frame:0,rollDegrees:0},{frame:38,rollDegrees:1},{frame:75,rollDegrees:1},
 {frame:112,rollDegrees:-.9},{frame:149,rollDegrees:-6}],
 start=[123.9,33.3,130.7,42.95],midpoint=[127.3,38.125],
 plan=()=>compileReferencePresentationPlan({rollKeyframes:keys,totalFrames:150,fps:30,overscan:1.19});
const near=(a,b,tolerance=1e-8)=>assert.ok(Math.abs(a-b)<=tolerance,`${a} != ${b}`);
const pointNear=(a,b,tolerance=1e-8)=>a.forEach((v,i)=>near(v,b[i],tolerance));

test('all 150 measured-roll frames sample strictly inside the genuine map texture',()=>{
 const p=plan();let lowest=Infinity;
 for(let f=0;f<150;f++){
  const state=evaluateReferencePresentationFrame(p,f);
  assert.equal(state.noCornerClip,true);
  const b=state.sourceUVBounds;lowest=Math.min(lowest,b[0],b[1],1-b[2],1-b[3]);
  assert.ok(b[0]>=0&&b[1]>=0&&b[2]<=1&&b[3]<=1);
 }
 assert.ok(lowest>.003);
});
test('measured roll keyframes are exact and no segment overshoots the measured range',()=>{
 const p=plan();for(const key of keys)near(evaluateReferencePresentationFrame(p,key.frame).rollDegrees,key.rollDegrees,1e-12);
 for(const segment of p.segments){
  const a=keys.find(k=>k.frame===segment.startFrame).rollDegrees,b=keys.find(k=>k.frame===segment.endFrame).rollDegrees;
  for(let frame=segment.startFrame;frame<=segment.endFrame;frame++){
   const angle=evaluateReferencePresentationFrame(p,frame).rollDegrees;assert.ok(angle>=Math.min(a,b)-1e-9&&angle<=Math.max(a,b)+1e-9);
  }
 }
});
test('shared cubic roll velocity is continuous at every measured knot',()=>{
 const p=plan();for(let i=1;i<p.segments.length;i++){
  const left=p.segments[i-1],right=p.segments[i],[,b,c,d]=left.coefficients,
   leftVelocity=(b+2*c+3*d)/(left.endFrame-left.startFrame),
   rightVelocity=right.coefficients[1]/(right.endFrame-right.startFrame);
  near(leftVelocity,rightVelocity,1e-12);
 }
});
test('foreground unit projection and inverse are exact under the same roll/crop transform',()=>{
 const p=plan();for(const frame of[0,38,75,112,149]){
  const state=evaluateReferencePresentationFrame(p,frame);
  for(const point of[[0,0],[540,960],[900,1400],[-80,240]])pointNear(unprojectPresentationPoint(projectNativePoint(point,state),state),point);
 }
});
test('zero-roll overscan cancels the rendering extent expansion without changing geography',()=>{
 const state=evaluateReferencePresentationFrame(plan(),0),b=expandNativeBounds({bounds:start,referenceStartBounds:start,
  rollDegrees:0,overscan:state.overscan});
 for(const geo of[[126.97,37.57],[129.07,35.12],[125.75,39.03]]){
  const expected=[(geo[0]-start[0])/(start[2]-start[0])*1080,(start[3]-geo[1])/(start[3]-start[1])*1920];
  pointNear(geoToPresentationScreen(geo,b,state),expected);
 }
});
test('inverse-rotated pan preserves the actual measured map-center displacement',()=>{
 const state=evaluateReferencePresentationFrame(plan(),149),a=1.1515,d=[106.97,419.955],w=6.8/a,h=9.65/a,
  c=[midpoint[0]-d[0]*w/1080,midpoint[1]+d[1]*h/1920],bounds=[c[0]-w/2,c[1]-h/2,c[0]+w/2,c[1]+h/2],
  b=expandNativeBounds({bounds,referenceStartBounds:start,rollDegrees:state.rollDegrees,overscan:state.overscan});
 pointNear(geoToPresentationScreen(midpoint,b,state),[540+d[0],960+d[1]]);
});
test('rolled geographic projection agrees with directly measured screen similarity',()=>{
 const state=evaluateReferencePresentationFrame(plan(),149),a=1.1515,d=[106.97,419.955],w=6.8/a,h=9.65/a,
  c=[midpoint[0]-d[0]*w/1080,midpoint[1]+d[1]*h/1920],bounds=[c[0]-w/2,c[1]-h/2,c[0]+w/2,c[1]+h/2],
  b=expandNativeBounds({bounds,referenceStartBounds:start,rollDegrees:state.rollDegrees,overscan:state.overscan});
 for(const geo of[[125.8,39.8],[127.7,40.2],[128.2,37.4]]){
  const output=geoToPresentationScreen(geo,b,state),inverse=referenceScreenToGeo(output,{startBounds:start,scale:a,
   rollDegrees:state.rollDegrees,displacement:d});pointNear(inverse,geo);
 }
});
test('all-map geographic and screen inverse stay consistent for every frame',()=>{
 const p=plan();for(let frame=0;frame<150;frame++){
  const state=evaluateReferencePresentationFrame(p,frame),b=expandNativeBounds({bounds:start,referenceStartBounds:start,
   rollDegrees:state.rollDegrees,overscan:state.overscan});
  for(const geo of[[125,39],[128,36],[130,42]])pointNear(presentationScreenToGeo(geoToPresentationScreen(geo,b,state),b,state),geo);
 }
});
test('compile never modifies the supplied measured keyframes',()=>{
 const before=JSON.stringify(keys);const p=plan();assert.equal(JSON.stringify(keys),before);assert.ok(Object.isFrozen(p.keyframes));
 assert.equal(p.sourceFootageSampling,false);assert.equal(p.cameraV5SourceUnchanged,true);
});
test('insufficient overscan, missing keys and invalid timing are rejected',()=>{
 assert.throws(()=>compileReferencePresentationPlan({rollKeyframes:keys,totalFrames:150,overscan:1.01}),/INSUFFICIENT/);
 assert.throws(()=>compileReferencePresentationPlan({rollKeyframes:keys.slice(1),totalFrames:150}),/ORDERED_COMPLETE/);
 assert.throws(()=>compileReferencePresentationPlan({rollKeyframes:keys,totalFrames:1}),/TIMING/);
});
test('out-of-range frames and invalid geographic bounds cannot silently render',()=>{
 assert.throws(()=>evaluateReferencePresentationFrame(plan(),150),/FRAME_REQUIRED/);
 assert.throws(()=>expandNativeBounds({bounds:[1,1,0,0],referenceStartBounds:start,rollDegrees:0}),/FRAMING/);
 assert.throws(()=>expandNativeBounds({bounds:[170,-80,179,85],referenceStartBounds:[170,-80,179,85],rollDegrees:0,overscan:2}),/GEOGRAPHIC_DOMAIN/);
});
test('larger measured absolute starting roll requires a corresponding real overscan margin',()=>{
 const large=[{frame:0,rollDegrees:12},{frame:149,rollDegrees:6}];
 assert.throws(()=>compileReferencePresentationPlan({rollKeyframes:large,totalFrames:150,overscan:1.19}),/INSUFFICIENT/);
 const p=compileReferencePresentationPlan({rollKeyframes:large,totalFrames:150,overscan:1.36});
 assert.equal(evaluateReferencePresentationFrame(p,0).noCornerClip,true);
});
test('actual initial coastline fit plus measured relative roll has safe corners through the entire 150-frame proof',()=>{
 const initial=10.997080633577195,p=compileReferencePresentationPlan({rollKeyframes:keys.map(k=>({...k,rollDegrees:k.rollDegrees+initial})),
  totalFrames:150,overscan:1.36});
 let minimumInset=Infinity,maxStep=0,last;
 for(let frame=0;frame<150;frame++){
  const state=evaluateReferencePresentationFrame(p,frame),b=state.sourceUVBounds;
  minimumInset=Math.min(minimumInset,b[0]*1080,b[1]*1920,(1-b[2])*1080,(1-b[3])*1920);
  if(last)maxStep=Math.max(maxStep,Math.abs(state.rollDegrees-last.rollDegrees));last=state;
  assert.equal(state.noCornerClip,true);
 }
 // Bilinear sampling needs half a texel of interior support, not an arbitrary larger map crop.
 assert.ok(minimumInset>.5);assert.ok(maxStep<.2);
 near(evaluateReferencePresentationFrame(p,149).rollDegrees,initial-6);
});
