import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {validatePreviewRange,loadVerifiedPreview,assertRuntimeSlice,capturePreviewWithRuntime,writePreviewProgress} from '../preview_capture.mjs';
import {longEncodingArgs,assertEncodedSegment} from '../../universal-auto-video-v2/long_capture.mjs';
import {evaluateProductionGeometryClock} from '../../universal-production-v3/production_visual_profile.mjs';
import {suppliedFrontObservations} from '../../universal-integration-completion-v2/source_observations.mjs';

const here=fileURLToPath(new URL('../',import.meta.url)),execute=promisify(execFile),
 sourceFile=path.resolve(here,'../verified-front-data-v4-recovery/VIDEO_PLAN_80S.json'),
 raw=await readFile(sourceFile),plan=JSON.parse(raw),digest=createHash('sha256').update(raw).digest('hex'),
 range={startFrame:1450,endFrame:1600,fps:30,totalFrames:2400,frameCount:150,frameConvention:'GLOBAL_HALF_OPEN',localPtsFrameOrigin:0};

test('exact150 global range retains source clock while local encoded PTS start atzero',()=>{
 assert.equal(validatePreviewRange(range),range);
 for(const change of [{frameCount:2400},{endFrame:1601},{startFrame:-1},{localPtsFrameOrigin:1450},{fps:60},{unknown:true}])
  assert.throws(()=>validatePreviewRange({...range,...change}));
});

test('original FFmpeg settings select150 sequential local images without seeking or retiming source',()=>{
 const args=longEncodingArgs({framesDirectory:'/private/new/frames',outputFile:'/private/new/preview.mp4',frameCount:150,fps:30});
 assert.equal(args[args.indexOf('-framerate')+1],'30');assert.equal(args[args.indexOf('-frames:v')+1],'150');
 assert.equal(args[args.indexOf('-i')+1],'/private/new/frames/%06d.png');
 assert.ok(!args.includes('-ss')&&!args.includes('-sseof')&&!args.includes('-vf'));
 const probe={streams:[{codec_name:'h264',width:1080,height:1920,avg_frame_rate:'30/1',nb_frames:'150',duration:'5.000000'}]};
 assert.equal(assertEncodedSegment(probe,range),true);
 assert.throws(()=>assertEncodedSegment({streams:[{...probe.streams[0],nb_frames:'151'}]},range));
});

test('actual2400-frame source geometry slice equals originalglobal evaluation; no recreated initial state',async()=>{
 const front=JSON.parse(await readFile(path.resolve(here,'../verified-front-data-v4-recovery/FRONT_PROFILE.json'))),
  complete=suppliedFrontObservations(plan,front),selected=complete.slice(range.startFrame,range.endFrame);
 assert.equal(selected.length,150);assert.equal(selected[0].frame,1450);assert.equal(selected.at(-1).frame,1599);
 assert.notDeepEqual(selected[0],complete[0]);
 for(let local=0;local<150;local++){
  const global=1450+local,clock=evaluateProductionGeometryClock(plan,global);
  assert.equal(clock.globalFrame,global);assert.equal(selected[local],complete[global]);
  assert.equal(clock.coordinatesInterpolated,false);assert.equal(clock.eventDateFrontPrecisionClaimed,false);
 }
 assert.equal(evaluateProductionGeometryClock(plan,1450).fromStateId,'NORTH_ADVANCE');
 assert.equal(evaluateProductionGeometryClock(plan,1599).toStateId,'SEOUL_WITHDRAWAL');
});

test('runtime cannot mutateoriginalScene or presentsoftware asNVIDIA',()=>{
 const sourceScene=plan.scenes.find(row=>row.sceneId==='scene-0007'),
  loaded={document:plan,scene:sourceScene,planSha256:digest,assertSourceUnchanged:async()=>true},
  runtime={info:{backend:'ANGLE (SwiftShader Device)',testOnly:true},page:{evaluate(){}},errors:[],close(){}},
  request={bindings:{originalPlanSHA256:digest}},slice={sceneId:sourceScene.sceneId,startFrame:1450,endFrame:1600},
  input={plan:loaded,runtime,slice,request,planDocument:plan,softwareProbe:true};
 assert.equal(assertRuntimeSlice(input),true);
 assert.throws(()=>assertRuntimeSlice({...input,softwareProbe:false}),/SOFTWARE_FORBIDDEN/);
 assert.throws(()=>assertRuntimeSlice({...input,plan:{...loaded,scene:{...sourceScene,startFrame:0}}}),/SCENE_UNCHANGED/);
 assert.throws(()=>assertRuntimeSlice({...input,plan:{...loaded,document:{...plan,totalFrames:150}}}),/PLAN_UNCHANGED/);
 assert.throws(()=>assertRuntimeSlice({...input,runtime:{...runtime,info:{backend:'unknown',testOnly:true}}}),/SWIFTSHADER/);
});

