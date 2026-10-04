// Real-time browser playback of the delivered MP4; separate from frame extraction.
import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const name=process.argv[2]||'master_cinematic_20s_v2.mp4';const stem=name.replace(/\.mp4$/,'');
const capture=!process.argv.includes('--no-capture'),mobile=process.argv.includes('--mobile');const validationStem=stem+(capture?'':'_replay')+(mobile?'_mobile':'');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,ignoreDefaultArgs:['--mute-audio'],args:['--no-sandbox','--autoplay-policy=no-user-gesture-required','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage({viewport:mobile?{width:375,height:667}:{width:1080,height:1920}});
 await page.goto('http://127.0.0.1:8020/outputs/');
 await page.setContent('<style>html,body{margin:0;background:#030910}video{width:100vw;height:100vh;object-fit:contain}</style><video id="v" playsinline preload="auto"></video>');
 await page.evaluate(async name=>{let v=document.getElementById('v');v.src=name;v.volume=.7;await new Promise((ok,no)=>{v.onloadedmetadata=ok;v.onerror=()=>no(new Error(v.error.message))});window.playbackTimes=[];let tick=(now,meta)=>{window.playbackTimes.push({now,mediaTime:meta.mediaTime,presentedFrames:meta.presentedFrames});if(!v.ended)v.requestVideoFrameCallback(tick)};v.requestVideoFrameCallback(tick);await v.play()},name);
 console.log('Playback started',name);
 await page.waitForFunction(()=>document.getElementById('v').currentTime>=Math.min(3,document.getElementById('v').duration*.33),null,{timeout:10000});
 if(capture)await page.screenshot({path:path.join(root,'outputs',stem+'_playback_early.png')});
 await page.waitForFunction(()=>document.getElementById('v').currentTime>=Math.min(14,document.getElementById('v').duration*.72),null,{timeout:20000});
 if(capture)await page.screenshot({path:path.join(root,'outputs',stem+'_playback_late.png')});
 await page.waitForFunction(()=>document.getElementById('v').ended,null,{timeout:12000});
 const result=await page.evaluate(()=>{let v=document.getElementById('v'),q=v.getVideoPlaybackQuality(),ts=window.playbackTimes;let gaps=ts.slice(1).map((x,i)=>x.mediaTime-ts[i].mediaTime);return {ended:v.ended,currentTime:v.currentTime,duration:v.duration,width:v.videoWidth,height:v.videoHeight,muted:v.muted,totalVideoFrames:q.totalVideoFrames,droppedVideoFrames:q.droppedVideoFrames,corruptedVideoFrames:q.corruptedVideoFrames,callbacks:ts.length,maxPresentedMediaGap:Math.max(...gaps),audioDecodedBytes:v.webkitAudioDecodedByteCount,videoError:v.error?.message||null}});
 await writeFile(path.join(root,'outputs',validationStem+'_playback_validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));if(!result.ended||result.videoError||result.currentTime<result.duration-.05)throw Error('Delivered movie did not play to completion');
}finally{await browser.close()}
