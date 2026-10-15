/** Derived material weights only. Original values, source axes and validity
 * masks are immutable inputs. This module never invents geographic samples. */
export const MAX_SUPPORT_PIXELS=4*1024*1024;
const check=(ok,code)=>{if(!ok)throw Error(code);};
/** Testable reference of the GPU boolean support derivation. This only derives
 * a visual weight mask, never substitutes or repairs source values. */
export function supportMaskForRole(role,width,height,valid,values,{transform}={}){
 check(['terrain','bathymetry','surfaceTexture'].includes(role),'QUALITY_SOURCE_ROLE_REQUIRED');
 check(valid instanceof Uint8Array&&valid.length===width*height&&valid.every(v=>v===0||v===1),'QUALITY_BOOLEAN_SUPPORT_REQUIRED');
 check(values.length===width*height*(role==='surfaceTexture'?4:1),'QUALITY_SOURCE_SHAPE_REQUIRED');
 const mask=new Uint8Array(width*height);
 for(let j=0;j<height;j++)for(let i=0;i<width;i++){
  const k=j*width+i;if(!valid[k])continue;
  if(role==='surfaceTexture'){mask[k]=values[k*4+3]>0?1:0;continue;}
  if(role==='bathymetry'){mask[k]=Number.isFinite(values[k])&&values[k]<0?1:0;continue;}
  if(i<1||j<1||i>=width-1||j>=height-1)continue;
  if(transform&&Math.cos((transform[3]+(j+.5)*transform[5])*Math.PI/180)<.0001)continue;
  mask[k]=[k,k-1,k+1,k-width,k+width].every(n=>valid[n]===1&&Number.isFinite(values[n]))?1:0;
 }
 return mask;
}
function edtLine(f,n,out,v,z){
 let k=0;v[0]=0;z[0]=-Infinity;z[1]=Infinity;
 for(let q=1;q<n;q++){
  let s=((f[q]+q*q)-(f[v[k]]+v[k]*v[k]))/(2*q-2*v[k]);
  while(s<=z[k]){k--;s=((f[q]+q*q)-(f[v[k]]+v[k]*v[k]))/(2*q-2*v[k]);}
  k++;v[k]=q;z[k]=s;z[k+1]=Infinity;
 }
 k=0;for(let q=0;q<n;q++){while(z[k+1]<q)k++;const d=q-v[k];out[q]=d*d+f[v[k]];}
}
/** Euclidean distance from every supported native cell to unsupported cells,
 * including an explicit zero-support border. Half-cell subtraction aligns the
 * transition with cell edges. Invalid cells retain negative half-cell support. */
export function buildSupportDistance(mask,width,height){
 check(Number.isSafeInteger(width)&&Number.isSafeInteger(height)&&width>0&&height>0&&width*height<=MAX_SUPPORT_PIXELS,'QUALITY_SUPPORT_PIXEL_LIMIT');
 check(mask instanceof Uint8Array&&mask.length===width*height&&mask.every(v=>v===0||v===1),'QUALITY_BOOLEAN_SUPPORT_REQUIRED');
 const w=width+2,h=height+2,n=w*h,a=new Float64Array(n),b=new Float64Array(n),max=Math.max(w,h);
 for(let j=1;j<h-1;j++)for(let i=1;i<w-1;i++)a[j*w+i]=mask[(j-1)*width+i-1]?1e20:0;
 const line=new Float64Array(max),out=new Float64Array(max),v=new Int32Array(max),z=new Float64Array(max+1);
 for(let j=0;j<h;j++){for(let i=0;i<w;i++)line[i]=a[j*w+i];edtLine(line,w,out,v,z);for(let i=0;i<w;i++)b[j*w+i]=out[i];}
 for(let i=0;i<w;i++){for(let j=0;j<h;j++)line[j]=b[j*w+i];edtLine(line,h,out,v,z);for(let j=0;j<h;j++)a[j*w+i]=out[j];}
 const distances=new Float32Array(width*height);let supported=0,maximum=0;
 for(let j=0;j<height;j++)for(let i=0;i<width;i++){
  const k=j*width+i;if(mask[k]){supported++;distances[k]=Math.max(0,Math.sqrt(a[(j+1)*w+i+1])-.5);maximum=Math.max(maximum,distances[k]);}
  else distances[k]=-.5;
 }
 return {distances,statistics:{width,height,supported,total:width*height,unsupported:width*height-supported,
  maximumDistanceSourcePixels:maximum,sourceValuesChanged:false,geographicSupportExpanded:false}};
}
/** CPU reference of shader MANUAL bilinear weights (raw values stay NEAREST).
 * Native coordinates are CORNER positions, so cell centres are i+.5,j+.5. */
export function supportDistanceAt(distances,width,height,sourcePosition){
 const x=sourcePosition[0]-.5,y=sourcePosition[1]-.5,i=Math.floor(x),j=Math.floor(y),fx=x-i,fy=y-j;
 const at=(a,b)=>a<0||b<0||a>=width||b>=height?-.5:distances[b*width+a];
 return (at(i,j)*(1-fx)+at(i+1,j)*fx)*(1-fy)+(at(i,j+1)*(1-fx)+at(i+1,j+1)*fx)*fy;
}
export function featherWeight(distance,width){
 check(Number.isFinite(width)&&width>0&&width<=32,'QUALITY_FEATHER_WIDTH_REQUIRED');
 const x=Math.max(0,Math.min(1,distance/width));return x*x*(3-2*x);
}
/** Numerical baseline defect reference: old support depends only on rectangle,
 * so an internal invalid cell borders a fully weighted valid cell. */
export function oldRectangleWeight(width,height,sourcePosition,feather=1){
 const edge=Math.min(sourcePosition[0],sourcePosition[1],width-sourcePosition[0],height-sourcePosition[1]);
 return featherWeight(edge,feather);
}
