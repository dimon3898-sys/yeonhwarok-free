/** CPU-only actual label consumer evidence; this is NOT a map/GPU renderer. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {projectBounds} from '../universal-presentation-v2/presentation_plan.mjs';
import {validateLabelSpec} from '../universal-presentation-v2/presentation_labels.mjs';
import {layoutLabels,paintLabels,LABEL_FONT_FAMILY} from '../universal-presentation-v2/presentation_label_layer.mjs';

const require=createRequire(import.meta.url),{createCanvas,GlobalFonts}=require('@napi-rs/canvas');
const here=path.dirname(fileURLToPath(import.meta.url)),evidence=path.join(here,'evidence');
await fs.mkdir(evidence,{recursive:true});
const fontFile=path.resolve(here,'../../web/fonts/NotoSansCJKkr-Bold.otf'),font=await fs.readFile(fontFile);
const fontSHA=createHash('sha256').update(font).digest('hex');
assert.equal(fontSHA,'da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0');
assert.ok(GlobalFonts.registerFromPath(fontFile,LABEL_FONT_FAMILY));
const samplePath=path.join(here,'GENERIC_LABELS_10S.json'),sampleRaw=await fs.readFile(samplePath),input=JSON.parse(sampleRaw);
assert.equal(input.schema,'WORLD_ENGINE_PRESENTATION_PROMPT_V2');assert.equal(input.data.durationSeconds,10);
const compiledRaw=await fs.readFile(path.join(evidence,'COMPILED_LABEL_PREVIEW_INPUT.json')),compiled=JSON.parse(compiledRaw);
assert.equal(compiled.schema,'WORLD_ENGINE_CPU_LABEL_PREVIEW_INPUT_V1');assert.equal(compiled.gpuExecuted,false);
const WIDTH=1080,HEIGHT=1920,SAFE=[64,96,1016,1824],frames=[15,60,210,255],records=[],panels=[];

function cameraAt(keys,frame){
 let left=keys[0],right=keys.at(-1);for(let i=1;i<keys.length;i++)if(frame<=keys[i].frame){left=keys[i-1];right=keys[i];break;}
 const t=Math.max(0,Math.min(1,(frame-left.frame)/Math.max(1,right.frame-left.frame)));
 return{center:left.center.map((v,i)=>v+(right.center[i]-v)*t),zoom:left.zoom+(right.zoom-left.zoom)*t};
}
for(const globalFrame of frames){
 const segment=compiled.scenes.find(s=>globalFrame>=s.startFrame&&globalFrame<s.endFrame),frame=globalFrame-segment.startFrame;
 const presentation={camera:segment.camera,labels:segment.labels,highlights:segment.highlights};
 const scene={timing:{fps:30,total_frames:segment.endFrame-segment.startFrame},locations:segment.locations};
 const labels=validateLabelSpec(presentation.labels,{scene,highlights:presentation.highlights});
 const key=cameraAt(presentation.camera.keyframes,frame),base=input.region.bbox;
 // Explicit region-bbox test view. It is not the source-qualified native camera
 // footprint and must not be described as full presentation/GPU visual evidence.
 const span=[base[2]-base[0],base[3]-base[1]].map(v=>v/key.zoom),bounds=[key.center[0]-span[0]/2,key.center[1]-span[1]/2,key.center[0]+span[0]/2,key.center[1]+span[1]/2];
 const project=point=>projectBounds(bounds,point),canvas=createCanvas(WIDTH,HEIGHT),ctx=canvas.getContext('2d');
 ctx.fillStyle='#243642';ctx.fillRect(0,0,WIDTH,HEIGHT);
 ctx.strokeStyle='#3e5361';ctx.lineWidth=1;
 for(let x=0;x<=WIDTH;x+=120){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,HEIGHT);ctx.stroke();}
 for(let y=0;y<=HEIGHT;y+=120){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(WIDTH,y);ctx.stroke();}
 // Schematic fixture outlines use supplied geometry only; no terrain is faked.
 const geometry=segment.geometry.find(g=>g.id==='COUNTRY_NAM')?.geometry;
 const polygons=geometry?.type==='Polygon'?[geometry.coordinates]:geometry?.type==='MultiPolygon'?geometry.coordinates:[];
 ctx.beginPath();for(const polygon of polygons)for(const ring of polygon){ring.forEach((point,i)=>{const p=project(point);if(i)ctx.lineTo(...p);else ctx.moveTo(...p);});ctx.closePath();}
 ctx.fillStyle='#4d635b';ctx.fill('evenodd');ctx.strokeStyle='#90a297';ctx.lineWidth=2;ctx.stroke();
 const protectedBoxes=[];
 for(const event of presentation.highlights){
  if(frame<event.startFrame||frame>=event.endFrame)continue;
  const location=scene.locations.find(l=>l.id===event.locationId),p=project(location.anchor);
  protectedBoxes.push([p[0]-20,p[1]-20,p[0]+20,p[1]+20]);ctx.beginPath();ctx.arc(p[0],p[1],15,0,Math.PI*2);ctx.fillStyle='#e35d48';ctx.fill();ctx.strokeStyle='#fee7dc';ctx.lineWidth=3;ctx.stroke();
 }
 const overlay=createCanvas(WIDTH,HEIGHT),c=overlay.getContext('2d');
 const layout=layoutLabels({items:labels.items,frame,project,width:WIDTH,height:HEIGHT,safeArea:SAFE,protectedBoxes,
  measureText:(text,fontValue)=>{c.font=fontValue;return c.measureText(text);}});
 paintLabels(c,layout);ctx.drawImage(overlay,0,0);
 ctx.strokeStyle='#92a0aa';ctx.lineWidth=1;ctx.setLineDash([7,7]);ctx.strokeRect(...[SAFE[0],SAFE[1],SAFE[2]-SAFE[0],SAFE[3]-SAFE[1]]);ctx.setLineDash([]);
 ctx.fillStyle='rgba(13,24,32,.92)';ctx.fillRect(0,0,WIDTH,90);ctx.fillStyle='#fff';ctx.font=`30px "${LABEL_FONT_FAMILY}"`;ctx.fillText('CPU LABEL LAYER / PROVIDED GEOMETRY FIXTURE',28,38);ctx.font=`24px "${LABEL_FONT_FAMILY}"`;ctx.fillText(`frame ${globalFrame} | ${segment.sceneId} | no GPU / no terrain render`,28,72);
 const name=`LABEL_CPU_FRAME_${String(globalFrame).padStart(3,'0')}.png`,bytes=canvas.toBuffer('image/png');await fs.writeFile(path.join(evidence,name),bytes);
 records.push({file:name,sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length,globalFrame,localFrame:frame,sceneId:segment.sceneId,projectionFixture:{owner:'EXISTING_projectBounds',bounds,cameraFootprintScope:'REGION_BBOX_TEST_VIEW_NOT_QUALIFIED_NATIVE_CAMERA'},visibleCount:layout.visibleCount,drawn:layout.drawn,suppressed:layout.suppressed});panels.push(canvas);
}
const sheet=createCanvas(1140,2180),ctx=sheet.getContext('2d');ctx.fillStyle='#111b23';ctx.fillRect(0,0,sheet.width,sheet.height);ctx.fillStyle='#fff';ctx.font=`30px "${LABEL_FONT_FAMILY}"`;ctx.fillText('WORLD ENGINE - CPU LABEL LAYER ONLY',24,42);ctx.font=`21px "${LABEL_FONT_FAMILY}"`;ctx.fillText('Actual pinned Korean font + input label metadata; schematic provided-geometry view.',24,77);ctx.fillText('NO GPU / NO TERRAIN CAPTURE / NO REFERENCE-PARITY CLAIM',24,108);
for(let i=0;i<panels.length;i++){const x=20+(i%2)*560,y=140+Math.floor(i/2)*1010;ctx.drawImage(panels[i],x,y,540,960);ctx.fillStyle='#fff';ctx.font=`22px "${LABEL_FONT_FAMILY}"`;ctx.fillText(`frame ${frames[i]} - visible labels ${records[i].visibleCount}`,x,y+991);}
const bytes=sheet.toBuffer('image/png');await fs.writeFile(path.join(evidence,'LABEL_CPU_CONTACT_SHEET.png'),bytes);
const report={schema:'WORLD_ENGINE_LABEL_CPU_CONTACT_SHEET_V1',status:'PASS_CPU_LAYER_EVIDENCE_ONLY',sampleFile:'GENERIC_LABELS_10S.json',sampleSHA256:createHash('sha256').update(sampleRaw).digest('hex'),compiledInput:'COMPILED_LABEL_PREVIEW_INPUT.json',compiledInputSHA256:createHash('sha256').update(compiledRaw).digest('hex'),fontSHA256:fontSHA,frames:records,contactSheet:{file:'LABEL_CPU_CONTACT_SHEET.png',sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length},actualGPUExecuted:false,actualTerrainRendered:false,nativeCameraQualificationPerformed:false,referenceParityClaimed:false,existingPASSReexecuted:false};
await fs.writeFile(path.join(evidence,'CPU_CONTACT_SHEET_RECEIPT.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:report.status,frames:records.map(r=>({frame:r.globalFrame,labels:r.visibleCount})),contactSheet:report.contactSheet,actualGPUExecuted:false}));
