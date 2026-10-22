/** Paired actual-draw test: same qualified map/camera, one explicitly changed
 * synthetic route. This does not produce a Studio video or historical content. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {analyzePrompt} from '../prompt_pipeline.mjs';
import {captureGeneric} from '../capture_generic.mjs';
const own=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const hash=b=>createHash('sha256').update(b).digest('hex'),check=(v,c)=>{if(!v)throw Error(c);};
const args={};for(const arg of process.argv.slice(2)){const m=/^--(input|output-root|deps-root|frame|gates)=(.+)$/.exec(arg);check(m&&!args[m[1]],'UDP_PAIR_ARGUMENT_INVALID');args[m[1]]=m[2];}
const gates=JSON.parse(await fs.readFile(args.gates??path.join(own,'reports/GATES.json'),'utf8'));
for(const name of ['phaseA','phaseB','phaseC','phaseD','phaseE'])check(gates[name]?.status==='PASS','UDP_PAIR_'+name.toUpperCase()+'_GATE_REQUIRED');
check(gates.protection?.status==='PASS'&&gates.paidGpuExecuted===false&&gates.historicalG3==='BLOCKED','UDP_PAIR_PROTECTION_AND_FREE_SCOPE_REQUIRED');
const input=JSON.parse(await fs.readFile(args.input,'utf8'));check(input.simulationType!=='HISTORICAL','UDP_PAIR_SYNTHETIC_INPUT_REQUIRED');
const changed=structuredClone(input),facts=changed.scenes[0].facts,route=facts.routes[0];check(route,'UDP_PAIR_ROUTE_REQUIRED');
const geo=facts.geometries.find(g=>g.id===route.geometry_ref);check(geo?.geometry.type==='LineString'&&geo.geometry.coordinates.length>=3,'UDP_PAIR_MIDDLE_VERTEX_REQUIRED');
const index=Math.floor(geo.geometry.coordinates.length/2),before=[...geo.geometry.coordinates[index]];geo.geometry.coordinates[index][0]+=.2;
const after=[...geo.geometry.coordinates[index]],frame=Number(args.frame??45);await fs.mkdir(args['output-root'],{mode:0o700});
const receipt={schema:'WORLD_ENGINE_PAIRED_INPUT_PIXEL_PROBE_V1',status:'RUNNING',frame,changedField:{geometryId:geo.id,vertexIndex:index,before,after},nvidiaVerified:false,visualQualityApproved:false,paidExecuted:false,studioVideoClaimed:false,cases:[]};
for(const [id,prompt] of [['original',input],['changed',changed]]){
 const result=analyzePrompt(prompt);check(result.status==='PASS','UDP_PAIR_PROMPT_DID_NOT_PASS');const request=result.renderRequests[0];
 const sceneRaw=Buffer.from(JSON.stringify(request.scene,null,2)+'\n'),sceneFile=path.join(args['output-root'],id+'_SCENE.json');
 await fs.writeFile(sceneFile,sceneRaw,{flag:'wx',mode:0o600});await fs.writeFile(path.join(args['output-root'],id+'_PROMPT.json'),JSON.stringify(prompt,null,2)+'\n',{flag:'wx',mode:0o600});
 const outputRoot=path.join(args['output-root'],id),capture=await captureGeneric({sceneFile,outputRoot,expectedSHA256:hash(sceneRaw),sourceRegionId:request.renderSettings.sourceRegionId,
  depsRoot:args['deps-root']??process.env.WORLD_ENGINE_NODE_DEPS,inputTrace:{inputSHA256:result.inputSHA256,trace:request.inputTrace},probeFrames:[frame]});
 const drawn=JSON.parse(await fs.readFile(path.join(outputRoot,'FRAME_EVIDENCE.json'),'utf8')).frames[0];
 check(capture.status==='ACTUAL_DRAW_PROBE_PASS_NOT_STUDIO_VIDEO'&&drawn.diagnostic.featureChangedPixels>0,'UDP_PAIR_FEATURE_PIXEL_DRAW_REQUIRED');
 receipt.cases.push({id,inputSHA256:result.inputSHA256,sceneSHA256:hash(sceneRaw),outputRoot,baseRawSHA256:drawn.baseRawSHA256,rawSHA256:drawn.rawSHA256,
  geometryBinding:drawn.diagnostic.sourceGeometryBinding,camera:drawn.diagnostic.camera.actualFactory,material:drawn.diagnostic.material,features:drawn.diagnostic.features,
  featureChangedPixels:drawn.diagnostic.featureChangedPixels});
}
const [a,b]=receipt.cases;check(a.baseRawSHA256===b.baseRawSHA256,'UDP_PAIR_BASEMAP_UNEXPECTEDLY_CHANGED');
check(JSON.stringify(a.camera)===JSON.stringify(b.camera),'UDP_PAIR_CAMERA_UNEXPECTEDLY_CHANGED');check(a.rawSHA256!==b.rawSHA256,'UDP_PAIR_SUPPLIED_ROUTE_DID_NOT_CHANGE_PIXELS');
check(a.geometryBinding!==b.geometryBinding,'UDP_PAIR_SOURCE_BINDING_DID_NOT_CHANGE');
const originalFlow=a.features.find(f=>f.engine==='EXISTING_FLOW_V2'),changedFlow=b.features.find(f=>f.engine==='EXISTING_FLOW_V2');
check(JSON.stringify(originalFlow.projectedRoute)!==JSON.stringify(changedFlow.projectedRoute),'UDP_PAIR_PROJECTED_ROUTE_DID_NOT_CHANGE');
receipt.status='PAIRED_ACTUAL_SWIFTSHADER_DRAW_PASS';receipt.unchangedBasemapVerified=true;receipt.unchangedCameraVerified=true;receipt.changedInputChangedActualPixels=true;
await fs.writeFile(path.join(args['output-root'],'PAIRED_PIXEL_PROOF.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx',mode:0o600});
process.stdout.write(JSON.stringify({status:receipt.status,outputRoot:args['output-root']})+'\n');
