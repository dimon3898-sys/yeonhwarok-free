/** All-frame changed-input layout diagnostics. Existing layout code; no renderer/encode. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const [root,preparedFile,output,depsRoot]=process.argv.slice(2);
assert([root,preparedFile,output,depsRoot].every(path.isAbsolute));
await fs.mkdir(output,{recursive:false});
const require=createRequire(path.join(depsRoot,'package.json'));
const {createCanvas,GlobalFonts}=require('@napi-rs/canvas');
assert(GlobalFonts.registerFromPath(path.join(root,'world-simulation-shorts-engine/web/fonts/NotoSansCJKkr-Bold.otf'),'Gate1Bold'));
const context=createCanvas(1080,1920).getContext('2d');
const engine=path.join(root,'world-simulation-shorts-engine/recovery/universal-presentation-v2');
const {layoutLabels}=await import(pathToFileURL(path.join(engine,'presentation_label_layer.mjs')));
const {projectBounds,presentationReplacesHighlightMarker,resolvePresentationMarkerLayout}=await import(pathToFileURL(path.join(engine,'presentation_plan.mjs')));
const payload=JSON.parse(await fs.readFile(preparedFile,'utf8'));
assert(payload.totalFrames===300&&payload.segments.length===2);
const frames=[],failures=[];
for(const segment of payload.segments){
 let previous=null;
 const p=segment.presentationPlan.presentation,safe=segment.nativePlan.layout.safe;
 const baseSize=segment.nativePlan.layout.measured?.markerSize??segment.nativePlan.layout.markerSize;
 assert(Number.isFinite(baseSize));
 for(let frame=0;frame<segment.scene.timing.total_frames;frame++){
  const bounds=segment.presentationPlan.cpuFrameBounds[frame],project=point=>projectBounds(bounds,point);
  const markers=(segment.scene.markers??[]).map(row=>({id:row.id,anchor:row.anchor,scale:1}));
  for(const h of p.highlights)if(frame>=h.startFrame&&frame<h.endFrame){
   const loc=segment.scene.locations.find(x=>x.id===h.locationId),progress=(frame-h.startFrame)/(h.endFrame-h.startFrame-1);
   markers.push({id:h.id,locationId:h.locationId,anchor:loc.anchor,scale:1+.4*Math.sin(Math.PI*progress),...(presentationReplacesHighlightMarker(p,h,frame)?{qualityPinCandidate:true}:{})});
  }
  const markerRows=markers.map(row=>{const at=project(row.anchor),r=baseSize*row.scale/2+2;return {...row,box:[at[0]-r,at[1]-r,at[0]+r,at[1]+r]};});
  const prepare=protectedBoxes=>layoutLabels({items:p.labels.items,frame,project,width:1080,height:1920,safeArea:safe,protectedBoxes,previousLayout:previous,measureText:(text,font)=>{context.font=font;return context.measureText(text);}});
  const resolved=resolvePresentationMarkerLayout(markerRows,prepare),layout=resolved.layout??prepare(resolved.markerRows);
  const active=p.labels.items.filter(x=>frame>=x.startFrame&&frame<x.endFrame);
  const suppressed=layout.suppressed.filter(x=>x.reason!=='OUTSIDE_EVENT_TIMING');
  const heroes=active.filter(x=>x.pin==='HERO'),missingHeroes=heroes.filter(x=>!layout.drawn.find(d=>d.id===x.id)?.pinDrawn).map(x=>x.id);
  const row={frame:segment.startFrame+frame,sceneId:segment.sceneId,bounds,active:active.map(x=>x.id),visibleCount:layout.visibleCount,drawn:layout.drawn,suppressed,missingHeroes};
  if(suppressed.length||missingHeroes.length||layout.visibleCount!==active.length||!active.length)failures.push({frame:row.frame,suppressed,missingHeroes,active:row.active,visibleCount:layout.visibleCount});
  frames.push(row);previous=layout;
 }
}
const summary={status:failures.length?'FAIL_CHANGED_INPUT_LAYOUT':'PASS_CHANGED_INPUT_LAYOUT_SKIA',frames:frames.length,
 noActiveLabelFrames:frames.filter(f=>!f.active.length).length,unexpectedSuppressionFrames:failures.length,
 heroVisibleFrames:frames.filter(f=>f.drawn.some(x=>x.pin==='HERO'&&x.pinDrawn)).length,
 measurement:'Existing layout with pinned font via @napi-rs/canvas; Chromium pixels still required',failures,
 gpuStarts:0,renders:0,oldPASSReruns:0,referenceQualityApproved:false};
await fs.writeFile(path.join(output,'LAYOUT_300.json'),JSON.stringify({summary,frames},null,2)+'\n',{flag:'wx'});
await fs.writeFile(path.join(output,'LAYOUT_RESULT.json'),JSON.stringify(summary,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({...summary,failures:failures.slice(0,5)}));
if(failures.length)process.exitCode=1;
