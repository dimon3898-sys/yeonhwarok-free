// STEP 1 only: read-only admission verification. No V3 camera/graphic implementation or proof.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {openRuntime,repo,productionFixture,sha,json} from '../event-v1-candidate-v2/candidate_runtime.mjs';
import {SafeClosestExtent,terrainDetailDescriptor} from '../../web/map_infographic_v1/local_detail_admission.mjs';
const execute=promisify(execFile),directory=path.dirname(fileURLToPath(import.meta.url));
const refs={v5:'29b8ee294360812b55ef577b62411de58159003b',event_v2:'8cbbbd64573ea87aa56decbc0fb5218071e45bbe',
 suez_data:'69e6ed83acac00bfa7ab1853722f873792a813e1'};
const engine='world-simulation-shorts-engine',v5=engine+'/recovery/v5',v2=engine+'/recovery/event-v1-candidate-v2';
const camera=await json(path.join(repo,v5,'inputs/camera-plan.json'));
const regional=await json(path.join(repo,engine,'recovery/v4/equivalent-plans/REGIONAL-plan.json'));
const input=await json(path.join(repo,engine,'recovery/v4/V4-state-records/input-manifest.json'));
const registeredAdmission=await json(path.join(repo,engine,'recovery/v4/past-paths/tmp/world-local-detail-admission/iteration-02/local-admission.json'));
const terrainMetadata=registeredAdmission.safeClosest.baselineDataAssessment.terrain.source;
assert.equal(terrainMetadata.sha256,regional.assets.terrain.sha256,'REGISTERED_TERRAIN_METADATA_HASH_MISMATCH');
const fixture=await json(path.join(repo,productionFixture));
const on=await json(path.join(repo,v2,'evidence/on150/REPORT.json'));
const current=camera.intent.finalExtent,safe=on.frames.at(-1).placement.safeArea,line=on.frames.at(-1).line;
const protectedPaths={v5:[v5,engine+'/web/map_infographic_v1/camera_director_v5.mjs',
 engine+'/web/map_infographic_v1/camera_gpu_pipeline_v5.mjs',engine+'/web/map_infographic_v1/renderer.mjs'],
 event_v2:[v2,engine+'/web/map_infographic_v1'],suez_data:[engine+'/recovery/event-data/suez-full-canal-20261012']};
const checks={};
for(const [name,paths]of Object.entries(protectedPaths)){
 await execute('git',['rev-parse','--verify',refs[name]+'^{commit}'],{cwd:repo});
 const {stdout}=await execute('git',['diff','--name-only',refs[name],'--',...paths],{cwd:repo});
 assert.equal(stdout.trim(),'','PROTECTED_BASELINE_CHANGED_'+name);checks[name]={commit:refs[name],changed_paths:[]};
}
const shrink=(bounds,factors)=>{
 const centre=[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2],half=[(bounds[2]-bounds[0])*factors[0]/2,(bounds[3]-bounds[1])*factors[1]/2];
 return [centre[0]-half[0],centre[1]-half[1],centre[0]+half[0],centre[1]+half[1]];
};
assert.equal(camera.admission.status,'LOCAL_NOT_ADMITTED');assert.equal(camera.admission.localPermitted,false);
assert.deepEqual(camera.admission.stopBounds,current);assert.deepEqual(camera.admission.regionalStopBounds,current);
const assessment=SafeClosestExtent({approvedExtent:current,requestedExtent:shrink(current,[.99,.99]),
 output:[1080,1920],anchor:regional.anchor.coordinates,primary:regional.primary,geometries:regional.geometries,
 eventGeometry:[{id:fixture.geometry_id,geometry:fixture.intent.line.geometry}],qualityEvidence:{},
 terrain:terrainDetailDescriptor(regional.assets.terrain,terrainMetadata),heightSource:input.heightSource,requirements:{requireRealDEM:false}});
assert.equal(assessment.additionalZoomPermitted,false);assert.equal(assessment.closestExtentCertified,false);
assert.deepEqual(assessment.bounds,current);
let session;
const report={schema:1,status:'EVENT_DETAIL_APPROACH_BLOCKED',next:'EVENT_V3_ACTION_REQUIRED',
 step:1,event_final:false,candidate_pass:false,baselines:checks,
 v2_manifest_validation:{command:'/usr/bin/python3 -B '+v2+'/validate_manifests.py --require-persisted',
  status:'PASS',required_files:258,source_persisted:true,required_temp_only_files:0},
 camera_admission:camera.admission,current_framing:current,live_safe_closest:assessment,
 admission_input_note:'Use current registered terrain/GIS and the saved validated full Event geometry. No unverified metre accuracy is invented; historical incomplete Event fragments are not a production blocker claim.',
 unexecuted_steps:Array.from({length:15},(_,index)=>index+2),proof_generated:false,checkpoints_generated:false,
 iterations_used:0,required_temp_only_files:0,started_at_utc:new Date().toISOString()};
