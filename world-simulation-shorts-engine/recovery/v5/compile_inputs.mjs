#!/usr/bin/env node
// Bind preserved geographic inputs to the V5 camera. No rendering or Reveal logic.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {compileMinimumContextPlan} from '../../web/map_infographic_v1/camera_director_v5.mjs';

const directory=path.dirname(fileURLToPath(import.meta.url));
const engine=path.resolve(directory,'../..'),repo=path.dirname(engine);
const baselineDirectory=path.join(engine,'recovery/v4');
const expectedManifestSha='24bf44dc623991cc8c8fabf00a3f8df6f1f66af083b13b1c2953d00a058693b0';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');

export function sceneFromPreservedIntent(intent,texts){
 return {
  primary_region_id:intent.primaryRegionId,primary_geometry:structuredClone(intent.primaryGeometry),
  event_anchor:[...intent.anchor],event_geometry:structuredClone(intent.eventGeometry),
  context_geometry:structuredClone(intent.contextGeometry),
  primary_label:texts.primary_label,location_label:texts.location_label,event_title:texts.event_title,
  canonical_output:[...intent.display.canonicalOutput],safe_area:[...intent.display.safeArea],
  start_extent:[...intent.startExtent],approved_final_extent:[...intent.approvedFinalExtent],
  desired_detail_level:intent.requestedScale,
  scale_admission:{localDetail:{admission:{status:intent.admission.status,
   renderLocal:intent.admission.localUsed},safeClosest:{bounds:[...intent.approvedFinalExtent],
   status:intent.admission.safeClosestStatus}}}
 };
}

export async function compileFixtureInputs(){
 const sources={};
 async function load(relative){
  const file=path.join(repo,relative),bytes=await readFile(file);
  sources[relative]={sha256:sha(bytes),bytes:bytes.length};return JSON.parse(bytes);
 }
 const prefix=path.relative(repo,baselineDirectory).split(path.sep).join('/');
 const baseline=await load(prefix+'/BASELINE_MANIFEST.json');
 if(sources[prefix+'/BASELINE_MANIFEST.json'].sha256!==expectedManifestSha||
    baseline.baseline_name!=='V4_RECOVERED_EQUIVALENT_BASELINE')throw Error('BASELINE_IDENTITY_MISMATCH');
 const preserved=await load(prefix+'/V4-state-records/camera-plan.json');
 const texts=await load(prefix+'/equivalent-plans/scene.json');
 const scene=sceneFromPreservedIntent(preserved.intent,texts);
 const cameraPlan=compileMinimumContextPlan({scene,seed:0});
 if(cameraPlan.directorVersion!=='CAMERA_DIRECTOR_V5'||cameraPlan.implementationStage!=='NATURAL_TURNAROUND')
  throw Error('NATURAL_TURNAROUND_NOT_IMPLEMENTED');
 if(JSON.stringify(cameraPlan.intent.finalExtent)!==JSON.stringify(preserved.intent.finalExtent))
  throw Error('APPROVED_FINAL_FRAMING_CHANGED');
 if(JSON.stringify(cameraPlan.anchor)!==JSON.stringify(preserved.anchor))throw Error('MARKER_ANCHOR_CHANGED');
 if(cameraPlan.admission.status!=='LOCAL_NOT_ADMITTED'||cameraPlan.admission.localUsed)
  throw Error('BASELINE_LOCAL_ADMISSION_CHANGED');
 return {scene,cameraPlan,provenance:{schema:1,state:'V5_CANDIDATE',
  baseline_name:baseline.baseline_name,baseline_source_commit:baseline.commit,
  baseline_manifest_sha256:expectedManifestSha,sources,
  input_binding:'Exact saved geographic fields and text; new generic V5 camera compilation only',
  renderer_visual_layout_scale_reveal:'UNCHANGED',original_v4_plan_claim:false}};
}

async function main(){
 const args=process.argv.slice(2);
 if(args.length!==2||args[0]!=='--output-dir')throw Error('USAGE: compile_inputs.mjs --output-dir NEW_DIRECTORY');
 const target=path.resolve(args[1]);await mkdir(target);
 const result=await compileFixtureInputs();
 for(const [name,value]of [['scene.json',result.scene],['camera-plan.json',result.cameraPlan],
   ['INPUT_PROVENANCE.json',result.provenance]])
  await writeFile(path.join(target,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({state:'V5_CANDIDATE',totalFrames:result.cameraPlan.totalFrames,
  contextSkipped:result.cameraPlan.intent.context.minimumContextSkipped,
  contextExtent:result.cameraPlan.intent.contextExtent,finalExtent:result.cameraPlan.intent.finalExtent}));
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))
 main().catch(error=>{console.error(String(error.message));process.exitCode=1;});
