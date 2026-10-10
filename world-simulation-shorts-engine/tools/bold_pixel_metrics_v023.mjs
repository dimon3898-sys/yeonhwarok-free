/** Pixel measurements only. No GPU renderer, pipeline fallback, or inferred quality PASS. */
const finite=value=>Number.isFinite(value);
const quantile=(values,q)=>{if(!values.length)return null;const sorted=[...values].sort((a,b)=>a-b);return sorted[Math.min(sorted.length-1,Math.floor(q*(sorted.length-1)))];};
const luminance=(data,index)=>(.2126*data[index]+.7152*data[index+1]+.0722*data[index+2])/255;
const rgbDifference=(a,b,index)=>Math.hypot(a[index]-b[index],a[index+1]-b[index+1],a[index+2]-b[index+2])/(255*Math.sqrt(3));
const validImage=(value,width,height)=>{if(!(value instanceof Uint8ClampedArray||value instanceof Uint8Array)||value.length!==width*height*4)throw Error('BOLD_PIXEL_IMAGE_INVALID');};

export function imageDifference(before,after,width,height){
 validImage(before,width,height);validImage(after,width,height);let different=0,maximum=0;
 for(let i=0;i<before.length;i++){const difference=Math.abs(before[i]-after[i]);if(difference){different++;maximum=Math.max(maximum,difference);}}
 return {identical:different===0,different_channels:different,maximum_channel_difference:maximum};
}

/** Ignore anti-aliased boundary pixels; compare actual interior RGBA and terrain edges. */
export function regionPixelMetrics(before,after,mask,width,height,{erosion=6,stride=2}={}){
 for(const image of [before,after,mask])validImage(image,width,height);
 if(!Number.isInteger(erosion)||erosion<1||!Number.isInteger(stride)||stride<1)throw Error('BOLD_PIXEL_SAMPLE_POLICY_INVALID');
 const deltas=[],beforeEdges=[],afterEdges=[];let samples=0,changed=0;
 // A two-pass distance field excludes diagonally oriented real boundaries;
 // four cardinal probes miss nearby diagonal coastlines and pollute texture metrics.
 const distance=new Float32Array(width*height),diagonal=Math.SQRT2;
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){const i=y*width+x;distance[i]=mask[i*4+3]>=250?Math.min(x+1,y+1,width-x,height-y):0;}
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){const i=y*width+x;if(!distance[i])continue;let d=distance[i];if(x)d=Math.min(d,distance[i-1]+1);if(y)d=Math.min(d,distance[i-width]+1);if(x&&y)d=Math.min(d,distance[i-width-1]+diagonal);if(x+1<width&&y)d=Math.min(d,distance[i-width+1]+diagonal);distance[i]=d;}
 for(let y=height-1;y>=0;y--)for(let x=width-1;x>=0;x--){const i=y*width+x;if(!distance[i])continue;let d=distance[i];if(x+1<width)d=Math.min(d,distance[i+1]+1);if(y+1<height)d=Math.min(d,distance[i+width]+1);if(x+1<width&&y+1<height)d=Math.min(d,distance[i+width+1]+diagonal);if(x&&y+1<height)d=Math.min(d,distance[i+width-1]+diagonal);distance[i]=d;}
 const interior=(x,y)=>{const i=y*width+x;return distance[i]>erosion&&distance[i+1]>erosion&&distance[i+width]>erosion;};
 for(let y=erosion;y<height-erosion-1;y+=stride)for(let x=erosion;x<width-erosion-1;x+=stride){
  if(!interior(x,y))continue;const index=(y*width+x)*4,delta=rgbDifference(before,after,index);samples++;deltas.push(delta);if(delta>2/255)changed++;
  for(const step of [4,width*4]){beforeEdges.push(luminance(before,index+step)-luminance(before,index));afterEdges.push(luminance(after,index+step)-luminance(after,index));}
 }
 let xx=0,yy=0,xy=0;for(let i=0;i<beforeEdges.length;i++){xx+=beforeEdges[i]**2;yy+=afterEdges[i]**2;xy+=beforeEdges[i]*afterEdges[i];}
 const textured=xx>1e-7;
 return {interior_samples:samples,changed_fraction:samples?changed/samples:0,median_rgb_contrast:quantile(deltas,.5),p10_rgb_contrast:quantile(deltas,.1),terrain_measurement_available:textured,
  terrain_edge_retention:textured?Math.sqrt(yy/xx):null,terrain_edge_correlation:textured&&yy>1e-12?xy/Math.sqrt(xx*yy):null,
  scope:'Actual sampled Canvas2D RGBA interior; contrast is color distance, terrain retention is source edge amplitude/correlation.'};
}