test('raw plan/requestSHA verification issharedwith actualPythoncontract before anyruntime opens',async()=>{
 const directory=await mkdtemp(path.join(tmpdir(),'overnight-preview-contract-'));
 try{
  const planFile=path.join(directory,'PLAN.json'),requestFile=path.join(directory,'PREVIEW_REQUEST.json');
  await writeFile(planFile,raw,{flag:'wx'});
  const code="import json,sys;sys.path.insert(0,sys.argv[1]);import preview_contract as p;raw=open(sys.argv[2],'rb').read();b={'sourceCommit':'a'*40,'sourceManifestSHA256':'b'*64,'imageDigest':'sha256:'+'c'*64,'originalPlanSHA256':p.sha256(raw),'completionProfileSHA256':'d'*64,'sourceCatalogSHA256':'e'*64};print(json.dumps(p.compile_preview(json.loads(raw),bindings=b)))";
  const checked=await execute('/usr/bin/python3',['-B','-c',code,here,planFile]);
  await writeFile(requestFile,checked.stdout,{flag:'wx'});
  const result=await loadVerifiedPreview({planFile,requestFile,expectedPlanSha256:digest});
  assert.deepEqual(result.planDocument,plan);assert.deepEqual(result.request.range,range);
  const changed=JSON.parse(checked.stdout);changed.range.startFrame=0;await writeFile(requestFile,JSON.stringify(changed));
  await assert.rejects(loadVerifiedPreview({planFile,requestFile,expectedPlanSha256:digest}));
 }finally{await rm(directory,{recursive:true,force:true});}
});

test('softwareharness requires explicitmode andnever fallsbackfromproduction',async()=>{
 await assert.rejects(capturePreviewWithRuntime({softwareProbe:false}),/EXPLICIT_ONLY/);
 await assert.rejects(capturePreviewWithRuntime({softwareProbe:true}),/ACTUAL_SOFTWARE_RUNTIME/);
 const source=await readFile(path.join(here,'preview_capture.mjs'),'utf8');
 assert.ok(source.includes("import('./capture_runtime.mjs')"));
 assert.ok(source.includes('source.loadLongRuntimePlan({...options,sceneId})'));
 assert.ok(source.includes('source.openLongRuntime({...options,loadedPlan:plan})'));
 assert.ok(source.includes("hardwareVerified=!softwareProbe"));
});

test('CLI stdoutJSON publishes actualaggregate SCENE_CAPTURE progress acrossworkunits',async()=>{
 const entry=new URL('../preview_capture.mjs',import.meta.url).href,
  code=`import {writePreviewProgress} from ${JSON.stringify(entry)};
   writePreviewProgress({globalFrame:444,completedFrames:45,previewCompletedFrames:45,privateDetail:'NEVER_PUBLISH'});
   writePreviewProgress({globalFrame:474,completedFrames:30,previewCompletedFrames:75});
   writePreviewProgress({globalFrame:549,completedFrames:105,previewCompletedFrames:150});`;
 const childEnv={...process.env};delete childEnv.NODE_TEST_CONTEXT;
 // The managed Codex Node->Node pipe loses child stdout; a standard-library
 // relay captures the real child bytes without fabricating progress records.
 const relay="import subprocess,sys; r=subprocess.run([sys.argv[1],'--input-type=module','-e',sys.argv[2]],capture_output=True); sys.stdout.buffer.write(r.stdout); sys.stderr.buffer.write(r.stderr); sys.exit(r.returncode)";
 const result=await execute('/usr/bin/python3',['-B','-c',relay,process.execPath,code],{env:childEnv}),
  rows=result.stdout.trim().split('\n').map(line=>JSON.parse(line));
 assert.deepEqual(rows.map(row=>row.completedFrames),[45,75,150]);
 assert.ok(rows.every(row=>row.phase==='SCENE_CAPTURE'&&row.totalFrames===150));
 assert.deepEqual(rows.map(row=>row.globalFrame),[444,474,549]);assert.doesNotMatch(result.stdout,/NEVER_PUBLISH|privateDetail/);
 const source=await readFile(path.join(here,'preview_capture.mjs'),'utf8');
 assert.ok(source.includes('options.progress=value=>writePreviewProgress(value)'));
 assert.throws(()=>writePreviewProgress({globalFrame:4,completedFrames:151},{write(){}}),/ACTUAL_PROGRESS_COUNT/);
 assert.throws(()=>writePreviewProgress({globalFrame:4,completedFrames:1.5},{write(){}}),/ACTUAL_PROGRESS_COUNT/);
});
