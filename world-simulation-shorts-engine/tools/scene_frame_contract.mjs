import {spawn} from 'node:child_process';

export class FrameFailure extends Error {
 constructor(code,details={}){super(code);this.code=code;this.details=details;}
}

// Browser console errors and draw invariants are independent sources of failure.
// Missing audit fields fail closed; non-finite values are checked before JSON
// serialization can turn NaN/Infinity into null.
export function auditFailures(audit,browserErrors=[]){
 if(!audit||typeof audit!=='object')return ['AUDIT_MISSING'];
 const failed=[];
 if(browserErrors.length)failed.push('BROWSER_ERROR');
 if(audit.webglError!==0)failed.push('WEBGL_ERROR');
 for(const [field,rule] of [['textClipped','TEXT_CLIPPED'],['entityClipped','ENTITY_CLIPPED'],['missingTextures','TEXTURE_MISSING'],['routeDiscontinuities','ROUTE_DISCONTINUITY']])
  if(!Array.isArray(audit[field])||audit[field].length)failed.push(rule);
 if(audit.routeInsideEarth!==false)failed.push('ROUTE_INSIDE_EARTH');
 if(audit.fontReady!==true)failed.push('FONT_NOT_READY');
 const finite=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
 if(!finite(audit.cameraPosition,3)||!finite(audit.cameraQuaternion,4)||!Number.isFinite(audit.cameraFov)||audit.cameraFov<=0||audit.cameraFov>=180)failed.push('CAMERA_NONFINITE');
 if((audit.entities||[]).some(e=>!finite(e.position,3)||!finite(e.quaternion,4)))failed.push('ENTITY_NONFINITE');
 if((audit.routeProgress||[]).some(r=>!Number.isFinite(r.progress)||r.progress<0||r.progress>1))failed.push('ROUTE_PROGRESS_INVALID');
 return failed;
}

export function validateJpeg(buffer,{width,height,decoded,decodeError=false,frameIndex,expectedIndex}){
 let rule=null;
 if(!Buffer.isBuffer(buffer)||buffer.length<4)rule='JPEG_EMPTY';
 else if(buffer[0]!==255||buffer[1]!==216||buffer.at(-2)!==255||buffer.at(-1)!==217)rule='JPEG_SIGNATURE_OR_TRUNCATION';
 else if(decodeError||!Array.isArray(decoded)||decoded.length!==2)rule='JPEG_DECODE_FAILED';
 else if(decoded[0]!==width||decoded[1]!==height)rule='JPEG_SIZE_MISMATCH';
 else if(!Number.isInteger(frameIndex)||frameIndex!==expectedIndex)rule='FRAME_SEQUENCE_INVALID';
 if(rule)throw new FrameFailure('SCENE_FRAME_INVALID',{failed_invariants:[rule],frame_index:frameIndex});
 return buffer;
}

export class FFmpegPipe {
 constructor(args,{executable='ffmpeg'}={}){
  this.child=spawn(executable,args,{stdio:['pipe','ignore','pipe']});this.stderr=[];this.result=null;this.inputError=null;
  this.child.stderr.on('data',data=>{this.stderr.push(String(data).slice(-2000));this.stderr=this.stderr.slice(-12);});
  this.child.stdin.on('error',error=>{this.inputError=error;});
  // Resolve early child exits instead of leaving an unobserved rejected promise.
  this.closed=new Promise(resolve=>{
   this.child.once('error',error=>{this.result={code:null,error:error.code};resolve(this.result);});
   this.child.once('close',(code,signal)=>{this.result={code,signal};resolve(this.result);});
  });
 }
 failure(){return new FrameFailure('FFMPEG_PIPE_FAILED',{failed_invariants:['ENCODER_PIPE_OR_EXIT'],return_code:this.result?.code??null});}
 async write(buffer){
  if(this.result||this.inputError||this.child.stdin.destroyed)throw this.failure();
  if(this.child.stdin.write(buffer))return;
  let clean;
  const drained=new Promise(resolve=>{
   const drain=()=>resolve(true),close=()=>resolve(false),error=()=>resolve(false);
   this.child.stdin.once('drain',drain);this.child.stdin.once('close',close);this.child.stdin.once('error',error);
   clean=()=>{this.child.stdin.off('drain',drain);this.child.stdin.off('close',close);this.child.stdin.off('error',error);};
  });
  const ok=await Promise.race([drained,this.closed.then(()=>false)]);clean();
  if(!ok||this.inputError)throw this.failure();
 }
 async finish(){
  this.child.stdin.end();const result=await this.closed;
  if(result.code!==0||this.inputError)throw this.failure();
 }
 async abort(){
  if(this.result)return;
  this.child.stdin.destroy();this.child.kill('SIGTERM');
  const timer=setTimeout(()=>this.child.kill('SIGKILL'),5000);
  await this.closed;clearTimeout(timer);
 }
}

export function encoderArguments({outputWidth,outputHeight,fps,quality,destination}){
 return ['-hide_banner','-loglevel','warning','-n','-f','image2pipe','-vcodec','mjpeg','-framerate',String(fps),'-i','pipe:0','-vf',`scale=${outputWidth}:${outputHeight}:flags=lanczos:in_range=full:out_range=limited:in_color_matrix=bt601:out_color_matrix=bt709,setsar=1,format=yuv420p`,'-c:v','libx264','-preset',quality==='FAST'?'medium':'slow','-crf',quality==='FAST'?'18':'15','-threads','4','-pix_fmt','yuv420p','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-bsf:v','h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1','-movflags','+faststart','-an',destination];
}
