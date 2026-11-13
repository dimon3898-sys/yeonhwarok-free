/** Opt-in geographic camera math shared by source admission and the existing native renderer. */
import {fitC2VectorSamples} from './camera_curve_v1.mjs';
export const GEOGRAPHIC_CAMERA_VERSION='GEOGRAPHIC_MERCATOR_V1';
const check=(x,c)=>{if(!x)throw Error(c);},rad=x=>x*Math.PI/180,deg=x=>x*180/Math.PI;
export const mercatorY=latitude=>deg(Math.log(Math.tan(Math.PI/4+rad(latitude)/2)));
export const inverseMercatorY=y=>deg(2*Math.atan(Math.exp(rad(y)))-Math.PI/2);
export const geographicQ=point=>[point[0],-mercatorY(Math.max(-85,Math.min(85,point[1])))];
const keys=(x,allowed,code)=>{check(x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).every(k=>allowed.includes(k)),code);};
export function geographicCameraFrame(pose){
 keys(pose,['center','scale','rollDegrees'],'GEOGRAPHIC_CAMERA_POSE_FIELDS');
 check(Array.isArray(pose.center)&&pose.center.length===2&&pose.center.every(Number.isFinite)&&Math.abs(pose.center[0])<180&&Math.abs(pose.center[1])<85&&Number.isFinite(pose.scale)&&pose.scale>0&&pose.scale<=10000&&Number.isFinite(pose.rollDegrees)&&Math.abs(pose.rollDegrees)<=45,'GEOGRAPHIC_CAMERA_POSE_RANGE');
 const q=geographicQ(pose.center),a=rad(pose.rollDegrees),c=Math.cos(a),s=Math.sin(a);
 const inverse=p=>{const x=(p[0]-540)/pose.scale,y=(p[1]-960)/pose.scale;return[q[0]+c*x+s*y,inverseMercatorY(-(q[1]-s*x+c*y))];};
 const corners=[[0,0],[1080,0],[1080,1920],[0,1920]].map(inverse),bounds=[Math.min(...corners.map(p=>p[0])),Math.min(...corners.map(p=>p[1])),Math.max(...corners.map(p=>p[0])),Math.max(...corners.map(p=>p[1]))];
 check(bounds[0]>-180&&bounds[2]<180&&bounds[1]>-85&&bounds[3]<85,'GEOGRAPHIC_CAMERA_DOMAIN');
 const result={pose:structuredClone(pose),centerQ:q,corners,flatBounds:bounds,cameraLocked:false,settle:{locked:false},camera:{center:[...pose.center],noCloserThanApprovedStop:true},project(point){const p=geographicQ(point),x=p[0]-q[0],y=p[1]-q[1];return[540+pose.scale*(c*x-s*y),960+pose.scale*(s*x+c*y)];}};
 Object.defineProperty(result,"project",{value:result.project,enumerable:false});return result;
}
export function compileGeographicCamera(camera,{totalFrames,holdFrames=0,closestBounds}={}){
 keys(camera,['mode','projection','frames','interpolation'],'GEOGRAPHIC_CAMERA_FIELDS');
 check(camera.mode==='GEOGRAPHIC_TRACK'&&camera.projection===GEOGRAPHIC_CAMERA_VERSION&&Array.isArray(camera.frames)&&camera.frames.length===totalFrames,'GEOGRAPHIC_COMPLETE_CAMERA_TRACK_REQUIRED');
 const last=totalFrames-holdFrames-1;
 camera.frames.forEach(geographicCameraFrame);
 check(last>=0,'GEOGRAPHIC_HOLD_RANGE');
 for(let f=last+1;f<totalFrames;f++)check(JSON.stringify(camera.frames[f])===JSON.stringify(camera.frames[last]),'GEOGRAPHIC_FINAL_HOLD_REQUIRED');
 let frames=structuredClone(camera.frames),interpolationEvidence;
 if(camera.interpolation!==undefined){
  keys(camera.interpolation,['mode','knotSpacingFrames'],'GEOGRAPHIC_INTERPOLATION_FIELDS');
  check(camera.interpolation.mode==='QUINTIC_C2','GEOGRAPHIC_INTERPOLATION_MODE');
  const vectors=frames.slice(0,last+1).map(p=>[p.center[0],mercatorY(p.center[1]),Math.log(p.scale),p.rollDegrees]);
  const fitted=fitC2VectorSamples(vectors,camera.interpolation);
  frames=fitted.frames.map(v=>({center:[v[0],inverseMercatorY(v[1])],scale:Math.exp(v[2]),rollDegrees:v[3]}));
  frames[0]=structuredClone(camera.frames[0]);frames[last]=structuredClone(camera.frames[last]);
  for(let f=last+1;f<totalFrames;f++)frames.push(structuredClone(frames[last]));
  interpolationEvidence=fitted.evidence;
 }
 const samples=frames.map(geographicCameraFrame);
 if(closestBounds)for(const {pose}of samples){const q=geographicQ(pose.center),h=960/pose.scale,axis=[1080/pose.scale,inverseMercatorY(-q[1]+h)-inverseMercatorY(-q[1]-h)];check(axis[0]>=closestBounds[2]-closestBounds[0]-1e-8&&axis[1]>=closestBounds[3]-closestBounds[1]-1e-8,'GEOGRAPHIC_DETAIL_ADMISSION_EXCEEDED');}
 const bounds=samples.map(x=>x.flatBounds),coverageBounds=[Math.min(...bounds.map(b=>b[0])),Math.min(...bounds.map(b=>b[1])),Math.max(...bounds.map(b=>b[2])),Math.max(...bounds.map(b=>b[3]))];
 return {schema:GEOGRAPHIC_CAMERA_VERSION,totalFrames,frames,cpuFrameBounds:bounds,coverageBounds,holdFrames,...(interpolationEvidence?{interpolationEvidence}:{})};
}
export function selectGeographicTerrain(sources,pose,{maximumTextureSize=16384}={}){
 const frame=geographicCameraFrame(pose),b=frame.flatBounds,selected=[];
 check(Array.isArray(sources)&&sources.length>0&&sources.length<=8,'GEOGRAPHIC_TERRAIN_LEVELS_REQUIRED');
 for(const [index,a]of sources.entries()){
  if(!Array.isArray(a.bounds)||!Array.isArray(a.dimensions)||!Array.isArray(a.pixelSpacing)||a.CRS!=='EPSG:4326'||a.NoData!==null||!/^[a-f0-9]{64}$/.test(a.sha256??'')||a.dimensions.some(v=>!Number.isSafeInteger(v)||v<2||v>maximumTextureSize))throw Error('GEOGRAPHIC_TERRAIN_DESCRIPTOR');
  const spacing=a.pixelSpacing.map((v,i)=>Math.max(v,(a.bounds[i+2]-a.bounds[i])/a.dimensions[i]));
  check(spacing.every(v=>Number.isFinite(v)&&v>0),'GEOGRAPHIC_TERRAIN_SPACING');
  const gutter=Math.min((b[0]-a.bounds[0])/spacing[0],(b[1]-a.bounds[1])/spacing[1],(a.bounds[2]-b[2])/spacing[0],(a.bounds[3]-b[3])/spacing[1]);
  const density=[pose.scale*spacing[0],pose.scale*spacing[1]/Math.min(Math.cos(rad(b[1])),Math.cos(rad(b[3])))];
  if(gutter>=1-1e-8&&Math.max(...density)<=1+1e-8)selected.push({index,sha256:a.sha256,bounds:[...a.bounds],spacing,density,gutter});
 }
 check(selected.length,'GEOGRAPHIC_NO_QUALIFIED_TERRAIN_LEVEL');
 // Coarsest adequate level limits memory bandwidth; every selected level has genuine native density.
 selected.sort((a,b)=>b.spacing[0]-a.spacing[0]);return selected[0];
}
