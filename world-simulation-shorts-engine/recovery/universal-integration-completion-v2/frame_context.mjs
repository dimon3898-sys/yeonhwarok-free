/** Source clock only; deterministic per-frame evaluation, no GPU or camera edits. */
const contexts=new WeakMap();
let activeCanvas=null;
export function setFrameContext(canvas,context){
 if(!canvas||!Number.isSafeInteger(context?.frame)||context.frame<0)throw Error('COMPLETION_GLOBAL_FRAME_REQUIRED');
 contexts.set(canvas,Object.freeze({...context}));activeCanvas=canvas;
}
export function readFrameContext(canvas){return contexts.get(canvas)??null;}
export function publishNativeFrame(context){
 const previous=activeCanvas&&contexts.get(activeCanvas);
 if(!previous||context?.frame!==previous.frame||!Array.isArray(context.boundarySegments))
  throw Error('COMPLETION_NATIVE_CONTEXT_FRAME_MISMATCH');
 contexts.set(activeCanvas,Object.freeze({...previous,...context}));
}
export function clearFrameContext(canvas){contexts.delete(canvas);if(activeCanvas===canvas)activeCanvas=null;}
