/** Test-only CPU Canvas2D preview. Never invokes WebGL or production scene rendering. */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const app=path.resolve('.'),repo=path.resolve('..'),args=process.argv.slice(2);
const value=key=>{const index=args.indexOf(key);return index<0?null:args[index+1];};
const planFile=value('--plan');if(!planFile)throw Error('Provide --plan with actual selected v023 scene plan');
const output=path.resolve(value('--output')||'/tmp/world-bold-v023/canvas-preview');
const plan=JSON.parse(fs.readFileSync(planFile));
const require=createRequire(path.join(repo,'cinematic-world-map/package.json')),{chromium}=require('playwright');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const files={
 '/three.js':path.join(repo,'cinematic-world-map/node_modules/three/build/three.module.js'),
 '/infographic.js':path.join(app,'web/infographic_adapter.js'),
 '/bold.js':path.join(app,'web/bold_infographic_adapter.js'),
 '/metrics.mjs':path.join(app,'tools/bold_pixel_metrics_v023.mjs'),
 '/single.js':path.join(app,'web/single_event_camera.js'),
 '/return.js':path.join(app,'web/return_wide_camera.js'),
 '/second.js':path.join(app,'web/second_event_camera.js'),
 '/registry.json':path.join(app,'web/infographic/v022/registry.json'),
 '/profile.json':path.join(app,'web/infographic/v023/bold_profile.json'),
 '/legacy_profile.json':path.join(app,'web/infographic/v022/profile.json'),
 '/manifest.json':path.join(app,'web/earth-detail/v018/manifest.json'),
 '/day.jpg':path.join(repo,'cinematic-world-map/assets/v3/earth/earth-day-8k.jpg'),
 '/detail_0.png':path.join(app,'web/earth-detail/v018/detail_0.png'),
 '/detail_1.png':path.join(app,'web/earth-detail/v018/detail_1.png'),
};
const servedBytes=Object.fromEntries(Object.entries(files).map(([url,file])=>[url,fs.readFileSync(file)]));
const pageHTML='<meta charset="utf-8"><canvas id="frame" width="1080" height="1920"></canvas>';
const server=http.createServer((request,response)=>{
 if(request.url==='/'){response.setHeader('Content-Type','text/html');response.end(pageHTML);return;}
 if(request.url==='/plan.json'){response.setHeader('Content-Type','application/json');response.end(JSON.stringify(plan));return;}
 const file=files[request.url];if(!file){response.writeHead(404);response.end();return;}
 try{response.setHeader('Content-Type',file.endsWith('.js')||file.endsWith('.mjs')?'text/javascript':file.endsWith('.json')?'application/json':file.endsWith('.jpg')?'image/jpeg':'image/png');response.end(servedBytes[request.url]);}
 catch{response.writeHead(500);response.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));fs.mkdirSync(output,{recursive:true});let browser;
try{
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu','--disable-gpu-compositing']});
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;globalThis.__boldWebGLAttempts=0;HTMLCanvasElement.prototype.getContext=function(kind,...rest){if(/webgl/i.test(String(kind))){globalThis.__boldWebGLAttempts++;throw Error('BOLD_PREVIEW_GPU_CONTEXT_FORBIDDEN');}return original.call(this,kind,...rest);};});await page.goto(`http://127.0.0.1:${server.address().port}/`);
 const receipt=await page.evaluate(async()=>{
  const THREE=await import('/three.js'),metrics=await import('/metrics.mjs');
  const strip=source=>source.replace(/^import .*;\s*$/gm,'').replace(/^export /gm,'');
  const get=async file=>(await fetch(file)).text();
  const infographic=new Function('THREE','SceneStoryProgressionRenderer','SceneProductionEarthRenderer','createStoryProgressionRenderer','characterRevealState','markerPopState','digestBytes','trustedStaticURL',strip(await get('/infographic.js'))+'\nreturn {prepareInfographicGeometry,projectInfographicGeometry};')(THREE,class{},class{},()=>{},()=>{},()=>{},()=>{},()=>{});
  const single=new Function('THREE','SceneProductionEarthRenderer',strip(await get('/single.js'))+'\nreturn {singleCameraValues,installSingleCamera};')(THREE,class{});
  const returning=new Function('singleCameraValues','installSingleCamera','SceneSingleEventRenderer',strip(await get('/return.js'))+'\nreturn {returnCameraValues,installReturnCamera};')(single.singleCameraValues,single.installSingleCamera,class{});
  const second=new Function('THREE','returnCameraValues','installReturnCamera','SceneReturnWideRenderer',strip(await get('/second.js'))+'\nreturn {installSecondCamera,secondCameraState};')(THREE,returning.returnCameraValues,returning.installReturnCamera,class{});
  const boldSource=await get('/bold.js');
  // Bind real production helpers while replacing only unused GPU renderer parents.
  const bold=new Function('THREE','prepareInfographicGeometry','projectInfographicGeometry','SceneInfographicRenderer','SceneProductionInfographicRenderer','createInfographicRenderer','validateInfographicSelection','digestBytes','trustedStaticURL',strip(boldSource)+'\nreturn {drawBoldRegionLayer,boldRegionStyle,validateBoldProfile};')(THREE,infographic.prepareInfographicGeometry,infographic.projectInfographicGeometry,class{},class{},()=>{},()=>{},()=>{},()=>{});
  const plan=await(await fetch('/plan.json')).json(),scene=plan.scenes[0],profile=await(await fetch('/profile.json')).json(),registry=await(await fetch('/registry.json')).json(),legacyProfile=await(await fetch('/legacy_profile.json')).json(),manifest=await(await fetch('/manifest.json')).json();
  bold.validateBoldProfile(profile);
  const width=1080,height=1920,canvas=document.getElementById('frame'),ctx=canvas.getContext('2d',{willReadFrequently:true});
  const makeCanvas=()=>{const c=document.createElement('canvas');c.width=width;c.height=height;return c;};
  const image=async(url)=>{const value=new Image();value.src=url;await value.decode();const c=document.createElement('canvas');c.width=value.width;c.height=value.height;const cx=c.getContext('2d',{willReadFrequently:true});cx.drawImage(value,0,0);return {width:c.width,height:c.height,data:cx.getImageData(0,0,c.width,c.height).data};};
  const day=await image('/day.jpg'),detail=[await image('/detail_0.png'),await image('/detail_1.png')];
  const camera={scene:structuredClone(scene),camera:new THREE.PerspectiveCamera(64,width/height,.02,30)};second.installSecondCamera(camera);
  const snapshots=[],cases=[],checks=[],check=(id,condition,detail={})=>{checks.push({id,passed:!!condition,...detail});};
  const captured=(name,c=canvas)=>snapshots.push({name,png:c.toDataURL('image/png')});
  function mapPixels(cam,factor=1){
   const out=new ImageData(width,height),position=cam.position,m=cam.matrixWorld.elements,scale=Math.tan(cam.fov*Math.PI/360),aspect=width/height,C=position.lengthSq()-1;
   const native=manifest.textures.filter(r=>r.role==='regional_day_relief');
   for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const sx=(2*(x+.5)/width-1)*scale*aspect,sy=(1-2*(y+.5)/height)*scale;
    let dx=m[0]*sx+m[4]*sy-m[8],dy=m[1]*sx+m[5]*sy-m[9],dz=m[2]*sx+m[6]*sy-m[10],length=Math.hypot(dx,dy,dz);dx/=length;dy/=length;dz/=length;
    const b=position.x*dx+position.y*dy+position.z*dz,discriminant=b*b-C,index=(y*width+x)*4;
    if(discriminant<0){out.data.set([6,13,22,255],index);continue;}const at=-b-Math.sqrt(discriminant);if(at<0){out.data.set([6,13,22,255],index);continue;}
    const xx=position.x+dx*at,yy=position.y+dy*at,zz=position.z+dz*at,lon=Math.atan2(-zz,xx)*180/Math.PI,lat=Math.asin(Math.max(-1,Math.min(1,yy)))*180/Math.PI;
    let source=day,u=(lon+180)/360,v=(90-lat)/180;
    for(let r=0;r<native.length;r++){const [left,bottom,right,top]=native[r].bounds;if(cam.position.length()-1<.5&&lon>=left&&lon<=right&&lat>=bottom&&lat<=top){source=detail[r];u=(lon-left)/(right-left);v=(top-lat)/(top-bottom);break;}}
    const tx=Math.min(source.width-1,Math.max(0,Math.floor(u*source.width))),ty=Math.min(source.height-1,Math.max(0,Math.floor(v*source.height))),sample=(ty*source.width+tx)*4;
    for(let c=0;c<3;c++)out.data[index+c]=Math.round(source.data[sample+c]*factor);out.data[index+3]=255;
   }return out;
  }
  function polygonMask(projected){const c=makeCanvas(),x=c.getContext('2d');x.fillStyle='#fff';x.beginPath();for(const polygon of projected.polygons){x.moveTo(polygon[0].x,polygon[0].y);for(const p of polygon.slice(1))x.lineTo(p.x,p.y);x.closePath();}x.fill();return c;}
  function draw(projected,role,options={},target=canvas){const x=target.getContext('2d',{willReadFrequently:true}),style=bold.boldRegionStyle(profile,role);return bold.drawBoldRegionLayer(x,projected,style,{...options,width,height});}
  const selections=[['WIDE',75,'COUNTRY_EGY'],['SUEZ_REGIONAL',135,'COUNTRY_EGY'],['SUEZ_EVENT_VIEW',240,'COUNTRY_EGY'],['SINGAPORE_REGIONAL',570,'COUNTRY_SGP'],['SUEZ_DARK_STRESS',240,'COUNTRY_EGY',.25],['SUEZ_BRIGHT_STRESS',240,'COUNTRY_EGY',1.15]];
  for(const [name,frame,id,luminanceStress=1]of selections){
   camera.update(frame/30);const base=mapPixels(camera.camera,luminanceStress);ctx.putImageData(base,0,0);captured(name+'_SOURCE');
   const record=registry.geometries.find(r=>r.id===id),prepared=infographic.prepareInfographicGeometry(record),projected=infographic.projectInfographicGeometry(prepared,camera.camera,width,height),mask=polygonMask(projected),maskPixels=mask.getContext('2d').getImageData(0,0,width,height).data;
   // Geometry-only old v022 comparison; no claim that this is a GPU BEFORE frame.
   ctx.save();ctx.fillStyle=legacyProfile.state_styles.LOCATION.color;ctx.globalAlpha=legacyProfile.geometry.region_fill_alpha*legacyProfile.state_styles.LOCATION.opacity;ctx.beginPath();for(const polygon of projected.polygons){ctx.moveTo(polygon[0].x,polygon[0].y);for(const p of polygon.slice(1))ctx.lineTo(p.x,p.y);ctx.closePath();}ctx.fill();ctx.globalAlpha=legacyProfile.state_styles.LOCATION.opacity;ctx.strokeStyle=legacyProfile.state_styles.LOCATION.color;ctx.lineWidth=id==='COUNTRY_EGY'&&frame>=180?legacyProfile.geometry.secondary_outline_px:legacyProfile.geometry.primary_outline_px;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();for(const [a,b]of projected.segments){ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);}ctx.stroke();ctx.restore();captured(name+'_BEFORE_V022_REGION_LAYER');ctx.putImageData(base,0,0);

   const activeSecondary=(scene.bold_infographic?.regions||[]).filter(r=>r.role==='SECONDARY'&&r.start_frame<=frame&&frame<r.end_frame&&r.primary_geometry_ref===id),secondaryProjected=activeSecondary.map(r=>({selection:r,record:registry.geometries.find(g=>g.id===r.geometry_ref)})).filter(r=>r.record).map(r=>({...r,projected:infographic.projectInfographicGeometry(infographic.prepareInfographicGeometry(r.record),camera.camera,width,height)}));
   for(const entry of secondaryProjected)draw(entry.projected,'SECONDARY');draw(projected,'PRIMARY');const after=ctx.getImageData(0,0,width,height).data;captured(name+'_AFTER_V023_REGION_LAYER');
   const boundary=makeCanvas();draw(projected,'PRIMARY',{drawFill:false},boundary);
   const fill=makeCanvas();draw(projected,'PRIMARY',{drawBoundary:false},fill);
   const primary=metrics.regionPixelMetrics(base.data,after,maskPixels,width,height,{erosion:8,stride:1}),primaryBoundary=metrics.boundaryPixelMetrics(boundary.getContext('2d').getImageData(0,0,width,height).data,width,height,projected.segments,{brightCore:true}),containment=metrics.containmentPixelMetrics(fill.getContext('2d').getImageData(0,0,width,height).data,maskPixels,width,height);
   const off=makeCanvas();off.getContext('2d').putImageData(base,0,0);bold.drawBoldRegionLayer(off.getContext('2d'),projected,null,{width,height});
   const unchanged=metrics.imageDifference(base.data,off.getContext('2d').getImageData(0,0,width,height).data,width,height);
   const secondary=[];for(const entry of secondaryProjected){
    const layer=makeCanvas();layer.getContext('2d').putImageData(base,0,0);draw(entry.projected,'SECONDARY',{drawBoundary:false},layer);
    const smask=polygonMask(entry.projected).getContext('2d').getImageData(0,0,width,height).data,sline=makeCanvas();draw(entry.projected,'SECONDARY',{drawFill:false},sline);
    secondary.push({geometry_id:entry.record.id,geometry_sha256:entry.record.sha256,metrics:metrics.regionPixelMetrics(base.data,layer.getContext('2d').getImageData(0,0,width,height).data,smask,width,height),boundary:metrics.boundaryPixelMetrics(sline.getContext('2d').getImageData(0,0,width,height).data,width,height,entry.projected.segments,{brightCore:true}),visible:entry.projected.visible});
   }
   cases.push({name,frame,timestamp:frame/30,preview_only_luminance_stress:luminanceStress,geometry_id:id,geometry_sha256:record.sha256,camera:{position:camera.camera.position.toArray(),quaternion:camera.camera.quaternion.toArray(),fov:camera.camera.fov},primary,primaryBoundary,secondary,containment,off:unchanged,visibility:projected.visible,projected_bounds:projected.bounds});
   check(name+'_FILL_VISIBLE',primary.interior_samples>=32&&primary.changed_fraction>.95&&primary.median_rgb_contrast>.08,{contrast:primary.median_rgb_contrast});
   check(name+'_PRIMARY_BOUNDARY_WIDTH',primaryBoundary.cross_sections>0&&primaryBoundary.width_px_median>=6&&primaryBoundary.width_px_median<=11,{measured:primaryBoundary});
   const measurableSecondary=secondary.filter(r=>r.metrics.interior_samples>=32);
   check(name+'_SECONDARY_PRESENT',measurableSecondary.length>0,{count:measurableSecondary.length});
   check(name+'_SECONDARY_HIERARCHY',measurableSecondary.every(r=>r.metrics.median_rgb_contrast>.025&&r.metrics.median_rgb_contrast<primary.median_rgb_contrast&&r.metrics.terrain_edge_retention>.45&&r.metrics.terrain_edge_correlation>.85));
   check(name+'_SECONDARY_BOUNDARY_WIDTH',measurableSecondary.every(r=>r.boundary.cross_sections>0&&r.boundary.width_px_median>=2&&r.boundary.width_px_median<primaryBoundary.width_px_median),{measured:measurableSecondary.map(r=>({geometry_id:r.geometry_id,...r.boundary}))});
   check(name+'_TERRAIN_RETAINED',primary.terrain_measurement_available&&primary.terrain_edge_retention>.25&&primary.terrain_edge_correlation>.85);
   check(name+'_COASTLINE_CONTAINED',containment.outside_native_fill_pixels===0);
   check(name+'_OFF_EXACT',unchanged.identical);
  }
  camera.update(240/30);const highScale={internal_resolution:[2160,3840],output_resolution:[width,height],roles:{}};
  for(const [role,id]of [['PRIMARY','COUNTRY_EGY'],['SECONDARY','COUNTRY_JOR']]){
   const native=registry.geometries.find(r=>r.id===id),prepared=infographic.prepareInfographicGeometry(native),highProjected=infographic.projectInfographicGeometry(prepared,camera.camera,2160,3840),outputProjected=infographic.projectInfographicGeometry(prepared,camera.camera,width,height),internal=document.createElement('canvas');internal.width=2160;internal.height=3840;
   bold.drawBoldRegionLayer(internal.getContext('2d'),highProjected,bold.boldRegionStyle(profile,role),{drawFill:false,width:2160,height:3840});const down=makeCanvas(),downContext=down.getContext('2d',{willReadFrequently:true});downContext.imageSmoothingEnabled=true;downContext.imageSmoothingQuality='high';downContext.drawImage(internal,0,0,width,height);
   const measurement=metrics.boundaryPixelMetrics(downContext.getImageData(0,0,width,height).data,width,height,outputProjected.segments,{brightCore:true});highScale.roles[role]={geometry_id:id,source_sha256:native.sha256,...measurement};captured('HIGH_DOWNSAMPLED_'+role+'_CORE',down);
  }
  check('HIGH_2160_TO_1080_PRIMARY_CORE_WIDTH',highScale.roles.PRIMARY.cross_sections>0&&highScale.roles.PRIMARY.width_px_median>=6&&highScale.roles.PRIMARY.width_px_median<=11,{measurement:highScale.roles.PRIMARY});
  check('HIGH_2160_TO_1080_SECONDARY_CORE_WIDTH',highScale.roles.SECONDARY.cross_sections>0&&highScale.roles.SECONDARY.width_px_median>=2&&highScale.roles.SECONDARY.width_px_median<highScale.roles.PRIMARY.width_px_median,{measurement:highScale.roles.SECONDARY});
  const normal=([lon,lat])=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180));
  const topologyCamera=(coordinate,distance=1.6,fov=40)=>{const c=new THREE.PerspectiveCamera(fov,width/height,.001,100);c.position.copy(normal(coordinate).multiplyScalar(distance));c.lookAt(0,0,0);c.updateMatrixWorld(true);return c;};
  const geoPixel=(coordinate,camera)=>{const p=normal(coordinate).multiplyScalar(1.00008).project(camera);return [Math.round((p.x*.5+.5)*width),Math.round((.5-p.y*.5)*height)];};
  const filledAt=(layer,coordinate,camera)=>{const [x,y]=geoPixel(coordinate,camera);return layer.getContext('2d').getImageData(x,y,1,1).data[3]>3;};
  // Registry-native topology cases; no authored fake country/circle is introduced.
  for(const entry of [
   {id:'COUNTRY_ZAF',center:[27,-30],inside:[24,-30],outside:[28.25,-29.5],name:'REAL_LESOTHO_HOLE_EMPTY'},
   {id:'COUNTRY_IDN',center:[114,-4],inside:[110,-7],outside:[118.5,-6],name:'REAL_INDONESIA_MULTIPOLYGON_NO_OCEAN_BRIDGE'}
  ]){
   const native=registry.geometries.find(r=>r.id===entry.id),c=topologyCamera(entry.center),p=infographic.projectInfographicGeometry(infographic.prepareInfographicGeometry(native),c,width,height),layer=makeCanvas();draw(p,'PRIMARY',{drawBoundary:false},layer);
   check(entry.name,filledAt(layer,entry.inside,c)&&!filledAt(layer,entry.outside,c),{geometry_id:native.id,geometry_sha256:native.sha256});captured(entry.name,layer);
  }
  const fiji=registry.geometries.find(r=>r.id==='COUNTRY_FJI'),preparedFiji=infographic.prepareInfographicGeometry(fiji),front=infographic.projectInfographicGeometry(preparedFiji,topologyCamera([180,-17],1.6),width,height),back=infographic.projectInfographicGeometry(preparedFiji,topologyCamera([0,17],1.6),width,height),fijiLayer=makeCanvas();draw(front,'PRIMARY',{drawBoundary:false},fijiLayer);
  check('REAL_FIJI_ANTIMERIDIAN_NATIVE_PARTS',front.visible&&front.bounds.width<width*.8&&!back.visible,{source_geometry_sha256:fiji.sha256,front_bounds:front.bounds});captured('REAL_FIJI_ANTIMERIDIAN',fijiLayer);
  check('ZERO_WEBGL_CONTEXT_ATTEMPTS',globalThis.__boldWebGLAttempts===0);
  return {passed:checks.every(r=>r.passed),checks,cases:cases.slice(0,4),luminance_stress_cases:cases.slice(4),high_resolution_pixel_scale:highScale,snapshots,resolution:[width,height],webgl_context_attempts:globalThis.__boldWebGLAttempts,GPU:'NOT_RUN',production_frame_render:'NOT_RUN',visual_quality_acceptance:'NOT_RUN',scope:'Actual Canvas2D RGBA through production overlay helper and frozen native camera; real source texture CPU ray projection excludes GPU lighting/cloud/atmosphere, not an AFTER GPU image.'};
 });
 for(const snapshot of receipt.snapshots){const bytes=Buffer.from(snapshot.png.split(',')[1],'base64');fs.writeFileSync(path.join(output,snapshot.name+'.png'),bytes);snapshot.file=snapshot.name+'.png';snapshot.sha256=sha(bytes);delete snapshot.png;}
 receipt.source_sha256s=Object.fromEntries(Object.entries(servedBytes).map(([key,bytes])=>[key,sha(bytes)]));receipt.chromium_version=browser.version();receipt.launch_flags=['--no-sandbox','--disable-gpu','--disable-gpu-compositing'];fs.writeFileSync(path.join(output,'metrics.json'),JSON.stringify(receipt,null,2)+'\n');
 assert(receipt.passed,'BOLD_CANVAS_PIXEL_QC_FAILED');console.log(JSON.stringify({passed:true,checks:receipt.checks.length,frames:receipt.cases.length,output,GPU:'NOT_RUN'}));
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
