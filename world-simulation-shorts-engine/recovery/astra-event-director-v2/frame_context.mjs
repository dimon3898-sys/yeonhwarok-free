/** Private in-browser owner references, never serialized into public provenance. */
const owners=new WeakMap();
export function publishDirectorNativeOwner(canvas,native,metadata={}){
 if(!canvas||!native?.factory||!native?.renderer?.isWebGLRenderer||typeof native.project!=='function')
  throw Error('DIRECTOR_ACTUAL_NATIVE_OWNER_REQUIRED');
 const prior=owners.get(canvas);if(prior&&prior.native!==native)throw Error('DIRECTOR_NATIVE_OWNER_CANNOT_CHANGE');
 owners.set(canvas,{native,...metadata});
}
export function readDirectorNativeOwner(canvas){return owners.get(canvas)??null;}
export function clearDirectorNativeOwner(canvas){owners.delete(canvas);}
