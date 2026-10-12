#!/usr/bin/env node
// Ordered private validation and public media capture; never promotes Event FINAL.
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {once} from 'node:events';
import {promisify} from 'node:util';
import path from 'node:path';
import {repo,engine,runtime,WIDTH,HEIGHT,FPS,CAMERA_FRAME,productionFixture,sha,json,inventory,openRuntime,writeJson} from './candidate_runtime.mjs';
const execute=promisify(execFile);

function options(){
 const out={},args=process.argv.slice(2);
 for(let i=0;i<args.length;i+=2){if(!['--phase','--output-dir','--on-report'].includes(args[i])||!args[i+1])throw Error('USAGE: --phase off|on|grammar|video|checkpoints --output-dir NEW_DIRECTORY [--on-report REPORT]');out[args[i].slice(2)]=args[i+1];}
 if(!['off','on','grammar','video','checkpoints'].includes(out.phase)||!out['output-dir'])throw Error('PHASE_AND_NEW_OUTPUT_DIRECTORY_REQUIRED');
 return out;
}
function canonicalPng(encoded){
 if(!encoded.startsWith('data:image/png;base64,'))throw Error('CANONICAL_PNG_REQUIRED');
 const bytes=Buffer.from(encoded.slice('data:image/png;base64,'.length),'base64');
 if(bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||bytes.readUInt32BE(16)!==WIDTH||bytes.readUInt32BE(20)!==HEIGHT)throw Error('CANONICAL_PNG_REQUIRED');
 return bytes;
}
function checkFrame(row,fixture){
 assert.equal(row.glError,0,'WebGL error');
 assert.equal(row.frozenNativeSignatureUnchanged,true,'Native Camera/Reveal/Visual/layout changed');
 assert.equal(row.metricValue,fixture.intent.metric.display_value);assert.equal(row.metricUnit,fixture.intent.metric.unit);
 if(Object.hasOwn(row,'protected_changed_pixels')){assert.equal(row.protected_changed_pixels,0,'Protected native graphic pixels changed');assert.equal(row.outside_roi_changed_pixels,0,'Pixels outside Event ROI changed');}
}
function progress(frame,total){if(frame%15===0||frame===total-1)console.log(JSON.stringify({event:'FRAME_COMPLETE',frame,total}));}
async function main(){
 const opts=options(),out=path.resolve(opts['output-dir']);
 // Each phase creates a new exclusive directory and cannot replace saved evidence.
 if(out===repo||out===runtime)throw Error('NEW_EXCLUSIVE_PHASE_DIRECTORY_REQUIRED');
 await mkdir(path.dirname(out),{recursive:true});await mkdir(out);
 const {stdout:head}=await execute('git',['rev-parse','HEAD'],{cwd:repo});
 const inputs=await inventory(),fixture=await json(path.join(repo,productionFixture));
 const report={schema:1,state:'EVENT_SYSTEM_V1_CANDIDATE',phase:opts.phase,status:'STARTED',source_commit:head.trim(),
  user_video_review:'USER_VIDEO_REVIEW_REQUIRED',event_final:false,started_at_utc:new Date().toISOString(),
  viewport:[WIDTH,HEIGHT],fps:FPS,cameraFrame:CAMERA_FRAME,audio:false,required_inputs:inputs,frames:[],errors:[],
  command:{argv:[process.execPath,...process.argv.slice(1)],cwd:process.cwd()}};
 let session,encoder,encoderExit,encoderError='';
 try{
  if(opts.phase==='grammar'){
   if(!opts['on-report'])throw Error('COMPLETE_ON150_REPORT_REQUIRED');
   const on=await json(path.resolve(opts['on-report']));
   assert.equal(on.phase,'on');assert.equal(on.status,'PASS');assert.equal(on.frames.length,150);
   const timeline=on.eventPlan.timeline,states=timeline.map(x=>x.state);
   assert.deepEqual(states,['EVENT_READY','LINE_REVEAL','LINE_HOLD','METRIC_REVEAL','INFORMATION_HOLD']);
   assert.equal(on.eventPlan.totalFrames,150);assert.equal(on.eventPlan.fps,30);
   assert.equal(on.eventPlan.intent.data_mode,fixture.intent.data_mode);
   assert.deepEqual(on.eventPlan.intent.line,fixture.intent.line);assert.deepEqual(on.eventPlan.intent.metric,fixture.intent.metric);
   const fullText=`${fixture.intent.metric.display_value} ${fixture.intent.metric.unit}`;
   const graphemeCount=[...new Intl.Segmenter('ko',{granularity:'grapheme'}).segment(fullText)].length;
   const metricRows=on.frames.filter(row=>row.metric!==null),firstMetric=metricRows[0]?.metric;
   assert.ok(firstMetric,'Native measured Metric evidence required');
   assert.ok(firstMetric.atlasDimensions.every(value=>Number.isSafeInteger(value)&&value>0));
   assert.equal(firstMetric.baselines.length,1,'Fixed Metric must retain a single native baseline');
   assert.ok(firstMetric.baselines.every(value=>Number.isFinite(value)&&value>=0&&value<firstMetric.atlasDimensions[1]));
   const metricBeat=timeline.find(beat=>beat.state==='METRIC_REVEAL');
   assert.equal(metricRows.length,on.eventPlan.totalFrames-metricBeat.startFrame,'Complete native Metric coverage metadata required');
   let previousAlphas=Array.from({length:graphemeCount},()=>0);
   const nativeMeasurement={atlasDimensions:firstMetric.atlasDimensions,alphaBounds:firstMetric.alphaBounds,
    baselines:firstMetric.baselines,anchor:firstMetric.anchor};
   const reservation=metricRows[0].placement;
   assert.equal(reservation.reservationSpace,'FULL_MEASURED_ATLAS');
   assert.deepEqual(reservation.atlasDimensions,nativeMeasurement.atlasDimensions);
   for(const [index,row]of on.frames.entries()){
    assert.equal(row.eventFrame,index,'Evidence must cover every Event frame in order');
    const beat=timeline.find(x=>row.eventFrame>=x.startFrame&&row.eventFrame<x.endFrame);assert.equal(row.state,beat.state);checkFrame(row,fixture);
    if(['EVENT_READY','LINE_REVEAL','LINE_HOLD'].includes(row.state)){
     assert.equal(row.metricFraction,0,'Metric appeared before complete geographic line and hold');
     assert.equal(row.metric,null,'Native Metric pass appeared before its reveal beat');
    }
    if(['LINE_HOLD','METRIC_REVEAL','INFORMATION_HOLD'].includes(row.state))assert.equal(row.lineFraction,1);
    if(row.eventFrame>=metricBeat.startFrame){
     const metric=row.metric;assert.ok(metric,'Every Metric reveal/hold frame must have native glyph metadata');
     assert.equal(metric.text,fullText);assert.equal(metric.displayValue,fixture.intent.metric.display_value);assert.equal(metric.unit,fixture.intent.metric.unit);
     assert.equal(metric.fullReservation,true);assert.equal(metric.visibleFraction,row.metricFraction);
     assert.equal(metric.fullCoverage,row.metricFraction===1);assert.equal(metric.drawn,row.metricFraction>0);
     assert.deepEqual({atlasDimensions:metric.atlasDimensions,alphaBounds:metric.alphaBounds,baselines:metric.baselines,anchor:metric.anchor},nativeMeasurement,
      'Native glyph atlas, ink bounds, baseline or anchor changed during reveal');
     assert.deepEqual(row.placement,reservation,'Full measured reservation moved or resized during Metric reveal');
     const alphas=metric.graphemeAlphas;
     assert.equal(alphas.length,graphemeCount);assert.equal(metric.visibleGlyphCount,alphas.filter(alpha=>alpha>0).length);
     assert.ok(alphas.every(alpha=>Number.isFinite(alpha)&&alpha>=0&&alpha<=1));
     assert.ok(alphas.filter(alpha=>alpha>0&&alpha<1).length<=1,'Multiple graphemes partially revealed simultaneously');
     for(let glyph=0;glyph<graphemeCount;glyph++){
      assert.ok(alphas[glyph]>=previousAlphas[glyph],'Native grapheme coverage decreased');
      if(glyph>0&&alphas[glyph]>0)assert.equal(alphas[glyph-1],1,'Later native grapheme revealed before previous coverage completed');
     }
     if(row.metricFraction===0)assert.ok(alphas.every(alpha=>alpha===0));
     if(row.metricFraction===1)assert.ok(alphas.every(alpha=>alpha===1));
     previousAlphas=[...alphas];
    }
   }
   for(const state of ['LINE_HOLD','INFORMATION_HOLD']){
    const rows=on.frames.filter(x=>x.state===state);assert.ok(rows.length);assert.equal(new Set(rows.map(x=>x.raw_rgba_sha256)).size,1,state+' changed during hold');
   }
   Object.assign(report,{reference:{source:'Saved Core README full-video semantic audit',upload_sha256:'853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc',
    direct_video_identity_comparison:'NOT_REESTABLISHED_FROM_SAVED_SEMANTIC_AUDIT',timing:'EXPLICIT_GENERATOR_PROFILE_NOT_REFERENCE_FRAME_NUMBERS'},
    criteria:{geographic_line_first:'PASS',brief_complete_line_hold:'PASS',fixed_measured_glyph_reveal:'PASS',stable_information_hold:'PASS',
     supplied_metric_fixed_no_count_up:'PASS',sequential_native_grapheme_coverage:'PASS',fixed_native_atlas_and_baseline:'PASS',
     stable_full_measured_reservation:'PASS',protected_camera_marker_text_layout:'PASS'},
    native_glyph_evidence:{frames:metricRows.length,grapheme_count:graphemeCount,...nativeMeasurement,
     reservation:reservation.box,coverage_order:'COMPLETE_PREFIX_THEN_AT_MOST_ONE_PARTIAL_GRAPHEME_THEN_UNREVEALED_SUFFIX'},eventPlan:on.eventPlan,
    on_report:{path:path.relative(repo,path.resolve(opts['on-report'])),sha256:sha(await readFile(path.resolve(opts['on-report'])))} });
  }else{
   session=await openRuntime({fixture,includeV5:opts.phase==='off'});
   Object.assign(report,{chromium:'154.0.8037.57',node:process.version,backend:session.info.backend,pipeline:session.info.pipeline,eventPlan:session.info.eventPlan});
   assert.equal(session.info.cameraPlan.totalFrames,250);assert.equal(session.info.eventPlan.totalFrames,150);assert.equal(session.info.eventPlan.fps,FPS);
   const original=await json(path.join(engine,'recovery/v5/evidence/runtime-diagnostic.json'));
   const clean=await json(path.join(engine,'recovery/v5/evidence/final/clean-video/runtime-diagnostic.json'));
   assert.equal(original.frames.length,250);assert.equal(clean.frames.length,250);
   for(let i=0;i<250;i++){assert.equal(original.frames[i].frame,i);assert.deepEqual(original.frames[i],clean.frames[i]);}
   if(opts.phase==='off'){
    report.comparison='BIT_EXACT';report.reference='UNCHANGED_V5_PIPELINE_AND_BOTH_SAVED_FULL250_INVENTORIES';
    for(let frame=0;frame<250;frame++){
     const row=await session.page.evaluate(frame=>window.eventCandidate.off(frame),frame),expected=original.frames[frame];
     assert.equal(row.changed_bytes,0);assert.equal(row.raw_rgba_sha256,expected.raw_rgba_sha256);assert.equal(row.base_raw_rgba_sha256,expected.raw_rgba_sha256);
     assert.equal(row.png_sha256,expected.png_sha256);assert.equal(row.base_png_sha256,expected.png_sha256);
     assert.equal(row.eventEvaluated,false);assert.equal(row.eventDraws,false);assert.equal(row.glError,0);
     report.frames.push(row);progress(frame,250);
    }
   }else{
    report.cleanReference=await session.page.evaluate(frame=>window.eventCandidate.cleanReference(frame),CAMERA_FRAME);
    assert.equal(report.cleanReference.raw_rgba_sha256,original.frames[CAMERA_FRAME].raw_rgba_sha256);
    assert.equal(report.cleanReference.png_sha256,original.frames[CAMERA_FRAME].png_sha256);
    const captures=opts.phase==='checkpoints'?[0,1,30,59,74,75,90,104,149]:Array.from({length:150},(_,i)=>i);
    if(opts.phase==='video'){
     const video=path.join(out,'SUEZ_EVENT_SYSTEM_V1_CANDIDATE_5S_SILENT.mp4');
     const args=['-hide_banner','-loglevel','error','-nostdin','-f','image2pipe','-framerate',String(FPS),'-vcodec','png','-threads','2','-i','pipe:0',
      '-an','-c:v','libx264','-preset','faster','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video];
     report.encode_command=['ffmpeg',...args];encoder=spawn('ffmpeg',args,{stdio:['pipe','ignore','pipe']});
     encoder.stderr.on('data',chunk=>{encoderError=(encoderError+chunk).slice(-8192);});
     encoder.stdin.on('error',error=>{encoderError+=' '+error.message;});
     encoderExit=new Promise((resolve,reject)=>{encoder.once('error',reject);encoder.once('exit',(code,signal)=>resolve({code,signal}));});
    }
    for(const eventFrame of captures){
     const row=await session.page.evaluate(({cameraFrame,eventFrame,protect,png})=>window.eventCandidate.capture(cameraFrame,eventFrame,{protect,png}),
      {cameraFrame:CAMERA_FRAME,eventFrame,protect:opts.phase==='on',png:['video','checkpoints'].includes(opts.phase)});
     checkFrame(row,fixture);
     if(row.png){
      const bytes=canonicalPng(row.png);row.png_sha256=sha(bytes);delete row.png;
      if(encoder&&!encoder.stdin.write(bytes))await once(encoder.stdin,'drain');
      if(opts.phase==='checkpoints'){
       const name=String(report.frames.length+1).padStart(2,'0')+'_'+row.state+'_F'+String(eventFrame).padStart(3,'0')+'.png';
       await writeFile(path.join(out,name),bytes,{flag:'wx'});row.checkpoint={path:name,sha256:sha(bytes),bytes:bytes.length};
      }
     }
     report.frames.push(row);progress(eventFrame,150);
    }
    if(opts.phase==='on'){
     assert.equal(report.frames[0].changed_pixels,0);assert.ok(report.frames.at(-1).changed_pixels>0);
     for(let i=1;i<150;i++){assert.ok(report.frames[i].lineFraction>=report.frames[i-1].lineFraction);assert.ok(report.frames[i].metricFraction>=report.frames[i-1].metricFraction);}
     for(const state of ['LINE_HOLD','INFORMATION_HOLD'])assert.equal(new Set(report.frames.filter(x=>x.state===state).map(x=>x.raw_rgba_sha256)).size,1);
     report.protection={frames:150,outside_roi_changed_pixels:0,protected_changed_pixels:0,native_diagnostics_unchanged:true,
      marker:'ENTIRE_PROTECTED_GEOGRAPHIC_MARKER_RECTANGLE_BIT_EXACT',geometry:'SUPPLIED_IMMUTABLE_EVENT_GEOMETRY',arc_length:'MONOTONIC_UNINTERRUPTED_CONTROL_SEQUENCE'};
    }
    report.offRestored=await session.page.evaluate(frame=>window.eventCandidate.cleanReference(frame),CAMERA_FRAME);
    assert.equal(report.offRestored.raw_rgba_sha256,report.cleanReference.raw_rgba_sha256);assert.equal(report.offRestored.png_sha256,report.cleanReference.png_sha256);
    if(encoder){
     encoder.stdin.end();const ended=await encoderExit;if(ended.code!==0)throw Error('ENCODER_FAILED: '+encoderError);
     const video=path.join(out,'SUEZ_EVENT_SYSTEM_V1_CANDIDATE_5S_SILENT.mp4');
     const {stdout}=await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video],{maxBuffer:1048576});
     report.ffprobe=JSON.parse(stdout);const stream=report.ffprobe.streams[0];
     assert.equal(report.ffprobe.streams.length,1);assert.equal(stream.codec_type,'video');assert.equal(stream.codec_name,'h264');
     assert.equal(stream.width,WIDTH);assert.equal(stream.height,HEIGHT);assert.equal(stream.avg_frame_rate,'30/1');assert.equal(Number(stream.nb_read_frames),150);
     assert.ok(Math.abs(Number(stream.duration)-5)<.001);
     const bytes=await readFile(video);report.video={path:path.basename(video),sha256:sha(bytes),bytes:bytes.length,frames:150,duration_seconds:5,audio_streams:0};
    }
   }
   assert.equal(await session.page.evaluate(()=>window.eventCandidate.unchanged()),true);
   assert.equal(session.errors.length,0);report.server_stderr=session.serverError();
  }
  assert.deepEqual(await inventory(),inputs,'Required source/assets changed during capture');
  report.status='PASS';report.command.exit_code=0;
 }catch(error){report.status='FAIL';report.command.exit_code=1;report.errors.push(String(error.stack??error));throw error;}
 finally{
  if(encoder&&!encoder.stdin.destroyed)encoder.stdin.destroy();if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
  try{await session?.close();}finally{report.completed_at_utc=new Date().toISOString();await writeJson(path.join(out,'REPORT.json'),report);}
 }
 console.log(JSON.stringify({phase:opts.phase,status:report.status,frames:report.frames.length,report:path.join(out,'REPORT.json'),event_final:false}));
}
main().catch(error=>{console.error(String(error.stack??error));process.exitCode=1;});
