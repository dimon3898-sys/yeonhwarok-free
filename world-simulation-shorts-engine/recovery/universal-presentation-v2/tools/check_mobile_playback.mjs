/** Read-only playback of HTTPS-downloaded MP4s in Android-emulated Chromium. */
import {readFile,writeFile,lstat,realpath} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import path from 'node:path';

const root=process.argv[2],output=process.argv[3],deps=process.argv[4];
const check=(v,c)=>{if(!v)throw Error(c);},hash=x=>createHash('sha256').update(x).digest('hex');
check([root,output,deps].every(p=>typeof p==='string'&&path.isAbsolute(p)),'PLAYBACK_ABSOLUTE_PATHS_REQUIRED');
const names=['0-UP2_AVIATION_EUROPE.mp4','1-UP2_TRADE_SOUTH_AMERICA.mp4','2-UP2_FICTIONAL_AFRICA.mp4'];
const expected=['cec3447d1f2b932bc2c55de5156300194f30eb7ed806f6732fbfdde2fe53a8b8','28befce9d5ff11d05e5f9f4e989e1d16b278b1489386710b8a06cc74bd7bf1dc','c831b90282022ce58b7112b06498018a4227830cbceca11866e9d7c99440caf6'];
const files=[];
for(const[index,name]of names.entries()){
 const file=path.join(root,name),stat=await lstat(file);check(stat.isFile()&&!stat.isSymbolicLink()&&(await realpath(file))===file,'PLAYBACK_REGULAR_VERIFIED_FILE_REQUIRED');
 const sha256=hash(await readFile(file));check(sha256===expected[index],'PLAYBACK_DOWNLOADED_SHA_MISMATCH');files.push({file,name,bytes:stat.size,sha256});
}
const requests=[],errors=[];let origin,browser;
const html='<!doctype html><html lang="ko"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Downloaded video playback verification</title><body style="margin:0;background:#111"><video id="video" playsinline controls muted preload="metadata" style="display:block;width:100%;max-height:100vh"></video></body></html>';
const server=createServer(async(req,res)=>{
 try{
  check(['GET','HEAD'].includes(req.method)&&req.headers.host===new URL(origin).host,'PLAYBACK_READ_ONLY_LOOPBACK_REQUIRED');
  if(req.url==='/'){res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store'});res.end(req.method==='HEAD'?undefined:html);return;}
  const match=/^\/video\/([012])\.mp4$/.exec(req.url??'');check(match,'PLAYBACK_PATH_NOT_ALLOWLISTED');const item=files[Number(match[1])];let start=0,end=item.bytes-1,status=200;
  const headers={'content-type':'video/mp4','accept-ranges':'bytes','cache-control':'no-store','x-content-type-options':'nosniff'};
  if(req.headers.range){const range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range);check(range,'PLAYBACK_SINGLE_VALID_RANGE_REQUIRED');start=Number(range[1]);end=range[2]?Number(range[2]):end;
   check(Number.isSafeInteger(start)&&Number.isSafeInteger(end)&&start>=0&&start<=end&&end<item.bytes,'PLAYBACK_RANGE_OUT_OF_BOUNDS');status=206;headers['content-range']=`bytes ${start}-${end}/${item.bytes}`;}
  headers['content-length']=String(end-start+1);requests.push({video:item.name,status,range:[start,end]});res.writeHead(status,headers);
  if(req.method==='HEAD')res.end();else createReadStream(item.file,{start,end}).on('error',()=>res.destroy()).pipe(res);
 }catch(error){errors.push(String(error.message));res.writeHead(404);res.end();}
});
const report={schema:'WORLD_ENGINE_ANDROID_EMULATED_BROWSER_PLAYBACK_V2',status:'RUNNING',scope:'READ_ONLY_ACTUAL_HTTPS_DOWNLOADS_LOOPBACK_PLAYBACK',physicalAndroidPhoneTested:false,nvidiaVerified:false,visualQualityApproved:false,paidExecuted:false,sourceFilesModified:false,checks:[]};
try{
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});origin='http://127.0.0.1:'+server.address().port;
 const require=createRequire(path.join(deps,'package.json')),{chromium}=require('playwright');browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 report.browser={chromium:browser.version(),playwright:require('playwright/package.json').version,emulation:{viewport:{width:412,height:915},deviceScaleFactor:1,isMobile:true,hasTouch:true,userAgent:'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36'}};
 const context=await browser.newContext(report.browser.emulation);await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));await page.goto(origin,{waitUntil:'load'});
 for(const[index,item]of files.entries()){
  const result=await page.evaluate(async index=>{
   const video=document.querySelector('video'),wait=(name,timeout=20000)=>new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{cleanup();reject(Error('PLAYBACK_TIMEOUT_'+name));},timeout),done=()=>{cleanup();resolve();},failed=()=>{cleanup();reject(Error('PLAYBACK_MEDIA_ERROR_'+(video.error?.code??'unknown')));};
    function cleanup(){clearTimeout(timer);video.removeEventListener(name,done);video.removeEventListener('error',failed);}video.addEventListener(name,done,{once:true});video.addEventListener('error',failed,{once:true});
   }),stats=()=>{const q=video.getVideoPlaybackQuality?.();return{totalVideoFrames:q?.totalVideoFrames??null,droppedVideoFrames:q?.droppedVideoFrames??null,corruptedVideoFrames:q?.corruptedVideoFrames??null,webkitDecodedFrameCount:video.webkitDecodedFrameCount??null,webkitDroppedFrameCount:video.webkitDroppedFrameCount??null};};
   video.pause();video.removeAttribute('src');video.load();video.src='/video/'+index+'.mp4';const metadata=wait('loadedmetadata');video.load();await metadata;
   const actual={width:video.videoWidth,height:video.videoHeight,durationSeconds:video.duration,h264CanPlayType:video.canPlayType('video/mp4; codecs="avc1.640028"'),muted:video.muted,playsInline:video.playsInline};
   const ended=wait('ended');await video.play();const atStart=video.currentTime;await new Promise(resolve=>setTimeout(resolve,350));actual.playAdvanceSeconds=video.currentTime-atStart;actual.playing=!video.paused;await ended;
   actual.reachedEnded=video.ended;actual.fullPlaybackTime=video.currentTime;actual.afterFullPlayback=stats();actual.mediaError=video.error?{code:video.error.code,message:video.error.message}:null;
   const seeked=wait('seeked');video.currentTime=2;await seeked;actual.seekedTime=video.currentTime;await video.play();const before=video.currentTime;await new Promise(resolve=>setTimeout(resolve,350));actual.seekReplayAdvanceSeconds=video.currentTime-before;video.pause();actual.afterSeekReplay=stats();return actual;
  },index);
  check(result.width===1080&&result.height===1920&&Math.abs(result.durationSeconds-6)<.001,'PLAYBACK_MEDIA_METADATA_MISMATCH');
  check(result.h264CanPlayType&&result.playAdvanceSeconds>.05&&result.playing&&result.reachedEnded&&Math.abs(result.fullPlaybackTime-6)<.05&&!result.mediaError,'PLAYBACK_FULL_VIDEO_FAILED');
  check(Math.abs(result.seekedTime-2)<.05&&result.seekReplayAdvanceSeconds>.05,'PLAYBACK_SEEK_REPLAY_FAILED');
  const after=hash(await readFile(item.file));check(after===item.sha256,'PLAYBACK_SOURCE_FILE_CHANGED');report.checks.push({name:item.name,status:'PASS',sha256:item.sha256,bytes:item.bytes,sourceSHAUnchanged:true,...result});
 }
 check(errors.length===0,'PLAYBACK_SERVER_OR_BROWSER_ERROR');report.status='PASS';
}catch(error){report.status='FAIL';report.failure={code:String(error.message)};throw error;}
finally{await browser?.close();await new Promise(resolve=>server.close(resolve));report.serverRequests=requests;report.errors=errors;await writeFile(output,JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o644});process.stdout.write(JSON.stringify({status:report.status,checks:report.checks.map(c=>({name:c.name,status:c.status,afterFullPlayback:c.afterFullPlayback,seekedTime:c.seekedTime})),physicalAndroidPhoneTested:false,nvidiaVerified:false,visualQualityApproved:false,paidExecuted:false})+'\n');}
