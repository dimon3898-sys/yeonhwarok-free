// Actual font metrics + exact authored overlay + projected 3D aircraft bounds.
import * as THREE from 'three';
import {chromium} from 'playwright';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {geo,clamp,smooth} from '../src/core_v1_preserved.js';
import {CameraController,RouteAnimator,EntityAnimator,CITIES} from '../src/engine_v3.js';
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
let widths;
try{const page=await browser.newPage();await page.goto('http://127.0.0.1:8030/README_V3.md');await page.setContent("<style>@font-face{font-family:V3;src:url('/assets/v3/fonts/OpenSans-Light.ttf');font-weight:300}</style>");widths=await page.evaluate(async()=>{await document.fonts.load('300 100px V3');const c=document.createElement('canvas').getContext('2d');c.font='300 100px V3';return Object.fromEntries([...new Set('SEOULTKYINGAPRCW D')].map(ch=>[ch,c.measureText(ch).width]))})}finally{await browser.close()}
const ease=(t,a,b)=>smooth((t-a)/(b-a)),win=(t,a,b,c,d)=>ease(t,a,b)*(1-ease(t,c,d));
const text=await readFile('src/renderer_v3.js','utf8'),source=text.match(/ overlay\(t\)\{([\s\S]*?)\n drawInsert/)[1];
const overlay=new Function('THREE','geo','clamp','win','ease','CITIES','return function(t){'+source.slice(0,source.lastIndexOf('}'))+'}')(THREE,geo,clamp,win,ease,CITIES);
const ctx={save(){},restore(){},fillText(){},measureText(ch){const size=Number(this.font.match(/([\d.]+)px/)[1]);return {width:widths[ch]*size/100}}};
const routes=new RouteAnimator(),camera=new THREE.PerspectiveCamera(44,9/16,.02,30),rig=new CameraController(camera,routes),entity=new EntityAnimator(routes),w=2160,h=3840;
const state={w,h,ctx,labels:[],project(point){const v=point.clone().project(camera),n=point.clone().normalize();return {x:(v.x*.5+.5)*w,y:(.5-v.y*.5)*h,visible:n.dot(camera.position.clone().sub(point))>0&&v.z<1}}};
const parts=[];entity.model.traverse(m=>{if(!m.isMesh)return;const v=m.geometry.attributes.position,points=[];for(let i=0;i<v.count;i++)points.push(new THREE.Vector3().fromBufferAttribute(v,i));parts.push({mesh:m,points})});
const records=[],clipped=[],collisions=[],labelOverlaps=[],planeOutside=[];let labelFrames=0;
for(let frame=0;frame<600;frame++) {
 const t=frame/30;rig.update(t);entity.update(t,camera);overlay.call(state,t);
 let lo=new THREE.Vector2(Infinity,Infinity),hi=new THREE.Vector2(-Infinity,-Infinity);
 if(entity.model.visible&&entity.model.userData.alpha>.12)for(const part of parts)for(const vertex of part.points){const p=state.project(vertex.clone().applyMatrix4(part.mesh.matrixWorld));lo.min(new THREE.Vector2(p.x,p.y));hi.max(new THREE.Vector2(p.x,p.y))}
 const labels=state.labels;labelFrames+=labels.length?1:0;
 for(const label of labels){if(label.x<0||label.y<0||label.x+label.width>w||label.y+label.height>h)clipped.push({t,label:label.text});if(Number.isFinite(lo.x)&&label.x<hi.x+24&&label.x+label.width>lo.x-24&&label.y<hi.y+24&&label.y+label.height>lo.y-24)collisions.push({t,label:label.text,aircraftBounds:[...lo.toArray(),...hi.toArray()]})}
 for(let i=0;i<labels.length;i++)for(const b of labels.slice(i+1)){const a=labels[i];if(a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y)labelOverlaps.push({t,labels:[a.text,b.text]})}
 if(Number.isFinite(lo.x)&&(lo.x<150||hi.x>2010||lo.y<430||hi.y>3070))planeOutside.push({t,bounds:[...lo.toArray(),...hi.toArray()]});
 records.push({t,labels,aircraftBounds:Number.isFinite(lo.x)?[...lo.toArray(),...hi.toArray()]:null});
}
const hashes={};for(const file of ['src/aircraft_v3.js','src/engine_v3.js','src/renderer_v3.js','tools/layout_preflight_v3.mjs'])hashes[file]=createHash('sha256').update(await readFile(file)).digest('hex');
const report={sourceHashes:hashes,frames:600,internalResolution:[w,h],font:'Open Sans Light 300; actual browser glyph advances',labelFrames,textClipping:clipped,labelAircraftBoundsIntersections:collisions,labelLabelOverlaps:labelOverlaps,aircraftOutsideSafeScene:planeOutside,scope:'Exact current overlay logic, actual font metrics and all projected mesh vertices at nominal frame times; visual review remains required.',records};
const dest=process.argv[2]||'outputs/v3_layout_preflight.json';await writeFile(dest,JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify({...report,records:undefined,sourceHashes:undefined},null,2));if(clipped.length||collisions.length||labelOverlaps.length||planeOutside.length)process.exitCode=1;
