/** New camera tracks only: call the existing viewport gate, no old regression suite. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const [root,preparedDirectory,output]=process.argv.slice(2);
const {presentationAreaViewport,projectBounds}=await import(pathToFileURL(path.join(root,'world-simulation-shorts-engine/recovery/universal-presentation-v2/presentation_plan.mjs')));
let frames=0,stageChecks=0,markerChecks=0,minGutter=Infinity;
const inside=(p,b)=>p[0]>=b[0]&&p[0]<=b[2]&&p[1]>=b[1]&&p[1]<=b[3];
for(const part of [1,2]){
 const prepared=JSON.parse(await fs.readFile(path.join(preparedDirectory,`PREPARED_${part}.json`),'utf8'));
 for(const s of prepared.segments)for(const [f,b]of s.presentationPlan.cpuFrameBounds.entries()){
  const project=p=>projectBounds(b,p),p=s.presentation,source=s.sourceStyle.terrainAsset,safe=s.nativePlan.layout.safe,base=s.nativePlan.layout.measured?.markerSize??s.nativePlan.layout.markerSize;
  const gutter=Math.min((b[0]-source.bounds[0])/source.pixelSpacing[0],(b[1]-source.bounds[1])/source.pixelSpacing[1],(source.bounds[2]-b[2])/source.pixelSpacing[0],(source.bounds[3]-b[3])/source.pixelSpacing[1]);
  minGutter=Math.min(minGutter,gutter);assert(gutter>=1-1e-8,'NEW_CAMERA_SOURCE_GUTTER');
  for(const stage of s.scene.time_steps){
   const areas=s.scene.areas.filter(a=>a.stage_id===stage.id);
   const visibility=areas.map(a=>presentationAreaViewport({geometry:s.scene.geometries.find(g=>g.id===a.geometry_ref).geometry,project,safeArea:safe,presentation:p,allowOffscreenComponents:true}));
   assert(visibility.some(v=>v.visible!==false),'NEW_CAMERA_ACTIVE_STATE_OUTSIDE');stageChecks++;
  }
  for(const h of p.highlights)if(f>=h.startFrame&&f<h.endFrame){
   const at=project(s.scene.locations.find(l=>l.id===h.locationId).anchor),scale=1+.4*Math.sin(Math.PI*(f-h.startFrame)/(h.endFrame-h.startFrame-1)),r=base*scale/2+2;
   assert(inside([at[0]-r,at[1]-r],safe)&&inside([at[0]+r,at[1]+r],safe),'NEW_CAMERA_NATIVE_MARKER_ROI');markerChecks++;
  }
  frames++;
 }
}
await fs.writeFile(output,JSON.stringify({status:'PASS_NEW_CAMERA_COVERAGE',frames,stageChecks,markerChecks,minimumSourceGutterPixels:minGutter,oldPASSReruns:0,gpuStarts:0,mapFramesDrawn:0},null,2)+'\n',{flag:'wx'});
