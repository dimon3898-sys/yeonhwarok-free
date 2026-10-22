/** Native factory draw/readPixels verification, not Studio/reference production.
 * All frames are rendered by the real factory. CPU interpolation is audit only.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {legacyRegionProfile,loadRegionSourceCatalog,resolveRegionPlan,prepareRegionTerrain,verifyRegionQualification} from '../../universal-presentation-v2/region_source.mjs';
import {compileScalePlan} from '../../../web/map_infographic_v1/scale_contract.mjs';
const HERE=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),ENGINE=path.resolve(HERE,'../..'),REPO=path.dirname(ENGINE);
const sha=x=>createHash('sha256').update(x).digest('hex'),copy=structuredClone,run=promisify(execFile);
const args=Object.fromEntries(process.argv.slice(2).map(a=>{const m=/^--(attempt|only)=(.+)$/.exec(a);if(!m)throw Error('NATIVE_PROJECTION_ARGUMENT');return[m[1],m[2]];}));
const attempt=args.attempt??'attempt-01';if(!/^[a-zA-Z0-9_-]{1,50}$/.test(attempt))throw Error('NATIVE_PROJECTION_ATTEMPT_REQUIRED');
const output=path.join('/workspace/reference-director-v2-private-20261022','native-pixels-'+attempt);
await fs.mkdir(path.dirname(output),{recursive:true,mode:0o700});await fs.mkdir(output,{mode:0o700});
const write=(name,value)=>fs.writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
const originalFile=path.join(HERE,'backups/renderer.5cc9b98.original.mjs'),modifiedFile=path.join(ENGINE,'web/map_infographic_v1/renderer.mjs');
const original=await fs.readFile(originalFile),modified=await fs.readFile(modifiedFile);
if(sha(original)!=='e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38')throw Error('NATIVE_ORIGINAL_RENDERER_SHA_CHANGED');
const aliases=new Map([['/three.js',path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js')],['/web/map_infographic_v1/renderer-original.mjs',originalFile],['/web/map_infographic_v1/graphic_layout.mjs',path.join(ENGINE,'recovery/g2-final-recovery-v1/layout_extension.mjs')],['/web/map_infographic_v1/graphic_layout_legacy.mjs',path.join(ENGINE,'web/map_infographic_v1/graphic_layout.mjs')]]);
const golden=JSON.parse(await fs.readFile(path.join(HERE,'reports/NATIVE_ORIGINAL_GOLDENS.json'),'utf8'));
const goldenInputs=golden;
if(golden.rendererSHA256!==sha(original))throw Error('PRESERVED_GOLDEN_RENDERER_CHANGED');
const baseline=[];
for(const id of ['namibia_desert_coast','nepal_himalaya']){
 const row=await legacyRegionProfile(id),regionPlan=await resolveRegionPlan({scene:{locations:[]},region:{legacyProfileId:id}});
 const b=regionPlan.nativePlan.framing.bounds,c=[(b[0]+b[2])/2,(b[1]+b[3])/2],wide=[c[0]-(b[2]-b[0])*.52,c[1]-(b[3]-b[1])*.52,c[0]+(b[2]-b[0])*.52,c[1]+(b[3]-b[1])*.52];
 const prepared=await prepareRegionTerrain({regionPlan,bounds:wide,outputRoot:path.join(output,'prepared-'+id)});
 const qualified=await verifyRegionQualification({prepared});if(qualified.status!=='PASS')throw Error('CURRENT_G2_PROVIDER_SOURCE_FAILED');
 const plan=copy(prepared.nativePlan);
 // RGB image has no missing-data alpha; opt-in metadata is explicit, source bytes unchanged.
 plan.assets.terrain.NoData=null;plan.assets.terrain.CRS='EPSG:4326';
 for(const asset of Object.values(plan.assets)){
  const file=path.isAbsolute(asset.file)?asset.file:asset.file.startsWith('world-simulation-shorts-engine/')?path.join(REPO,asset.file):path.resolve(ENGINE,asset.file);
  const raw=await fs.readFile(file);if(sha(raw)!==asset.sha256)throw Error('NATIVE_BASELINE_ASSET_SHA_MISMATCH');aliases.set(asset.url,file);
 }
 const prior=golden.checks.find(c=>c.name==='DEFAULT_AND_INACTIVE_EXACT_PIXELS_'+id)?.states.find(s=>s.variant==='original');
 const priorInput=goldenInputs.baseline.find(b=>b.id===id);
 if(!prior||priorInput.terrainSHA256!==plan.assets.terrain.sha256||JSON.stringify(priorInput.framing)!==JSON.stringify(plan.framing))throw Error('PRESERVED_ORIGINAL_GOLDEN_INPUT_CHANGED');
 baseline.push({id,plan,terrainTreatment:'BAKED_RELIEF_V1',golden:prior});
}
const globe=compileScalePlan(copy(baseline[0].plan),'WORLD',{allCountries:baseline[0].plan.geometries});
// WORLD disables location labels by its existing scale policy; the optional G2
// location-gap-search adapter explicitly forbids itself for that role state.
// Omit only the inapplicable new-input policy, not any legacy layout check.
delete globe.layout.locationPlacement;
const catalog=(await loadRegionSourceCatalog()).data,globalSource=catalog.sources.find(s=>s.id==='GLOBAL_EARTH_DAY_RGB_V1');
if(!globalSource)throw Error('NATIVE_VERIFIED_GLOBAL_RGB_REQUIRED');
const globalFile=path.join(REPO,globalSource.file),globalRaw=await fs.readFile(globalFile);
if(sha(globalRaw)!==globalSource.sha256)throw Error('NATIVE_GLOBAL_RGB_SHA_MISMATCH');
const cropFile=path.join(output,'global-native-window.png');
const cropScript=`import json,sys,hashlib\nfrom PIL import Image\na,b,expected=sys.argv[1:]\nraw=open(a,'rb').read();assert hashlib.sha256(raw).hexdigest()==expected\nim=Image.open(a);assert im.mode=='RGB' and im.size==(8192,4096)\nw,s,e,n=-180,-90,180,90;dx=360/8192;dy=180/4096\nimport math\nx0=math.floor((-83-w)/dx)-2;x1=math.ceil((83-w)/dx)+2;y0=math.floor((n-83)/dy)-2;y1=math.ceil((n+83)/dy)+2\ncrop=im.crop((x0,y0,x1,y1))\nwith open(b,'xb')as f:crop.save(f,format='PNG',compress_level=6)\nassert max(crop.size)<=4096\nprint(json.dumps({'dimensions':list(crop.size),'bounds':[w+x0*dx,n-y1*dy,w+x1*dx,n-y0*dy],'pixelSpacing':[dx,dy],'parentPixelWindow':[x0,y0,x1,y1],'decodedRGBSHA256':hashlib.sha256(crop.tobytes()).hexdigest()}))`;
const crop=JSON.parse((await run('python',['-B','-c',cropScript,globalFile,cropFile,globalSource.sha256],{timeout:60000,maxBuffer:1024**2})).stdout),cropRaw=await fs.readFile(cropFile);
aliases.set('/test-assets/global-native-window.png',cropFile);
let fixture=copy(baseline[0].plan);fixture.anchor={geometry_type:'Point',crs:'EPSG:4326',coordinates:[0,0]};fixture.primary='SYNTHETIC_NORTH';fixture.secondary=['SYNTHETIC_SOUTH'];
fixture.geometries=[
 {id:'SYNTHETIC_NORTH',name:'Authored northern test shape',geometry_type:'Polygon',coordinates:[[[-12,8],[4,10],[12,20],[1,29],[-11,24],[-16,15],[-12,8]]]},
 {id:'SYNTHETIC_SOUTH',name:'Authored southern test shape',geometry_type:'Polygon',coordinates:[[[-12,-8],[1,-10],[8,-20],[-1,-29],[-17,-24],[-19,-15],[-12,-8]]]},
];
fixture.framing={projection:'REGIONAL_EQUIRECTANGULAR',bounds:[-36,-64,36,64]};fixture.text={eventTitle:'',locationLabel:'',watermark:''};fixture.layout.countryLabels=[];delete fixture.layout.locationPlacement;
fixture.scale={...fixture.scale,name:'REGIONAL',information:{location:false,country:false,title:false,disclosure:false},geographicExtent:[-36,-64,36,64]};
fixture.assets.terrain={url:'/test-assets/global-native-window.png',file:cropFile,path:cropFile,sha256:sha(cropRaw),bytes:cropRaw.length,bounds:crop.bounds,dimensions:crop.dimensions,pixelSpacing:crop.pixelSpacing,CRS:'EPSG:4326',NoData:null,classification:'RGB_TERRAIN_SOURCE',license:globalSource.license,source:{sha256:globalSource.sha256,crs:'EPSG:4326',resolution:globalSource.dimensions,geographicExtent:globalSource.bounds,pixelSpacing:globalSource.pixelSpacing}};
fixture=compileScalePlan(fixture,'REGIONAL',{allCountries:fixture.geometries});
fixture.scale.information={location:false,country:false,title:false,disclosure:false};

await write('INPUTS.json',{schema:'WORLD_ENGINE_NATIVE_PROJECTION_UNIT_INPUTS_V1',baseline:baseline.map(r=>({id:r.id,framing:r.plan.framing,terrainSHA256:r.plan.assets.terrain.sha256})),fixture,fixtureTruth:'SYNTHETIC_TEST: authored polygons are not real territory or coastline',crop:{...crop,sha256:sha(cropRaw),parentSHA256:globalSource.sha256,sourceId:globalSource.id,license:globalSource.license,attribution:globalSource.attribution,method:'SOURCE_PIXEL_WINDOW_NO_RESAMPLING'},originalRendererSHA256:sha(original),modifiedRendererSHA256:sha(modified)});
aliases.set('/reference-camera-math.mjs',path.join(ENGINE,'recovery/reference-director-v1/director_camera.mjs'));
const httpTrace=[],savedFrames=[],savedChecks=[];
const service=createServer(async(req,res)=>{let target='';try{
 const u=new URL(req.url,'http://127.0.0.1');target=decodeURIComponent(u.pathname);if(req.method!=='GET'||u.search||target.includes('..')||target.includes('\\'))throw Error('READ_ONLY_LOCAL_HTTP');
 let raw,type='application/octet-stream';
 if(target==='/'){raw=Buffer.from('<!doctype html><meta charset="utf-8"><style>body{margin:0}</style><canvas width="1080" height="1920" id="map"></canvas>');type='text/html';}
 else{const mounts=[['/web/',path.join(ENGINE,'web')],['/static/',path.join(ENGINE,'web')],['/v3/assets/',path.join(REPO,'cinematic-world-map/assets')]],mount=mounts.find(([prefix])=>target.startsWith(prefix));const file=aliases.get(target)??(mount&&path.join(mount[1],target.slice(mount[0].length)));if(!file)throw Error('NOT_FOUND');raw=await fs.readFile(file);type=/\.(mjs|js)$/.test(target)?'text/javascript':/\.png$/.test(target)?'image/png':/\.jpg$/.test(target)?'image/jpeg':/\.otf$/.test(target)?'font/otf':type;}
 httpTrace.push({path:target,status:200,bytes:raw.length,sha256:sha(raw)});res.writeHead(200,{'content-type':type,'cache-control':'no-store'});res.end(raw);
 }catch(e){httpTrace.push({path:target,status:404,code:e.message});res.writeHead(404);res.end();}});
const deps=createRequire('/workspace/universal-data-pipeline-v1-private-20261022/node-deps/package.json'),{chromium}=deps('playwright');
let browser;const errors=[],started=performance.now();let result;
try{
 await new Promise((ok,bad)=>{service.once('error',bad);service.listen(0,'127.0.0.1',ok);});const origin='http://127.0.0.1:'+service.address().port;
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});page.on('pageerror',e=>errors.push(e.message));
 await fs.writeFile(path.join(output,'FRAME_PROGRESS.ndjson'),'',{flag:'wx',mode:0o600});
 await page.exposeFunction('persistNativeCheck',async row=>{savedChecks.push(row);await fs.appendFile(path.join(output,'CHECK_PROGRESS.ndjson'),JSON.stringify(row)+'\n');});
 await page.exposeFunction('persistNativeFrame',async record=>{if(!/^[A-Za-z0-9_-]+$/.test(record.name))throw Error('NATIVE_FRAME_NAME');const row={...record};await fs.writeFile(path.join(output,row.name+'.png'),Buffer.from(row.png,'base64'),{flag:'wx',mode:0o600});delete row.png;savedFrames.push(row);await fs.appendFile(path.join(output,'FRAME_PROGRESS.ndjson'),JSON.stringify(row)+'\n');});
 await page.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort('blockedbyclient'));await page.goto(origin);
 result=await page.evaluate(async({baseline,fixture,globe,only,expectedBackend})=>{
  const THREE=await import('/three.js'),old=await import('/web/map_infographic_v1/renderer-original.mjs'),next=await import('/web/map_infographic_v1/renderer.mjs');
  const canvas=document.getElementById('map'),gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});if(!gl)throw Error('ACTUAL_WEBGL2_REQUIRED');
  const ext=gl.getExtension('WEBGL_debug_renderer_info'),backend=gl.getParameter(ext?ext.UNMASKED_RENDERER_WEBGL:gl.RENDERER);if(!String(backend).includes('SwiftShader'))throw Error('SOFTWARE_ONLY_BACKEND_REQUIRED');if(backend!==expectedBackend)throw Error('PRESERVED_GOLDEN_BACKEND_CHANGED');
  const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});renderer.setPixelRatio(1);renderer.setSize(1080,1920,false);renderer.autoClear=false;
  const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');
  const captures=[],checks=[];const recordCheck=async row=>{checks.push(row);await window.persistNativeCheck(row);};
  const assert=(x,code)=>{if(!x)throw Error(code);};
  const getPixel=(bytes,x,y)=>{const i=((1919-y)*1080+x)*4;return Array.from(bytes.slice(i,i+4));};
  async function capture(factory,name,options={}){
   const frame=factory.renderFrame({...options,finish:true}),pixels=factory.readPixels();assert(frame.glError===0,'ACTUAL_GL_ERROR');let nonBlack=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]+pixels[i+1]+pixels[i+2]>0)nonBlack++;
   const record={name,rawSHA256:await digest(pixels),nonBlackPixels:nonBlack,glError:frame.glError,programsRunnable:factory.evidence.programs.every(p=>p.runnable)};
   await window.persistNativeFrame({...record,png:canvas.toDataURL('image/png').split(',')[1]});captures.push(record);return{...record,pixels};
  }
  const options={outputRenderer:renderer,width:1080,height:1920};
  async function defaultCase(row){
   const states=[];for(const variant of (['verify05','unit05'].includes(only)?['patched','optin-inactive']:['original','patched','optin-inactive'])){
    renderer.resetState();const f=await(variant==='original'?old:next).createMapInfographicRenderer({canvas,plan:structuredClone(row.plan),layoutPlan:structuredClone(row.plan),terrainTreatment:row.terrainTreatment,...options,...(variant==='optin-inactive'?{projectionMode:'REFERENCE_SIMILARITY_2D_V1'}:{})});
    const standard=await capture(f,row.id+'_'+variant,{mode:0,graphics:true,boundaries:true,glow:true,dem:false});
    let wider=null;if(row.plan.framing.projection!=='WORLD_GLOBE_ORTHOGRAPHIC'){
     const b=row.plan.framing.bounds,c=[(b[0]+b[2])/2,(b[1]+b[3])/2],wide=[c[0]-(b[2]-b[0])*.51,c[1]-(b[3]-b[1])*.51,c[0]+(b[2]-b[0])*.51,c[1]+(b[3]-b[1])*.51];f.updateCamera(wide);wider=await capture(f,row.id+'_'+variant+'_bounds',{mode:0,graphics:true,boundaries:true,glow:true,dem:false});
    }
    states.push({variant,standardSHA256:standard.rawSHA256,widerSHA256:wider?.rawSHA256});f.dispose();
   }
   assert(states.every(s=>s.standardSHA256===row.golden.standardSHA256&&s.widerSHA256===row.golden.widerSHA256),'DEFAULT_PIXEL_REGRESSION_'+row.id);await recordCheck({name:'DEFAULT_AND_INACTIVE_EXACT_PIXELS_'+row.id,status:'PASS',states});
  }
  async function globeCase(){
   const states=[];for(const variant of ['original','patched']){renderer.resetState();const f=await(variant==='original'?old:next).createMapInfographicRenderer({canvas,plan:structuredClone(globe),layoutPlan:structuredClone(globe),terrainTreatment:'BAKED_RELIEF_V1',...options});const r=await capture(f,'world_'+variant,{mode:0,graphics:true,boundaries:true,glow:true,dem:false});states.push({variant,sha256:r.rawSHA256});f.dispose();}
   assert(states[0].sha256===states[1].sha256,'GLOBE_DEFAULT_PIXEL_REGRESSION');await recordCheck({name:'GLOBE_DEFAULT_EXACT_PIXELS',status:'PASS',states});
  }
  if(only==='guards'){
   const rejected=[];for(const scenario of ['MISSING_NATIVE_BUDGET','CRS_MISMATCH','NODATA_UNDECLARED']){
    const plan=structuredClone(fixture);if(scenario==='MISSING_NATIVE_BUDGET'){delete plan.assets.terrain.pixelSpacing;delete plan.assets.terrain.source.pixelSpacing;delete plan.assets.terrain.source.resolution;}if(scenario==='CRS_MISMATCH'){plan.assets.terrain.CRS='EPSG:3857';plan.assets.terrain.source.crs='EPSG:3857';}if(scenario==='NODATA_UNDECLARED')delete plan.assets.terrain.NoData;
    renderer.resetState();const f=await next.createMapInfographicRenderer({canvas,plan,layoutPlan:plan,terrainTreatment:'CURRENT',projectionMode:'REFERENCE_SIMILARITY_2D_V1',...options});const beforeEnvelope=JSON.stringify(f.sourceEnvelope()),beforeScreen=JSON.stringify(f.screen([2,3])),beforeEvidence=JSON.stringify(f.evidence.cameraFrame),before=await capture(f,'guard_'+scenario+'_before',{mode:5,graphics:false,boundaries:false,glow:false,dem:false});let code;try{f.updateSimilarity({centerQ:[0,0],scale:15,angleDegrees:25});}catch(e){code=e.code??e.message;}assert(code==='SIMILARITY_NATIVE_TERRAIN_DESCRIPTOR_REQUIRED','NATIVE_METADATA_NOT_REJECTED_'+scenario+'_'+code);
    // Admission is transactional: a pre-mutation rejection retains the prior
    // admitted/legacy camera. It cannot install the rejected rotated pose.
    assert(beforeEnvelope===JSON.stringify(f.sourceEnvelope())&&beforeScreen===JSON.stringify(f.screen([2,3]))&&beforeEvidence===JSON.stringify(f.evidence.cameraFrame),'REJECTED_METADATA_CHANGED_CAMERA_STATE');const after=await capture(f,'guard_'+scenario+'_after',{mode:5,graphics:false,boundaries:false,glow:false,dem:false});assert(before.rawSHA256===after.rawSHA256,'REJECTED_METADATA_CHANGED_NATIVE_SOURCE_PIXELS');rejected.push({scenario,code,priorStatePreserved:true,priorNativePixelsExact:true,rawSHA256:before.rawSHA256,rejectedPoseCommitted:false});f.dispose();
   }
   await recordCheck({name:'NATIVE_METADATA_REJECTION_PRIOR_STATE_PRESERVATION',status:'PASS',rejected});renderer.dispose();return{schema:'WORLD_ENGINE_NATIVE_PROJECTION_PIXEL_TEST_V1',scope:'PHASE1_NATIVE_FACTORY_METADATA_GUARDS_ONLY',backend,nvidiaVerified:false,paidExecuted:false,checks,captures,errors:[],optinResults:[],phase1OptinDraw:'NOT_RUN_GUARDS_ONLY'};
  }
  if(only==='determinism'){
   const states=[];for(const variant of ['original_first','original_second','patched_first','patched_second']){
    renderer.resetState();const f=await(variant.startsWith('original')?old:next).createMapInfographicRenderer({canvas,plan:structuredClone(globe),layoutPlan:structuredClone(globe),terrainTreatment:'BAKED_RELIEF_V1',...options});
    const passes=[];for(const pass of [{id:'full',mode:0,graphics:true,boundaries:true,glow:true},{id:'terrain',mode:0,graphics:false,boundaries:false,glow:false},{id:'source',mode:5,graphics:false,boundaries:false,glow:false}]){
     const first=await capture(f,'world_'+variant+'_'+pass.id,{...pass,dem:false}),repeat=await capture(f,'world_'+variant+'_'+pass.id+'_repeat',{...pass,dem:false});
     passes.push({pass:pass.id,firstSHA256:first.rawSHA256,repeatSHA256:repeat.rawSHA256,sameFactoryExact:first.rawSHA256===repeat.rawSHA256});
    }
    states.push({variant,passes,sameFactoryExact:passes.every(p=>p.sameFactoryExact)});f.dispose();
   }
   await recordCheck({name:'WORLD_ORIGINAL_NATIVE_DETERMINISM_AUDIT',status:states.every(s=>s.sameFactoryExact)&&states[0].passes.every((p,i)=>p.firstSHA256===states[1].passes[i].firstSHA256)?'PASS':'FAIL',states});
   renderer.dispose();return{schema:'WORLD_ENGINE_NATIVE_PROJECTION_PIXEL_TEST_V1',scope:'PHASE1_NATIVE_ORIGINAL_DETERMINISM_AUDIT',backend,nvidiaVerified:false,paidExecuted:false,checks,captures,errors:[],optinResults:[],phase1OptinDraw:'NOT_RUN_DETERMINISM_ONLY'};
  }
  if(only==='verify05')await globeCase();
  if(only!=='active')for(const row of baseline)await defaultCase(row);
  if(only!=='baseline'&&only!=='verify05'&&only!=='unit05')await globeCase();
  let optinResults=[];
  if(only!=='baseline'){
   const math=await import('/reference-camera-math.mjs'),{compileScalePlan:compileFixtureScale}=await import('/web/map_infographic_v1/scale_contract.mjs');
   const pointInside=(p,ring)=>{let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++)if((ring[i][1]>p[1])!==(ring[j][1]>p[1])&&p[0]<(ring[j][0]-ring[i][0])*(p[1]-ring[i][1])/(ring[j][1]-ring[i][1])+ring[i][0])yes=!yes;return yes;};
   const distanceToSegment=(p,a,b)=>{const d=b.map((v,i)=>v-a[i]),n=d[0]**2+d[1]**2,t=n?Math.max(0,Math.min(1,((p[0]-a[0])*d[0]+(p[1]-a[1])*d[1])/n)):0;return Math.hypot(p[0]-a[0]-t*d[0],p[1]-a[1]-t*d[1]);};
   const sample=(bytes,x,y)=>{const a=Math.floor(x),b=Math.floor(y),tx=x-a,ty=y-b,out=[0,0,0];for(let j=0;j<2;j++)for(let i=0;i<2;i++){const p=getPixel(bytes,a+i,b+j),w=(i?tx:1-tx)*(j?ty:1-ty);for(let c=0;c<3;c++)out[c]+=w*p[c];}return out;};
   const validSample=p=>p[0]>=2&&p[0]<1077&&p[1]>=2&&p[1]<1917;
   const absoluteError=(a,b)=>a.slice(0,3).reduce((sum,v,i)=>sum+Math.abs(v-b[i]),0)/3;
   const percentile=(v,q)=>[...v].sort((a,b)=>a-b)[Math.floor((v.length-1)*q)];
   const expectError=(fn,code)=>{let error;try{fn();}catch(e){error=e.code??e.message;}assert(error===code,'EXPECTED_'+code+'_GOT_'+error);return{expected:code,actual:error,status:'PASS'};};
   for(const originLatitude of [0,20,-20]){
    let plan=structuredClone(fixture);const height=originLatitude===0?128:100,cos=Math.cos(originLatitude*Math.PI/180),width=height*1080/1920/cos;
    plan.framing.bounds=[-width/2,originLatitude-height/2,width/2,originLatitude+height/2];plan.anchor.coordinates=[0,originLatitude];plan.scale.geographicExtent=[...plan.framing.bounds];plan=compileFixtureScale(plan,'REGIONAL',{allCountries:plan.geometries});plan.scale.information={location:false,country:false,title:false,disclosure:false};
    renderer.resetState();const f=await next.createMapInfographicRenderer({canvas,plan,layoutPlan:plan,terrainTreatment:'CURRENT',projectionMode:'REFERENCE_SIMILARITY_2D_V1',...options});
    const descriptor=f.projectionDescriptor(),projection=math.createFactoryFlatProjection(plan.framing.bounds),scale=1920/height,basePose={centerQ:[0,0],scale,angleDegrees:0};
    assert(JSON.stringify(descriptor.initialBounds)===JSON.stringify(projection.initialBounds),'NATIVE_PROJECTION_ORIGIN_MISMATCH');
    const baseEvidence=f.updateSimilarity(basePose),base=await capture(f,'active_'+originLatitude+'_base_source',{mode:5,graphics:false,boundaries:false,glow:false,dem:false});
    const poses=[{centerQ:[2,-1],scale:scale*.99,angleDegrees:25},{centerQ:[-3,1.5],scale:scale*.98,angleDegrees:50},{centerQ:[3,-2],scale:scale*.99,angleDegrees:82},{centerQ:[-1,2],scale:scale*.99,angleDegrees:-37}];
    const poseResults=[];
    for(let index=0;index<poses.length;index++){
     const pose=poses[index],admission=f.updateSimilarity(pose),envelope=f.sourceEnvelope();let maxAnchorResidual=0,maxInversePixelResidual=0,maxEnvelopeDelta=0;
     const probes=[[0,originLatitude],[10,originLatitude+10],[-10,originLatitude-10],[-12,8],[1,-20]];
     for(const geo of probes){const intended=math.projectDirectorPoint(geo,pose,projection),actual=f.screen(geo),back=f.inverseScreen(actual);maxAnchorResidual=Math.max(maxAnchorResidual,Math.hypot(actual[0]-intended[0],actual[1]-intended[1]));const round=math.projectDirectorPoint(back,pose,projection);maxInversePixelResidual=Math.max(maxInversePixelResidual,Math.hypot(round[0]-actual[0],round[1]-actual[1]));}
     const expectedEnvelope=math.sourceEnvelopeForPose(pose,projection);for(let i=0;i<4;i++)maxEnvelopeDelta=Math.max(maxEnvelopeDelta,Math.hypot(envelope.corners[i][0]-expectedEnvelope.corners[i][0],envelope.corners[i][1]-expectedEnvelope.corners[i][1]));
     assert(maxAnchorResidual<1e-6&&maxInversePixelResidual<1e-6&&maxEnvelopeDelta<1e-7,'NATIVE_FORWARD_INVERSE_MISMATCH');
     const raw=await capture(f,'active_'+originLatitude+'_'+index+'_source',{mode:5,graphics:false,boundaries:false,glow:false,dem:false}),correctErrors=[],wrongErrors=[];
     for(let y=40;y<1880;y+=40)for(let x=40;x<1040;x+=40){
      const geo=math.inverseDirectorScreen([x+.5,y+.5],pose,projection),from=math.projectDirectorPoint(geo,basePose,projection).map(v=>v-.5),wrongGeo=[envelope.bounds[0]+(x+.5)/1080*(envelope.bounds[2]-envelope.bounds[0]),envelope.bounds[3]-(y+.5)/1920*(envelope.bounds[3]-envelope.bounds[1])],wrongFrom=math.projectDirectorPoint(wrongGeo,basePose,projection).map(v=>v-.5);
      if(!validSample(from)||!validSample(wrongFrom))continue;const expected=sample(base.pixels,...from),wrong=sample(base.pixels,...wrongFrom);if(absoluteError(expected,wrong)<8)continue;
      const actual=getPixel(raw.pixels,x,y);correctErrors.push(absoluteError(actual,expected));wrongErrors.push(absoluteError(actual,wrong));
     }
     assert(correctErrors.length>=40,'INSUFFICIENT_SOURCE_ALIGNMENT_PROBES');
     const correctMean=correctErrors.reduce((a,b)=>a+b,0)/correctErrors.length,wrongMean=wrongErrors.reduce((a,b)=>a+b,0)/wrongErrors.length,median=percentile(correctErrors,.5);
     assert(median<=4&&correctMean<=8&&correctMean<wrongMean*.4,'TERRAIN_SHARED_INVERSE_PIXEL_MISMATCH');
     const cov=await capture(f,'active_'+originLatitude+'_'+index+'_coverage',{mode:4,graphics:false,boundaries:false,glow:false,dem:false});let coverageProbes=0,coverageMismatches=0;
     const polygons=plan.geometries.map(g=>g.coordinates[0]),edges=polygons.flatMap(r=>r.slice(1).map((p,i)=>[math.projectDirectorPoint(r[i],pose,projection),math.projectDirectorPoint(p,pose,projection)]));
     for(let y=30;y<1890;y+=30)for(let x=30;x<1050;x+=30){const screen=[x+.5,y+.5];if(edges.some(([a,b])=>distanceToSegment(screen,a,b)<4))continue;const geo=math.inverseDirectorScreen(screen,pose,projection),inside=polygons.map(r=>pointInside(geo,r)),expected=[inside.some(Boolean)?255:0,inside[1]?255:0,inside[0]?255:0],actual=getPixel(cov.pixels,x,y);coverageProbes++;if(expected.some((v,i)=>Math.abs(v-actual[i])>1))coverageMismatches++;}
     assert(coverageProbes>1000&&coverageMismatches===0,'NATIVE_ROTATED_GIS_COVERAGE_MISMATCH');
     const material=await capture(f,'active_'+originLatitude+'_'+index+'_material',{mode:0,graphics:false,boundaries:true,glow:true,dem:false});assert(material.nonBlackPixels>1080*1920*.99,'NATIVE_BLACK_CORNERS');
     poseResults.push({pose,admission,maxAnchorResidualPixels:maxAnchorResidual,maxInverseResidualPixels:maxInversePixelResidual,maxEnvelopeDeltaDegrees:maxEnvelopeDelta,sourceAlignment:{informativeSamples:correctErrors.length,medianRGBError:median,meanRGBError:correctMean,incorrectUnrotatedSamplingMeanRGBError:wrongMean,method:'Actual native raw-source readPixels compared at independent inverse-projected geographic points in the baseline native draw; CPU interpolation used for numerical audit only, never as output'},coverage:{probes:coverageProbes,mismatches:coverageMismatches,method:'Actual native coverage readPixels against independent inverse-projection/polygon inclusion away from antialiased edges'},actualMaterialFrameSHA256:material.rawSHA256});
    }
    const denied=[];denied.push(expectError(()=>f.updateSimilarity({...basePose,approved:true}),'SIMILARITY_POSE_INVALID'));
    denied.push(expectError(()=>f.updateSimilarity({...basePose,scale:scale*2}),'LOCAL_NOT_ADMITTED'));
    denied.push(expectError(()=>f.updateSimilarity({...basePose,centerQ:[100,0]}),'SIMILARITY_SOURCE_ENVELOPE_GUTTER_FAILED'));
    denied.push(expectError(()=>f.updateSimilarity({...basePose,centerQ:[0,-100]}),'SIMILARITY_GEOGRAPHIC_DOMAIN_OR_DATELINE_UNSUPPORTED'));
    f.updateSimilarity(basePose);denied.push(expectError(()=>f.renderFrame({graphics:true}),'SIMILARITY_CURRENT_PROJECTED_GRAPHIC_CONSUMER_REQUIRED'));
    // Restoring the legacy bounds contract leaves opt-in and renders the exact
    // same source expression as a fresh default factory for this same fixture.
    f.updateCamera(plan.framing.bounds);const restored=await capture(f,'active_'+originLatitude+'_legacy_restored',{mode:5,graphics:false,boundaries:false,glow:false,dem:false});f.dispose();
    renderer.resetState();const defaultFactory=await next.createMapInfographicRenderer({canvas,plan:structuredClone(plan),layoutPlan:structuredClone(plan),terrainTreatment:'CURRENT',...options});const fresh=await capture(defaultFactory,'active_'+originLatitude+'_fresh_legacy',{mode:5,graphics:false,boundaries:false,glow:false,dem:false});assert(restored.rawSHA256===fresh.rawSHA256,'UPDATE_BOUNDS_DID_NOT_RESTORE_LEGACY_PIXELS');denied.push(expectError(()=>defaultFactory.updateSimilarity(basePose),'SIMILARITY_EXPLICIT_OPT_IN_REQUIRED'));defaultFactory.dispose();
    await recordCheck({name:'COMMON_NATIVE_ROTATION_'+originLatitude,status:'PASS',poseCount:poses.length,deniedInputs:denied.length,legacyRestorationExact:true});optinResults.push({originLatitude,projection:descriptor,baseAdmission:baseEvidence,poses:poseResults,deniedInputs:denied,legacyRestoredSHA256:restored.rawSHA256});
   }
   // A distinct smaller admitted initial extent isolates source-resolution
   // rejection from the pre-existing closest-view rejection.
   const coarse=structuredClone(fixture);coarse.framing.bounds=[-18,-32,18,32];coarse.scale.geographicExtent=[...coarse.framing.bounds];renderer.resetState();const f=await next.createMapInfographicRenderer({canvas,plan:coarse,layoutPlan:coarse,terrainTreatment:'CURRENT',projectionMode:'REFERENCE_SIMILARITY_2D_V1',...options});
   const densityFailure=expectError(()=>f.updateSimilarity({centerQ:[0,0],scale:25,angleDegrees:0}),'SIMILARITY_NATIVE_TEXEL_DENSITY_EXCEEDED');f.dispose();await recordCheck({name:'NATIVE_SOURCE_RESOLUTION_REJECTED',status:'PASS',error:densityFailure});
  }
  renderer.dispose();return{schema:'WORLD_ENGINE_NATIVE_PROJECTION_PIXEL_TEST_V1',scope:'PHASE1_NATIVE_UNIT_DRAW_NOT_STUDIO_REFERENCE_PRODUCTION',backend,nvidiaVerified:false,paidExecuted:false,checks,captures,errors:[],optinResults,phase1OptinDraw:only==='baseline'?'NOT_RUN_BASELINE_ONLY':'ACTUAL_NATIVE_ROTATED_MAP_DRAW'};
 },{baseline,fixture,globe,only:args.only??'all',expectedBackend:golden.backend});
 if(errors.length)throw Error('BROWSER_PAGE_ERRORS:'+errors.join('|'));
 if(result.captures.length!==savedFrames.length)throw Error('NATIVE_FRAME_PROGRESS_MISMATCH');
 result.elapsedSeconds=(performance.now()-started)/1000;result.rendererSources={originalSHA256:sha(original),modifiedSHA256:sha(modified)};result.command=process.argv.join(' ');result.playwrightVersion=deps('playwright/package.json').version;result.chromiumVersion=browser.version();result.status=args.only==='baseline'?'BASELINE_DEFAULT_PIXELS_ONLY':args.only==='determinism'?'NATIVE_BASELINE_DETERMINISM_'+(result.checks.every(c=>c.status==='PASS')?'PASS':'FAIL'):args.only==='guards'?'NATIVE_FACTORY_METADATA_GUARDS_PASS':args.only==='unit05'?'INDEPENDENT_NATIVE_UNIT_PASS_GLOBE_GATE_BLOCKED':'PHASE1_NATIVE_PIXEL_PASS_NOT_REFERENCE_QUALITY_PASS';
 await write('PIXEL_RESULTS.json',result);console.log(JSON.stringify({status:result.status,outputRoot:output,checks:result.checks,frameCount:result.captures.length,backend:result.backend}));
} catch(e){await write('FAILURE.json',{status:'FAIL',code:String(e.message),stack:String(e.stack).slice(0,8000),elapsedSeconds:(performance.now()-started)/1000,browserErrors:errors});console.error(JSON.stringify({status:'FAIL',code:String(e.message).slice(0,1600),retainedActualFrames:savedFrames.length,outputRoot:output}));process.exitCode=1;}
finally{await browser?.close();await new Promise(ok=>service.close(ok));await write('HTTP_BINDINGS.json',httpTrace);}
