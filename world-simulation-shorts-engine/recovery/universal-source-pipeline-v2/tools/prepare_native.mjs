/** New data-only plan: unchanged source GIS/assets, scale and Camera V5 compilers. */
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {compileMinimumContextPlan,evaluateMinimumContextCameraFrame} from '../../../web/map_infographic_v1/camera_director_v5.mjs';
import {compileScalePlan,geometryBounds} from '../../../web/map_infographic_v1/scale_contract.mjs';
import {GRAPHIC_LAYOUT_VERSION} from '../../../web/map_infographic_v1/graphic_layout.mjs';
const HERE=path.dirname(fileURLToPath(import.meta.url)),ENGINE=path.resolve(HERE,'../../..'),REPO=path.dirname(ENGINE);
const hash=b=>createHash('sha256').update(b).digest('hex'),clone=x=>structuredClone(x),box=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
export async function prepareNative({seedPlanFile,config}){
 const keys=['primary_id','event_location','final_bounds','start_bounds','total_frames','fps','camera_profile'];
 if(!config||Object.keys(config).some(k=>!keys.includes(k))||keys.some(k=>!(k in config))||!box(config.final_bounds)||!box(config.start_bounds)
  ||!Array.isArray(config.event_location)||config.event_location.length!==2||!config.event_location.every(Number.isFinite)
  ||!Number.isSafeInteger(config.total_frames)||config.total_frames<30||config.total_frames>240||config.fps!==30)throw Error('GENERIC_NATIVE_CONFIG_INVALID');
 const seedRaw=await readFile(seedPlanFile),seed=JSON.parse(seedRaw),primary=seed.geometries.find(g=>g.id===config.primary_id);
 if(!primary)throw Error('GENERIC_NATIVE_SOURCE_PRIMARY_REQUIRED');
 if(seed.layout?.measured?.version!==GRAPHIC_LAYOUT_VERSION)throw Error('GENERIC_NATIVE_EXISTING_MEASURED_PROFILE_REQUIRED');
 const spacing=seed.assets?.terrain?.pixelSpacing;
 if(!Array.isArray(spacing)||spacing.length!==2||spacing.some(v=>!Number.isFinite(v)||v<=0))throw Error('GENERIC_NATIVE_RASTER_SPACING_REQUIRED');
 const requiredSpan=[spacing[0]*1080,spacing[1]*1920],actualSpan=[config.final_bounds[2]-config.final_bounds[0],config.final_bounds[3]-config.final_bounds[1]];
 if(actualSpan.some((span,index)=>span<requiredSpan[index]-1e-9))throw Error('GENERIC_DEMO_NATIVE_PIXEL_BUDGET_EXCEEDED');
 const plan=clone(seed),sourceBounds=geometryBounds(primary);
 plan.primary=config.primary_id;plan.secondary=[];plan.anchor={geometry_type:'Point',crs:'EPSG:4326',coordinates:[...config.event_location]};
 plan.framing={projection:'REGIONAL_EQUIRECTANGULAR',bounds:[...config.final_bounds]};
 plan.text={locationLabel:'ZONE',eventTitle:'DEMO',watermark:''};plan.layout.countryLabels=[];
 const nativePlan=compileScalePlan(plan,'REGIONAL',{allCountries:seed.geometries});
 const scene={primary_region_id:config.primary_id,primary_geometry:clone(primary),event_anchor:[...config.event_location],
  approved_final_extent:[...config.final_bounds],start_extent:[...config.start_bounds],desired_detail_level:'REGIONAL',
  scale_admission:{status:'LOCAL_NOT_ADMITTED'},canonical_output:[1080,1920],safe_area:[...nativePlan.layout.safe],
  event_title:'',location_label:'',primary_label:''};
 const cameraPlan=compileMinimumContextPlan({scene,profile:config.camera_profile,seed:0}),arrival=cameraPlan.naturalMotion.arrivalFrame;
 if(2*arrival+1>config.total_frames)throw Error('GENERIC_V5_SCHEDULE_EXCEEDS_CLIP');
 const hold=config.total_frames-2*arrival-1,cameraSchedule=[];
 for(let f=0;f<config.total_frames;f++){
  const sourceFrame=f<=arrival?f:f<=arrival+hold?arrival:Math.max(0,arrival-(f-arrival-hold));
  const state=evaluateMinimumContextCameraFrame(cameraPlan,sourceFrame);
  if(state.admission.localUsed)throw Error('GENERIC_DEMO_LOCAL_ADMISSION_FORBIDDEN');
  cameraSchedule.push({frame:f,sourceFrame,clockDirection:f<=arrival?'FORWARD':f<=arrival+hold?'HOLD':'REVERSE',flatBounds:state.camera.flatBounds});
 }
 const assets=[];
 for(const [role,asset]of Object.entries(nativePlan.assets)){
  const relative=asset.file;if(typeof relative!=='string')throw Error('GENERIC_SOURCE_ASSET_FILE_REQUIRED');
  const file=relative.startsWith('world-simulation-shorts-engine/')?path.join(REPO,relative):path.resolve(ENGINE,relative),raw=await readFile(file);
  if(hash(raw)!==asset.sha256)throw Error('GENERIC_SOURCE_ASSET_SHA_MISMATCH_'+role);
  assets.push({role,path:path.relative(REPO,file),sha256:hash(raw),bytes:raw.length});
 }
 return{schema:'WORLD_ENGINE_GENERIC_NATIVE_INPUTS_V2',nativePlan,cameraPlan,cameraSchedule,sourceBindings:[{role:'SEED_NATIVE_SOURCE_PLAN',path:String(seedPlanFile),sha256:hash(seedRaw),bytes:seedRaw.length},...assets],
  evidence:{newDataOnlyPlan:true,sourcePrimaryGeometryId:primary.id,sourcePrimaryGeometryBounds:sourceBounds,
   protectedG1PlanChanged:false,existingMeasuredLayoutProfileVersion:nativePlan.layout.measured.version,
   existingCameraMathChanged:false,cameraClock:'EXPLICIT_INTEGER_FORWARD_HOLD_REVERSE_OF_ACTUAL_V5_PLAN',
   resampledGlobalDerivativeClaimed:false,sourceRasterExtent:clone(nativePlan.assets.terrain.bounds),
   rasterOutsideSupport:'UNCHANGED_NATIVE_GLOBAL_SOURCE_FALLBACK',localAdmissionGranted:false,syntheticOnly:true,
   actualSourceFrames:cameraSchedule.map(r=>r.sourceFrame),cameraArrivalSourceFrame:arrival,holdFrames:hold}};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args={};for(const arg of process.argv.slice(2)){const m=/^--(config|output|seed-plan)=(.+)$/.exec(arg);if(!m||args[m[1]])throw Error('GENERIC_PREPARE_ARGUMENT_INVALID');args[m[1]]=m[2];}
 if(!args.config||!args.output||!args['seed-plan'])throw Error('GENERIC_PREPARE_INPUTS_REQUIRED');
 const value=await prepareNative({seedPlanFile:args['seed-plan'],config:JSON.parse(await readFile(args.config,'utf8'))});
 await writeFile(args.output,JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
 console.log(JSON.stringify({status:'PREPARED_NOT_RENDERED',output:args.output,frames:value.cameraSchedule.length,arrival:value.evidence.cameraArrivalSourceFrame,hold:value.evidence.holdFrames,sha256:hash(await readFile(args.output))}));
}