try{
 session=await openRuntime({fixture});
 const clean=await session.page.evaluate(()=>window.eventCandidate.cleanReference(249));
 const saved=await json(path.join(repo,v5,'evidence/runtime-diagnostic.json'));
 assert.equal(clean.raw_rgba_sha256,saved.frames[249].raw_rgba_sha256);
 assert.equal(clean.png_sha256,saved.frames[249].png_sha256);
 report.baseline_current_frame={frame:249,raw_rgba_sha256:clean.raw_rgba_sha256,png_sha256:clean.png_sha256,
  bit_exact:true,full250_new_run:false};
 report.renderer_guard=await session.page.evaluate(async({current,probes})=>{
  const THREE=await import('/three.js'),{createMapInfographicRenderer}=await import('/modules/renderer.mjs');
  const load=async p=>{const r=await fetch(p);if(!r.ok)throw Error('INPUT_HTTP_'+r.status);return r.json();};
  const [regional,continent,input]=await Promise.all([load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/input-manifest.json')]);
  const canvas=document.createElement('canvas'),gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
  const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});renderer.setPixelRatio(1);renderer.setSize(1080,1920,false);
  renderer.autoClear=false;renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
  let factory;
  try{
   factory=await createMapInfographicRenderer({canvas,plan:regional,layoutPlan:regional,
    contextTerrain:input.contextTerrain??continent.assets.terrain,contextGeometries:continent.geometries,
    heightSource:input.heightSource,width:1080,height:1920,outputRenderer:renderer,outputTarget:null});
   factory.updateCamera(current);const before=JSON.stringify(factory.evidence.cameraFrame),rows=[];
   for(const probe of probes){
    let failure=null;try{factory.updateCamera(probe.bounds);}catch(error){failure={message:error.message,code:error.code,category:error.category};}
    if(failure?.code!=='LOCAL_NOT_ADMITTED')throw Error('EXPECTED_ACTUAL_RENDERER_ADMISSION_REJECTION');
    if(JSON.stringify(factory.evidence.cameraFrame)!==before)throw Error('DENIED_CAMERA_CHANGED_NATIVE_STATE');
    rows.push({...probe,failure,actual_camera_unchanged:true});
   }
   return {status:'PASS',original_framing_accepted:true,narrower_framings_rejected:rows,
    evidence:'Actual unchanged native factory.updateCamera API, no omitted layoutPlan or forged detail plan',glError:gl.getError(),
    proof_frames_rendered:0};
  }finally{factory?.dispose();renderer.dispose();}
 },{current,probes:[{case:'WIDTH_ONLY',bounds:shrink(current,[.99,1])},
  {case:'HEIGHT_ONLY',bounds:shrink(current,[1,.99])},{case:'BOTH_AXES',bounds:shrink(current,[.99,.99])}]});
 assert.equal(report.renderer_guard.glError,0);assert.equal(session.errors.length,0);
 const bounds=[Math.min(...line.path.map(p=>p[0])),Math.min(...line.path.map(p=>p[1])),
  Math.max(...line.path.map(p=>p[0])),Math.max(...line.path.map(p=>p[1]))];
 report.detail_decision={geometry_requires_more_screen_space:true,decision:'DETAIL_APPROACH_REQUIRED',
  admission_blocked:true,target_framing:null,closest_permitted_framing:current,max_permitted_zoom_factor:1,
  projected_geometry_bounds:bounds,projected_geometry_length_pixels:line.visibleLengthPixels,safe_area:safe,
  current_axis_coverage:[(bounds[2]-bounds[0])/(safe[2]-safe[0]),(bounds[3]-bounds[1])/(safe[3]-safe[1])],
  maximum_permitted_axis_coverage:[(bounds[2]-bounds[0])/(safe[2]-safe[0]),(bounds[3]-bounds[1])/(safe[3]-safe[1])],
  pan_only_cannot_increase_screen_size:true,whole_geometry_visible:true,decision_algorithm_implemented:false};
 report.blockers=['CURRENT_ADMISSION_NO_ADDITIONAL_ZOOM','NATIVE_RENDERER_LOCKED_REGIONAL_MINIMUM_SPANS',
  'NATIVE_TERRAIN_DENSITY_EXCEEDS_DETAIL_POLICY','UNVERIFIED_GIS_METRE_ERROR_PREVENTS_CERTIFIED_CLOSER_REGIONAL_EXTENT'];
 report.v2_geometry_source_sha256=sha(await readFile(path.join(repo,productionFixture)));
 report.completed_at_utc=new Date().toISOString();
 await mkdir(path.join(directory,'evidence'),{recursive:true});
 const reportName=process.argv[2]??'BASELINE_ADMISSION_BLOCKED.json';
 if(!/^[A-Z0-9_\-]+\.json$/.test(reportName))throw Error('EXCLUSIVE_EVIDENCE_FILENAME_REQUIRED');
 await writeFile(path.join(directory,'evidence',reportName),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:report.status,baseline_current_frame_bit_exact:true,live_admission_zoom:false,
  actual_renderer_rejections:3,source_changes:0,proof_generated:false,report:path.join(directory,'evidence',reportName)}));
}finally{await session?.close();}
