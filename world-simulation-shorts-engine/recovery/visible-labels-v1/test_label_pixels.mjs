/** NEW label-layer CPU pixel tests only. No existing suite, GPU or browser run. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire,syncBuiltinESMExports} from 'node:module';
import {fileURLToPath} from 'node:url';
import {projectBounds} from '../universal-presentation-v2/presentation_plan.mjs';
import {validateLabelSpec} from '../universal-presentation-v2/presentation_labels.mjs';
import {layoutLabels,paintLabels,createPresentationLabelPass,LABEL_FONT_FAMILY} from '../universal-presentation-v2/presentation_label_layer.mjs';

const require=createRequire(import.meta.url),{createCanvas,GlobalFonts}=require('@napi-rs/canvas');
const HERE=path.dirname(fileURLToPath(import.meta.url)),EVIDENCE=path.join(HERE,'evidence');
await fs.mkdir(EVIDENCE,{recursive:true});
const FONT=path.resolve(HERE,'../../web/fonts/NotoSansCJKkr-Bold.otf');
const EXPECTED_FONT='da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0';
const fontBytes=await fs.readFile(FONT),fontSHA=createHash('sha256').update(fontBytes).digest('hex');
assert.ok(GlobalFonts.registerFromPath(FONT,LABEL_FONT_FAMILY),'pinned font must register');
// Any mistaken attempt to create an external process or network request fails.
const processes=require('node:child_process');
for(const key of ['exec','execFile','spawn','fork','execSync','execFileSync','spawnSync'])processes[key]=()=>{throw Error('PIXEL_TEST_REAL_PROCESS_FORBIDDEN');};
syncBuiltinESMExports();globalThis.fetch=async()=>{throw Error('PIXEL_TEST_NETWORK_FORBIDDEN');};

const W=1080,H=1920,SAFE=[64,96,1016,1824],BOUNDS=[0,0,20,40];
const scene={timing:{fps:30,total_frames:300},locations:[{id:'AREA',anchor:[8,22]},{id:'EVENT',anchor:[12,18]}]};
const highlights=[{id:'event-a',locationId:'EVENT',startFrame:20,endFrame:280}];
const labels=validateLabelSpec({enabled:true,items:[
 {id:'country',role:'COUNTRY',text:'합성 영역',locationId:'AREA',startFrame:0,endFrame:300,revealFrames:4,exitFrames:4},
 {id:'event',role:'EVENT',text:'사건 발생',locationId:'EVENT',eventId:'event-a',startFrame:20,endFrame:280,revealFrames:8,exitFrames:8},
 {id:'value',role:'NUMERIC',text:'120명',locationId:'EVENT',eventId:'event-a',startFrame:20,endFrame:280,revealFrames:8,exitFrames:8}
]},{scene,highlights});
const project=anchor=>projectBounds(BOUNDS,anchor);
const metricCanvas=createCanvas(W,H),metric=metricCanvas.getContext('2d');
const measureText=(text,font)=>{metric.font=font;return metric.measureText(text);};
function layout(extra={}){return layoutLabels({items:labels.items,frame:100,project,width:W,height:H,safeArea:SAFE,measureText,...extra});}
function paint(value){const canvas=createCanvas(value.width,value.height),context=canvas.getContext('2d');paintLabels(context,value);return{canvas,context,pixels:context.getImageData(0,0,value.width,value.height).data};}
function countPixels(data,width,rect,predicate){
 let count=0;for(let y=Math.max(0,Math.ceil(rect[1]));y<Math.min(data.length/4/width,Math.floor(rect[3]));y++)for(let x=Math.max(0,Math.ceil(rect[0]));x<Math.min(width,Math.floor(rect[2]));x++){
  const i=(y*width+x)*4;if(predicate(data[i],data[i+1],data[i+2],data[i+3]))count++;
 }return count;
}
function nonTransparentBounds(data,width){let minX=width,minY=data.length/4/width,maxX=-1,maxY=-1,count=0;
 for(let i=0;i<data.length;i+=4)if(data[i+3]){const n=i/4,x=n%width,y=Math.floor(n/width);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);count++;}
 return{count,bounds:count?[minX,minY,maxX+1,maxY+1]:null};
}
function intersects(a,b){return a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];}
function inside(p,b){return p[0]>=b[0]&&p[0]<=b[2]&&p[1]>=b[1]&&p[1]<=b[3];}
function lineHits(line,rect){for(let i=0;i<=1000;i++){const t=i/1000,p=line[0].map((v,j)=>v+(line[1][j]-v)*t);if(inside(p,rect))return true;}return false;}
const cases=[],observations={};
function check(name,fn){cases.push({name,fn});}

check('01_exact_pinned_korean_font_and_real_country_glyph_pixels',async()=>{
 assert.equal(fontSHA,EXPECTED_FONT);assert.equal(fontBytes.length,16997968);
 const value=layout({items:[labels.items[0]]}),result=paint(value),row=value.drawn[0],inner=[row.box[0]+8,row.box[1]+8,row.box[2]-8,row.box[3]-8];
 const white=countPixels(result.pixels,W,inner,(r,g,b,a)=>a>240&&r>240&&g>240&&b>240);
 const dark=countPixels(result.pixels,W,inner,(r,g,b,a)=>a>240&&r<80&&g<80&&b<80);
 assert.ok(white>1500);assert.ok(dark>180,'Korean text must contribute dark pixels inside the white plate, excluding border');
 observations.country={whiteInteriorPixels:white,darkGlyphInteriorPixels:dark,box:row.box};
});
check('02_event_and_numeric_text_have_actual_white_fill_and_dark_outline',()=>{
 const out={};for(const role of ['EVENT','NUMERIC']){
  const item=labels.items.find(r=>r.role===role),value=layout({items:[item]}),result=paint(value),row=value.drawn[0];
  const white=countPixels(result.pixels,W,row.box,(r,g,b,a)=>a>230&&r>235&&g>235&&b>235);
  const dark=countPixels(result.pixels,W,row.box,(r,g,b,a)=>a>230&&r<80&&g<80&&b<80);
  assert.ok(white>120,role+' has no visible white glyphs');assert.ok(dark>120,role+' has no actual dark outline');out[role]={whiteGlyphPixels:white,darkOutlinePixels:dark};
 }observations.eventNumeric=out;
});
check('03_yellow_pin_has_dark_center_and_thin_anchor_connector_pixels',()=>{
 const value=layout({items:[labels.items[0]]}),row=value.drawn[0],result=paint(value);
 assert.equal(row.pinDrawn,true);
 const yellow=countPixels(result.pixels,W,row.pinBox,(r,g,b,a)=>a>200&&r>220&&g>140&&b<100);assert.ok(yellow>120);
 const x=Math.round(row.projected[0]),y=Math.round(row.projected[1]-21),i=(y*W+x)*4;
 assert.ok(result.pixels[i+3]>240&&result.pixels[i]<80&&result.pixels[i+1]<80&&result.pixels[i+2]<80);
 assert.deepEqual(row.connector[1],row.projected);assert.ok(Math.hypot(...row.connector[0].map((v,j)=>v-row.connector[1][j]))>20);
 observations.pin={yellowPixels:yellow,darkCenterRGBA:Array.from(result.pixels.slice(i,i+4)),connector:row.connector};
});
check('04_existing_projection_pan_zoom_and_slot_hysteresis_do_not_drift',()=>{
 let previous=null;const baselineSlots=[];let maximumAnchorError=0;
 for(let f=100;f<112;f++){
  const p=point=>projectBounds([(f-100)*.01,0,20+(f-100)*.01,40],point);
  const value=layout({frame:f,project:p,previousLayout:previous});assert.equal(value.drawn.length,3);
  for(const row of value.drawn){const expected=p(row.anchor);maximumAnchorError=Math.max(maximumAnchorError,Math.hypot(...row.projected.map((x,j)=>x-expected[j])));}
  if(previous)assert.deepEqual(value.slots,previous.slots,'a still-valid placement must not flip between slots');
  baselineSlots.push(value.slots);previous=value;
 }
 const zoom=point=>projectBounds([3,8,17,32],point),value=layout({project:zoom});
 for(const row of value.drawn)assert.deepEqual(row.projected,zoom(row.anchor));
 assert.equal(maximumAnchorError,0);observations.motion={frames:12,maximumAnchorError,stableSlots:true};
});
check('05_priority_collision_repositions_and_suppresses_without_event_occlusion',()=>{
 const anchor=project(labels.items[1].anchor),protectedBox=[anchor[0]-20,anchor[1]-20,anchor[0]+20,anchor[1]+20];
 const items=Array.from({length:16},(_,i)=>({...labels.items[i===0?1:0],id:'overlap-'+String(i).padStart(2,'0'),anchor:[...labels.items[1].anchor],locationId:'EVENT',priority:i===0?100:30}));
 const value=layout({items,protectedBoxes:[protectedBox]});assert.ok(value.drawn.some(x=>x.id==='overlap-00'));
 assert.ok(value.suppressed.some(x=>x.reason==='OVERLAP_WITH_HIGHER_PRIORITY_OR_PRIMARY_EVENT'));
 for(const row of value.drawn){assert.equal(intersects(row.box,protectedBox),false);assert.equal(row.pinDrawn,false);assert.equal(lineHits(row.connector,protectedBox),false);}
 for(let i=0;i<value.drawn.length;i++)for(let j=i+1;j<value.drawn.length;j++)assert.equal(intersects(value.drawn[i].box,value.drawn[j].box),false);
 observations.collision={visible:value.drawn.length,suppressed:value.suppressed.length,primaryEventUnoccluded:true};
});
check('06_later_lower_priority_labels_never_cover_earlier_pin_pixels',()=>{
 const event=labels.items[1],items=[event,...Array.from({length:8},(_,i)=>({...labels.items[0],id:'country-'+i,locationId:'OTHER-'+i,anchor:[11.5+i*.15,15.3+i*.15]}))];
 const value=layout({items}),high=value.drawn.find(r=>r.id===event.id);assert.ok(high?.pinDrawn);
 for(const row of value.drawn.filter(r=>r.id!==event.id)){
  assert.equal(intersects(row.box,high.pinBox),false);assert.equal(lineHits(row.connector,high.pinBox),false);
  if(row.pinBox)assert.equal(intersects(row.pinBox,high.pinBox),false);
 }
});
check('07_reveal_hold_exit_use_scene_frames_and_leave_no_residual_pixels',()=>{
 const item={...labels.items[1],startFrame:20,endFrame:80,revealFrames:10,exitFrames:10};
 const alpha=[];for(const frame of [19,20,29,40,70,79,80]){const value=layout({items:[item],frame}),result=paint(value);alpha.push(value.drawn[0]?.alpha??0);if(frame===19||frame===80)assert.equal(nonTransparentBounds(result.pixels,W).count,0);}
 assert.deepEqual(alpha,[0,.1,1,1,1,.1,0]);observations.timing={frames:[19,20,29,40,70,79,80],alpha};
});
check('08_safe_viewport_edges_and_responsive_canvas_keep_all_pixels_inside',()=>{
 const edge=layout({items:[labels.items[0]],project:()=>[SAFE[0],SAFE[1]]}),result=paint(edge),bounds=nonTransparentBounds(result.pixels,W).bounds;
 if(bounds){assert.ok(bounds[0]>=SAFE[0]&&bounds[1]>=SAFE[1]&&bounds[2]<=SAFE[2]&&bounds[3]<=SAFE[3],JSON.stringify({bounds,safe:SAFE}));}
 const half=layout({width:540,height:960,safeArea:[32,48,508,912],project:p=>project(p).map(x=>x/2)}),small=paint(half);
 assert.equal(half.visibleCount,3);assert.ok(nonTransparentBounds(small.pixels,540).count>300);
 for(const row of half.drawn)assert.ok(row.fontSize>=10&&row.fontSize<=30);
});
check('09_offscreen_or_unsupported_projection_is_not_fabricated',()=>{
 const off=layout({project:()=>[-100,900]});assert.equal(off.visibleCount,0);assert.ok(off.suppressed.every(x=>x.reason==='ANCHOR_OUTSIDE_SAFE_VIEWPORT'));
 assert.throws(()=>layout({project:()=>[NaN,0]}),/UP2_LABEL_PROJECTION_UNSUPPORTED/);
 assert.throws(()=>layout({project:()=>{throw Error('unsupported');}}),/UP2_LABEL_PROJECTION_UNSUPPORTED/);
});
check('10_compositor_uses_y_down_texture_same_framebuffer_and_owned_disposal',()=>{
 const resources={textures:[],materials:[],geometries:[],cameras:[],renders:0,resets:0};
 class Texture{constructor(canvas){this.canvas=canvas;resources.textures.push(this);}dispose(){this.disposed=true;}}
 class Geometry{constructor(...args){this.args=args;resources.geometries.push(this);}dispose(){this.disposed=true;}}
 class Material{constructor(options){Object.assign(this,options);resources.materials.push(this);}dispose(){this.disposed=true;}}
 class Mesh{constructor(geometry,material){this.geometry=geometry;this.material=material;this.position={set:(...args)=>this.positionValue=args};}}
 class Scene{constructor(){this.objects=[];}add(mesh){this.objects.push(mesh);}}
 class Camera{constructor(...args){this.args=args;this.position={};resources.cameras.push(this);}updateMatrixWorld(){this.updated=true;}}
 const THREE={CanvasTexture:Texture,PlaneGeometry:Geometry,MeshBasicMaterial:Material,Mesh,Scene,OrthographicCamera:Camera,LinearFilter:'linear',NoColorSpace:'none',DoubleSide:'double'};
 const renderer={autoClear:false,getRenderTarget:()=>null,resetState:()=>resources.resets++,render:()=>resources.renders++};
 const pass=createPresentationLabelPass({renderer,THREE,canvasFactory:createCanvas});
 assert.equal(resources.textures[0].flipY,false);assert.equal(resources.materials[0].transparent,true);assert.equal(resources.materials[0].depthWrite,false);assert.equal(resources.materials[0].depthTest,false);assert.equal(resources.materials[0].side,'double');
 assert.deepEqual(resources.cameras[0].args,[0,W,0,H,.1,10]);assert.equal(resources.cameras[0].position.z,5);assert.equal(resources.cameras[0].updated,true);
 const output=pass.draw({labels,scene,frame:100,project,safeArea:SAFE});assert.equal(output.visibleCount,3);assert.equal(resources.renders,1);assert.ok(resources.textures[0].needsUpdate);
 renderer.getRenderTarget=()=>({});assert.throws(()=>pass.draw({labels,scene,frame:101,project,safeArea:SAFE}),/UP2_LABEL_CURRENT_FRAMEBUFFER_REQUIRED/);
 pass.dispose();pass.dispose();assert.ok(resources.textures[0].disposed&&resources.materials[0].disposed&&resources.geometries[0].disposed);
 assert.throws(()=>createPresentationLabelPass({renderer:{...renderer,autoClear:true},THREE,canvasFactory:createCanvas}),/UP2_LABEL/);
 observations.compositor={actualGPUExecuted:false,transparent:true,flipY:false,sameFramebufferRequired:true,autoClearDisabledRequired:true};
});
check('11_unsupported_raw_glyphs_cannot_use_an_ambient_fallback_font',()=>{
 for(const text of ['🙂','<script>','한글\u200b숨김'])assert.throws(()=>layout({items:[{...labels.items[0],text}]}),/LABEL/);
});

const selected=process.argv[2]?new Set(process.argv[2].split(',')):null,results=[];
for(const row of cases){if(selected&&!selected.has(row.name.slice(0,2)))continue;try{await row.fn();results.push({name:row.name,status:'PASS'});console.log('LABEL_PIXEL_CASE_PASS='+row.name);}catch(error){results.push({name:row.name,status:'BLOCKED',error:String(error?.message??error).slice(0,700)});console.log('LABEL_PIXEL_CASE_BLOCKED='+JSON.stringify(results.at(-1)));}}
const report={schema:'WORLD_ENGINE_NEW_LABEL_CPU_PIXEL_TESTS_V1',status:results.every(x=>x.status==='PASS')?'PASS':'BLOCKED',cases:results,passed:results.filter(x=>x.status==='PASS').length,failed:results.filter(x=>x.status!=='PASS').length,font:{path:'world-simulation-shorts-engine/web/fonts/NotoSansCJKkr-Bold.otf',sha256:fontSHA,expectedSHA256:EXPECTED_FONT,bytes:fontBytes.length,familyAlias:LABEL_FONT_FAMILY},observations,scope:'NEW_LABEL_CPU_CANVAS_ONLY_NO_MAP_RENDER_OR_GPU_PARITY',actualGPUExecuted:false,existingPASSSuitesReexecuted:false};
await fs.writeFile(path.join(EVIDENCE,selected?'new-label-pixels-targeted.json':'new-label-pixels-initial.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:report.status,passed:report.passed,failed:report.failed,gpuExecuted:false,scope:report.scope}));
if(report.failed)process.exitCode=1;
