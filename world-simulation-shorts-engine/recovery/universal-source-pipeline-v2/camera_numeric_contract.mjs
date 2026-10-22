/** Cross-engine arithmetic agreement only; this does not authorize a camera. */
export const CAMERA_NUMERIC_CONTRACT=Object.freeze({
 version:'CAMERA_V5_CROSS_ENGINE_NUMERICS_V1',maximumUlps:256,
 maximumCanonicalPixelDelta:1e-9,canonicalOutput:Object.freeze([1080,1920]),
 source:'Measured Node24/Chromium154 evaluation of the same immutable V5 plan',
 renderState:'ALWAYS_REEVALUATED_BY_BROWSER_CAMERA_V5',localAdmissionChanged:false,
});
const finiteBounds=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)
 &&b[0]<b[2]&&b[1]<b[3]&&b[0]>=-180&&b[2]<=180&&b[1]>=-90&&b[3]<=90;
function orderedFloat64(value){
 const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,value,false);
 const bits=view.getBigUint64(0,false);
 return(bits>>63n)?-(bits&0x7fffffffffffffffn):bits;
}
export function float64UlpDistance(a,b){
 if(!Number.isFinite(a)||!Number.isFinite(b))return null;
 const delta=orderedFloat64(a)-orderedFloat64(b);return delta<0n?-delta:delta;
}
export function cameraBoundsNumericallyAgree(actual,expected){
 if(!finiteBounds(actual)||!finiteBounds(expected))return{matches:false,reason:'INVALID_GEOGRAPHIC_BOUNDS'};
 let maxUlps=0n,maxCanonicalPixelDelta=0;
 for(let axis=0;axis<4;axis++){
  const distance=float64UlpDistance(actual[axis],expected[axis]),dimension=axis%2,
   span=Math.min(actual[dimension+2]-actual[dimension],expected[dimension+2]-expected[dimension]),
   pixels=Math.abs(actual[axis]-expected[axis])/span*CAMERA_NUMERIC_CONTRACT.canonicalOutput[dimension];
  if(distance>maxUlps)maxUlps=distance;maxCanonicalPixelDelta=Math.max(maxCanonicalPixelDelta,pixels);
 }
 const ulpsAccepted=maxUlps<=BigInt(CAMERA_NUMERIC_CONTRACT.maximumUlps),
  pixelsAccepted=maxCanonicalPixelDelta<=CAMERA_NUMERIC_CONTRACT.maximumCanonicalPixelDelta;
 return{matches:ulpsAccepted&&pixelsAccepted,reason:!ulpsAccepted?'ULP_BOUND_EXCEEDED':!pixelsAccepted?'CANONICAL_PIXEL_BOUND_EXCEEDED':'NUMERIC_AGREEMENT',
  maxUlps:maxUlps.toString(),maxCanonicalPixelDelta};
}