/** Pixel-width sampling across the rasterized line, not its configured lineWidth. */
export function boundaryPixelMetrics(image,width,height,segments,{maximumSamples=48,minimumSegmentLength=2,radius=18,step=.25,brightCore=false}={}){
 validImage(image,width,height);const widths=[],peaks=[];
 const value=(x,y,core=brightCore)=>{if(x<0||x>=width-1||y<0||y>=height-1)return 0;const xx=Math.floor(x),yy=Math.floor(y),dx=x-xx,dy=y-yy,p=(x,y)=>{const i=(y*width+x)*4;return image[i+3]/255*(core?luminance(image,i):1);};return p(xx,yy)*(1-dx)*(1-dy)+p(xx+1,yy)*dx*(1-dy)+p(xx,yy+1)*(1-dx)*dy+p(xx+1,yy+1)*dx*dy;};
 for(const [a,b]of segments){
  if(widths.length>=maximumSamples)break;const length=Math.hypot(b.x-a.x,b.y-a.y);if(length<minimumSegmentLength)continue;
  const x=(a.x+b.x)/2,y=(a.y+b.y)/2;if(x<radius||x>width-radius||y<radius||y>height-radius)continue;
  const nx=-(b.y-a.y)/length,ny=(b.x-a.x)/length,samples=[];for(let at=-radius;at<=radius+1e-7;at+=step)samples.push({at,alpha:value(x+nx*at,y+ny*at)});
  const peak=Math.max(...samples.map(v=>v.alpha));if(peak<.08)continue;
  // FWHM accepts anti-aliased coverage while rejecting absent/sub-visible strokes.
  const middle=Math.floor(samples.length/2),threshold=peak*.5;let lo=middle,hi=middle;
  if(samples[middle].alpha<threshold)continue;
  while(lo>0&&samples[lo-1].alpha>=threshold)lo--;while(hi<samples.length-1&&samples[hi+1].alpha>=threshold)hi++;
  if(lo===0||hi===samples.length-1)continue; // nearby unrelated geometry/corner crossing: unmeasurable
  const left=samples[lo-1].at+step*(threshold-samples[lo-1].alpha)/(samples[lo].alpha-samples[lo-1].alpha);
  const right=samples[hi].at+step*(samples[hi].alpha-threshold)/(samples[hi].alpha-samples[hi+1].alpha);
  widths.push(right-left);peaks.push(value(x,y,false));
 }
 return {cross_sections:widths.length,width_px_median:quantile(widths,.5),width_px_p10:quantile(widths,.1),width_px_p90:quantile(widths,.9),peak_alpha_median:quantile(peaks,.5),method:brightCore?'Subpixel perpendicular FWHM of actual premultiplied-luminance bright core; dark contrast edge excluded, no nominal width used.':'Subpixel perpendicular FWHM of actual transparent Canvas2D stroke RGBA; no nominal width used.'};
}

/** Fill may touch a single raster edge pixel; farther ocean/hole ink is a failure. */
export function containmentPixelMetrics(fill,referenceMask,width,height,{edgeTolerance=1}={}){
 validImage(fill,width,height);validImage(referenceMask,width,height);let filled=0,outside=0;
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  if(fill[(y*width+x)*4+3]<3)continue;filled++;let inside=false;
  for(let dy=-edgeTolerance;dy<=edgeTolerance&&!inside;dy++)for(let dx=-edgeTolerance;dx<=edgeTolerance;dx++){const xx=x+dx,yy=y+dy;if(xx>=0&&xx<width&&yy>=0&&yy<height&&referenceMask[(yy*width+xx)*4+3]>0){inside=true;break;}}
  if(!inside)outside++;
 }
 return {filled_pixels:filled,outside_native_fill_pixels:outside,outside_fraction:filled?outside/filled:0,edge_tolerance_px:edgeTolerance};
}

/** Fail closed on missing layers, invisible fill, opaque terrain, or reversed hierarchy. */
export function evaluateBoldPixels({primary,secondary,primaryBoundary,secondaryBoundary,containment,off,secondaryRequired=true}){
 const failures=[];
 const check=(condition,code)=>{if(!condition)failures.push(code);};
 check(primary?.interior_samples>=32,'PRIMARY_FILL_NOT_MEASURABLE');
 check(finite(primary?.median_rgb_contrast)&&primary.median_rgb_contrast>=.08&&primary.changed_fraction>=.95,'PRIMARY_FILL_LOW_CONTRAST');
 check(primary?.terrain_measurement_available===true&&primary.terrain_edge_retention>=.25&&primary.terrain_edge_correlation>=.85,'PRIMARY_TERRAIN_LOST');
 check(primaryBoundary?.cross_sections>=1&&primaryBoundary.width_px_median>=6&&primaryBoundary.width_px_median<=11&&primaryBoundary.peak_alpha_median>=.65,'PRIMARY_BOUNDARY_NOT_BOLD');
 if(secondaryRequired){
  check(secondary?.interior_samples>=32,'SECONDARY_FILL_NOT_MEASURABLE');
  check(finite(secondary?.median_rgb_contrast)&&secondary.median_rgb_contrast>=.025&&secondary.changed_fraction>=.90,'SECONDARY_FILL_LOW_CONTRAST');
  check(secondary?.terrain_measurement_available===true&&secondary.terrain_edge_retention>=.45&&secondary.terrain_edge_correlation>=.85,'SECONDARY_TERRAIN_LOST');
  check(secondaryBoundary?.cross_sections>=1&&secondaryBoundary.width_px_median>=2&&secondaryBoundary.width_px_median<primaryBoundary?.width_px_median,'SECONDARY_BOUNDARY_HIERARCHY');
  check(primary?.median_rgb_contrast>secondary?.median_rgb_contrast*1.1,'FILL_HIERARCHY_REVERSED');
 }
 check(containment?.filled_pixels>0&&containment.outside_native_fill_pixels===0,'COASTLINE_OR_HOLE_LEAK');
 check(off?.identical===true,'OFF_BASELINE_CHANGED');
 return {passed:failures.length===0,failures,GPU:'NOT_RUN',visual_quality_acceptance:'NOT_RUN',scope:'CPU Canvas pixel admission only; human 0.5s/GPU output readability remains unverified.'};
}
