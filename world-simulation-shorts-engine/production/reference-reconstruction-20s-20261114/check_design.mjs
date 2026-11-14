/** New 600-frame design admission only; no old QA suite or render is invoked. */
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateRuntimeRequest} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
import {validatePresentation} from '../../recovery/universal-presentation-v2/presentation_plan.mjs';
import {layoutLabels} from '../../recovery/universal-presentation-v2/presentation_label_layer.mjs';
import {geographicCameraFrame,compileGeographicCamera,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {canonicalJSON} from '../../recovery/universal-presentation-v2/region_source.mjs';
const base=new URL('./',import.meta.url),read=async n=>JSON.parse(await fs.readFile(new URL(n,base))),sha=x=>createHash('sha256').update(x).digest('hex');
const r=await read('AUTHORED_RUNTIME_REQUEST.json'),s=r.segments[0],p=s.presentation,old=await read('../continuous-territory-20261114/RUNTIME_REQUEST.json');
const checks=[];const passed=(name,evidence)=>checks.push({name,status:'PASS',evidence});
assert.equal(r.totalFrames,600);assert.equal(r.durationSeconds,20);assert.equal(s.scene.timing.fps,30);validateRuntimeRequest(r);passed('NEW_600_FRAME_SCENE_RUNTIME_CONTRACT',600);
const phases=(await fs.readFile(new URL('SHOT_PLAN_600F.csv',base),'utf8')).trim().split('\n').slice(1).map(x=>x.match(/^"[^"]+","(\d+)","(\d+)"/).slice(1).map(Number));
let end=0;for(const[a,b]of phases){assert.equal(a,end);assert.ok(b>a);end=b;}assert.equal(end,600);passed('SHOT_COVERAGE_NO_GAP_NO_OVERLAP',phases);
assert.equal(canonicalJSON(p.territoryChanges.items[0].continuous),canonicalJSON(old.segments[0].presentation.territoryChanges.items[0].continuous));
assert.equal(canonicalJSON(s.scene.geometries),canonicalJSON(old.segments[0].scene.geometries));passed('UNCHANGED_SOURCE_AND_106_SHAPE_BINDING',{continuousSHA256:sha(canonicalJSON(p.territoryChanges.items[0].continuous)),count:106,scope:'identity comparison, not regeneration or old topology suite'});
// Required admission of a new timing contract reuses, rather than weakens, validation.
validatePresentation(p,{scene:s.scene,region:s.region});passed('NEW_TERRITORY_AND_LABEL_TIME_BINDING',{start:177,endExclusive:283,labelSwitch:230});
compileGeographicCamera(p.camera,{totalFrames:600,holdFrames:148,closestBounds:s.regionEvidence.fittedBounds});
const font=fileURLToPath(new URL('../../web/fonts/NotoSansCJKkr-Bold.otf',base));
const metrics=JSON.parse(execFileSync('python',['-c',"from PIL import ImageFont;import json,sys;f=ImageFont.truetype(sys.argv[1],1000);print(json.dumps({x:f.getlength(x)/1000 for x in json.loads(sys.argv[2])},ensure_ascii=False))",font,JSON.stringify(p.labels.items.map(x=>x.text))],{encoding:'utf8'}));
const selectedIds=new Set(s.scene.areas.map(x=>x.geometry_ref));
const vertices=s.scene.geometries.filter(x=>selectedIds.has(x.id)).flatMap(x=>x.geometry.coordinates.flat(2));
let worstDensity=0,minGutter=Infinity,minClearance=Infinity,peakScreenSpeed=0,layouts=[],previous=null;
const pointCloud=[...vertices];
for(let f=0;f<600;f++){
 const pose=p.camera.frames[f],c=geographicCameraFrame(pose),level=selectGeographicTerrain(s.regionEvidence.sourceLevels,pose);
 worstDensity=Math.max(worstDensity,...level.density);minGutter=Math.min(minGutter,level.gutter);
 const pts=pointCloud.map(c.project);for(const [x,y]of pts){assert.ok(x>=72&&x<=1008&&y>=320&&y<=1320,'NEW_CAMERA_SOURCE_VERTEX_OUTSIDE_SAFE '+f);minClearance=Math.min(minClearance,x-72,1008-x,y-320,1320-y);}
 const bounds=[Math.min(...pts.map(x=>x[0])),Math.min(...pts.map(x=>x[1])),Math.max(...pts.map(x=>x[0])),Math.max(...pts.map(x=>x[1]))];
 const layout=layoutLabels({items:p.labels.items,frame:f,project:c.project,safeArea:[32,32,1048,1888],protectedBoxes:[bounds],measureText:(text,font)=>metrics[text]*parseFloat(font),previousLayout:previous});
 assert.equal(layout.drawn.length,3,'NEW_LABEL_COLLISION_OR_SUPPRESSION '+f);previous=layout;
 if([0,174,177,229,230,282,283,329,451,599].includes(f))layouts.push({frame:f,drawn:layout.drawn.map(x=>({id:x.id,box:x.box,fontSize:x.fontSize})),territoryBounds:bounds});
 if(f){const prior=geographicCameraFrame(p.camera.frames[f-1]);for(const point of pointCloud){const a=prior.project(point),b=c.project(point);peakScreenSpeed=Math.max(peakScreenSpeed,Math.hypot(a[0]-b[0],a[1]-b[1])*30);}}
}
passed('NEW_CAMERA_CONTINUITY_AND_FULL_SOURCE_VISIBILITY',{frameCount:600,minSafeClearancePixels:minClearance,peakSourceVertexSpeedPixelsPerSecond:peakScreenSpeed,interpolation:'C2_QUINTIC',noRoll:true});
passed('NEW_CAMERA_NATIVE_SOURCE_DENSITY',{maximum:worstDensity,minimumGutterPixels:minGutter});
passed('NEW_LABEL_GLYPH_METRICS_AND_600_LAYOUTS',{fontSHA256:sha(await fs.readFile(font)),metricsOwner:'Pillow/FreeType actual bundled font; browser raster result PENDING_GPU',layouts});
const result={schema:'WORLD_ENGINE_600_DESIGN_PREFLIGHT_V1',status:'PASS_NEW_DESIGN_ONLY',checks,oldPassReruns:0,geometryCompilations:0,gpuStarts:0,renderedFrames:0,GPUInputSchema:'PENDING_FORMAL_GPU_CONNECTION',visualQualityApproved:false};
await fs.writeFile(new URL('DESIGN_PREFLIGHT.json',base),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:result.status,checks:checks.length,maximumSourceDensity:worstDensity,peakScreenSpeed,minSafeClearancePixels:minClearance}));
