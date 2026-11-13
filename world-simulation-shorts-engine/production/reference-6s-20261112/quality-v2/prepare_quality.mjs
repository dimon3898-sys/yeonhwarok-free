import {loadNative} from './load_native.mjs';
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {execFileSync} from 'node:child_process';
import {compileGeographicCamera,geographicCameraFrame} from '../../../web/map_infographic_v1/geographic_camera_v1.mjs';
const p=path.dirname(fileURLToPath(import.meta.url)),e=path.resolve(p,'../../..'),repo=path.dirname(e),read=f=>JSON.parse(fs.readFileSync(f)),write=(f,v)=>fs.writeFileSync(path.join(p,f),JSON.stringify(v,null,2)+'\n');
const input=read(path.join(p,'../quality-v1/REFERENCE_6S_QUALITY_INPUT.json'));
input.presentation.camera.interpolation={mode:'QUINTIC_C2',knotSpacingFrames:8};
const track=compileGeographicCamera(input.presentation.camera,{totalFrames:180,holdFrames:30});
const b=track.coverageBounds,selected=[];
for(const record of loadNative()){
 const parts=(record.geometry_type??record.type)==='Polygon'?[record.coordinates]:record.coordinates;
 const intersects=parts.some(poly=>{const points=poly.flat(),x=points.map(p=>p[0]),y=points.map(p=>p[1]);return Math.max(...x)>=b[0]&&Math.min(...x)<=b[2]&&Math.max(...y)>=b[1]&&Math.min(...y)<=b[3];});
 if(intersects)selected.push(record);
}
input.presentation.mapStyle.boundaryTrace.countryIds=selected.map(g=>g.id).sort();
input.presentation.mapStyle.boundaryTrace.pathTiming='LENGTH_WEIGHTED';
write('REFERENCE_6S_QUALITY_INPUT.json',input);write('CAMERA_TRACK.json',track);
write('BOUNDARY_SELECTION.json',{method:'All existing native geometry parts whose bbox intersects full camera envelope; conservative superset, no source geometry edit',coverageBounds:b,countries:selected.map(g=>({id:g.id,parts:(g.geometry_type??g.type)==='Polygon'?1:g.coordinates.length})),previousTargetCount:7,newTargetCount:selected.length,sourceGeometryUnchanged:true});
// Needed only by focused source-data checks, not shipped in the runtime image.

const before=input.presentation.camera.frames,after=track.frames,landmarks=[[-5.316,35.889],[-2.938,35.292],[-3.7,40],[0,36]];
const diffs=(a,n)=>n?diffs(a.slice(1).map((v,i)=>v-a[i]),n-1):a;
const metrics=frames=>{const s=frames.map(p=>Math.log(p.scale));return{maxZoomRate:Math.max(...diffs(s,1)),maxZoomJerk:Math.max(...diffs(s,3).map(Math.abs)),rmsZoomJerk:Math.sqrt(diffs(s,3).reduce((s,v)=>s+v*v,0)/(s.length-3))};};
const drift=after.map((pose,f)=>Math.max(...landmarks.map(l=>{const a=geographicCameraFrame(before[f]).project(l),b=geographicCameraFrame(pose).project(l);return Math.hypot(a[0]-b[0],a[1]-b[1]);})));
write('CAMERA_DELTA.json',{before:metrics(before),after:metrics(after),maxLandmarkDriftPixels:Math.max(...drift),maxLandmarkDriftFrame:drift.indexOf(Math.max(...drift)),firstAndLastPosesExact:JSON.stringify(before[0])===JSON.stringify(after[0])&&JSON.stringify(before[149])===JSON.stringify(after[149]),holdExact:after.slice(149).every(p=>JSON.stringify(p)===JSON.stringify(after[149])),curve:track.interpolationEvidence,scope:'New generic camera interpolation only; source sampled measurements preserved as input'});
console.log(JSON.stringify({targets:selected.length,camera:read(path.join(p,'CAMERA_DELTA.json'))}));
