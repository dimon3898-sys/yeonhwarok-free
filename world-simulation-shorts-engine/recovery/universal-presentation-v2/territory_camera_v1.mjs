/** Source-qualified camera choreography driven by the existing continuous shapes.
 * Never changes scene dates, topology, historical route evidence, or event timing. */
import {continuousTerritoryAt} from './continuous_territory_runtime.mjs';
import {boundsOf,multi,areaKm2,geometry} from './territory_delta_v2.mjs';
import {geographicCameraFrame,compileGeographicCamera,mercatorY,inverseMercatorY,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
const copy=structuredClone,clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*x*(10+x*(-15+6*x));};
const mix=(a,b,t)=>({center:[a.center[0]+(b.center[0]-a.center[0])*t,inverseMercatorY(mercatorY(a.center[1])+(mercatorY(b.center[1])-mercatorY(a.center[1]))*t)],scale:Math.exp(Math.log(a.scale)+(Math.log(b.scale)-Math.log(a.scale))*t),rollDegrees:0});
export function compileFrontierCamera({scene,territoryChanges,timingAudit,sourceLevels,closestBounds,initialPose,resultPoses,changeMetrics}){
 const frames=Array(scene.timing.total_frames),keys=[],cycles=[];let previous=null;
 for(const [i,c] of timingAudit.choreography.entries()){
  const target=copy(resultPoses[i]),item=territoryChanges.items[i],metric=changeMetrics[i];
  const parts=multi(item.added).concat(multi(item.removed)),areas=parts.map(p=>areaKm2(geometry([p]))),sum=areas.reduce((a,b)=>a+b,0);
  const significant=areas.filter(a=>a>=sum*.01).length,quiet=metric.ratio<.005;
  const wantedZoom=quiet?1:1+Math.min(.72,1.8*Math.sqrt(metric.ratio))*(significant>3?.65:1);
  const states=Array.from({length:c.readEnd-c.cycleStart},(_,j)=>continuousTerritoryAt(territoryChanges,c.cycleStart+j));
  // Smooth the geometry-derived focus itself before applying an envelope. The
  // band can appear/disappear at event endpoints without a one-frame camera kick.
  const raw=states.map(s=>{const b=boundsOf(s.boundaryBand);return b?[(b[0]+b[2])/2,(mercatorY(b[1])+mercatorY(b[3]))/2]:null;});
  const focus=raw.map((_,j)=>{let x=0,y=0,w=0;for(let k=Math.max(0,j-10);k<=Math.min(raw.length-1,j+10);k++)if(raw[k]){const q=11-Math.abs(k-j);x+=raw[k][0]*q;y+=raw[k][1]*q;w+=q;}return w?[x/w,y/w]:null;});
  let accepted=null;
  // Qualification is global for the entire cycle. A frame never independently
  // jumps to a different fallback pose or changes its zoom/tracking strength.
  for(const zoomWeight of [1,.8,.6,.4,.2,0]){
   for(const tracking of quiet?[0]:[.12,.08,.04,0]){
    const start=previous?copy(previous):copy(initialPose),zoom=1+(wantedZoom-1)*zoomWeight;
    if(!previous)start.scale=target.scale/zoom;
    const candidate=states.map((s,j)=>{
     const f=c.cycleStart+j,t=clamp((f-c.cameraStart)/Math.max(1,c.cameraEnd-c.cameraStart)),pose=mix(start,target,ease(t));
     const local=clamp((f-c.startFrame)/Math.max(1,c.endFrame-c.startFrame-1)),envelope=Math.sin(Math.PI*local)**4;
     if(focus[j]&&f>=c.startFrame&&f<c.endFrame&&tracking){pose.center[0]+=(focus[j][0]-pose.center[0])*tracking*envelope;pose.center[1]=inverseMercatorY(mercatorY(pose.center[1])+(focus[j][1]-mercatorY(pose.center[1]))*tracking*envelope);}
     if(f>=c.cameraEnd)return copy(target);return pose;
    });
    try{
     for(const [j,pose]of candidate.entries()){
      const view=geographicCameraFrame(pose);selectGeographicTerrain(sourceLevels,pose,{maximumTextureSize:8192});
      if(closestBounds){const b=view.flatBounds;if(1080/pose.scale<closestBounds[2]-closestBounds[0]-1e-8||b[3]-b[1]<closestBounds[3]-closestBounds[1]-1e-8)throw Error('CAMERA_DETAIL_LIMIT');}
      if(!multi(states[j].geometry).flat(2).every(pt=>{const q=view.project(pt);return q[0]>=60&&q[0]<=1020&&q[1]>=160&&q[1]<=1740;}))throw Error('CAMERA_TERRITORY_SAFE_FRAME');
     }
     accepted={candidate,zoom,tracking,zoomWeight};break;
    }catch(error){if(!/GEOGRAPHIC_|CAMERA_/.test(error.message))throw error;}
   }
   if(accepted)break;
  }
  if(!accepted)throw Error('CAMERA_WHOLE_CYCLE_SOURCE_FIT_BLOCKED');
  accepted.candidate.forEach((pose,j)=>frames[c.cycleStart+j]=pose);
  keys.push({frame:c.cycleStart,role:'CONTEXT',pose:copy(frames[c.cycleStart])},{frame:c.cameraEnd,role:'RESULT',pose:copy(target)});
  cycles.push({cycleStart:c.cycleStart,endFrame:c.endFrame,readEnd:c.readEnd,significantRegions:significant,strategy:quiet?'QUIET_RESULT':significant>3?'MULTI_REGION_CONTEXT':'SMOOTH_BOUNDARY_FOLLOW',requestedZoomRatio:wantedZoom,actualZoomRatio:target.scale/frames[c.cycleStart].scale,trackingGain:accepted.tracking,qualification:'WHOLE_CYCLE_NO_PER_FRAME_FALLBACK',holdFrames:c.holdFrames});previous=target;
 }
 const camera={mode:'GEOGRAPHIC_TRACK',projection:'GEOGRAPHIC_MERCATOR_V1',frames};
 compileGeographicCamera(camera,{totalFrames:frames.length,holdFrames:scene.timing.final_hold_frames,closestBounds});
 return{camera,audit:{profile:'SOURCE_QUALIFIED_FRONTIER_CAMERA_V1',cameraKeys:keys,cycles,interpolation:'QUINTIC_EASE_WITH_SMOOTHED_FRONTIER_FOCUS',eventTimingChanged:false,geometryChanged:false,sourceDetailGateRelaxed:false,referenceTiming:copy(timingAudit.reference),limitations:['Zoom and northward framing remain bounded by source density and admitted detail.','Six-second single-event samples retain one approach and a reading hold; no forced zoom-return cycle.']}};
}
