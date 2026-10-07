// Synthetic transport fixture only. Does not create a browser or render a map.
import fs from 'node:fs';
import {encoderArguments,FFmpegPipe,validateJpeg} from './scene_frame_contract.mjs';
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const pipe=new FFmpegPipe(encoderArguments(fixture));
try{
 for(let i=0;i<fixture.frames.length;i++){
  const frame=fixture.frames[i],buffer=fs.readFileSync(frame.path);
  validateJpeg(buffer,{width:fixture.internalWidth,height:fixture.internalHeight,decoded:frame.decoded,frameIndex:i,expectedIndex:i});
  await pipe.write(buffer);
 }
 await pipe.finish();
 console.log(JSON.stringify({passed:true,frames:fixture.frames.length,code:pipe.result.code,scope:'Synthetic JPEG image2pipe transport; no WebGL/GPU scene'}));
}finally{await pipe.abort();}
