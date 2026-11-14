/** Data-only, half-open source frame windows. Shared by validation and renderer. */
export const WINDOW_RUNTIME_PROFILE='HISTORICAL_AUTHORED_WINDOW_V2';
const check=(value,code)=>{if(!value)throw Error('UP2_WINDOW_'+code);};
export function validateTimelineWindow(window,sourceFrames,outputFrames){
 check(Number.isSafeInteger(sourceFrames)&&sourceFrames>=2,'SOURCE_FRAMES');
 if(window===undefined||window===null){
  check(outputFrames===undefined||outputFrames===sourceFrames,'LEGACY_TIMING');
  return {startFrame:0,endFrame:sourceFrames,totalFrames:sourceFrames};
 }
 check(window&&typeof window==='object'&&!Array.isArray(window)&&Object.keys(window).length===2&&Object.keys(window).every(k=>['startFrame','endFrame'].includes(k)),'FIELDS');
 const {startFrame,endFrame}=window;
 check(Number.isSafeInteger(startFrame)&&Number.isSafeInteger(endFrame)&&startFrame>=0&&endFrame>startFrame&&endFrame<=sourceFrames,'RANGE');
 check(outputFrames===undefined||endFrame-startFrame===outputFrames,'OUTPUT_LENGTH');
 return {startFrame,endFrame,totalFrames:endFrame-startFrame};
}
export function sourceFrameForWindow(localFrame,window,sourceFrames){
 const selected=validateTimelineWindow(window,sourceFrames);
 check(Number.isSafeInteger(localFrame)&&localFrame>=0&&localFrame<selected.totalFrames,'LOCAL_FRAME');
 return selected.startFrame+localFrame;
}
