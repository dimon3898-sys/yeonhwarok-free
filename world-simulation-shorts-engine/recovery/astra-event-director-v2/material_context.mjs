/** Runtime-only identity bridge for the actual composed terrain texture.
 * Texture handles never enter Scene JSON and never substitute a finished image.
 */
const records=new WeakMap(),owners=new WeakMap();
const validBounds=x=>Array.isArray(x)&&x.length===4&&x.every(Number.isFinite)&&x[0]<x[2]&&x[1]<x[3];
export function registerDirectorMaterialOwner(canvas,{owner,gl}={}){
 if(!canvas||!owner||typeof owner.draw!=='function'||typeof owner.dispose!=='function'
  ||typeof gl?.isTexture!=='function')throw Error('DIRECTOR_ACTUAL_MATERIAL_OWNER_REQUIRED');
 if(owners.has(canvas))throw Error('DIRECTOR_MATERIAL_OWNER_ALREADY_BOUND');
 owners.set(canvas,{owner,gl});
}
export function clearDirectorMaterialFrame(canvas,owner){
 const selected=owners.get(canvas);
 if(selected&&selected.owner!==owner)throw Error('DIRECTOR_MATERIAL_OWNER_MISMATCH');
 records.delete(canvas);
}
export function releaseDirectorMaterialOwner(canvas,owner){
 clearDirectorMaterialFrame(canvas,owner);owners.delete(canvas);
}
export function publishDirectorMaterialFrame(canvas,{owner,gl,texture,frame,bounds,diagnostic}={}){
 const selected=owners.get(canvas);
 if(!selected||selected.owner!==owner||selected.gl!==gl)throw Error('DIRECTOR_MATERIAL_OWNER_MISMATCH');
 if(!Number.isSafeInteger(frame)||frame<0||!validBounds(bounds))throw Error('DIRECTOR_MATERIAL_FRAME_BOUNDS_REQUIRED');
 if(!texture||gl.isTexture(texture)!==true)throw Error('DIRECTOR_ACTUAL_WEBGL_TEXTURE_REQUIRED');
 const record=Object.freeze({frame,bounds:Object.freeze([...bounds]),texture,
  sourceKind:'ACTUAL_COMPOSED_ASTRA_OR_SOURCE_FALLBACK_TEXTURE',
  originalMaterialOwner:owner,diagnostic,
  actualCombinedTexture:true,finishedFrameOverlay:false,
  historicalLightV3Connected:false,historicalLightV3Blocker:'SCALAR_CONTROL_SOURCE_REQUIRED',
  historicalLightV3DrawCount:0,nvidiaHardwareVerified:false,visualQualityApproved:false});
 records.set(canvas,record);return record;
}
export function readDirectorMaterialFrame(canvas,{frame,bounds,required=true}={}){
 const record=records.get(canvas),selected=owners.get(canvas);
 if(!record){if(required)throw Error('DIRECTOR_MATERIAL_FRAME_UNAVAILABLE');return null;}
 if(record.originalMaterialOwner!==selected?.owner||selected.gl.isTexture(record.texture)!==true)
  throw Error('DIRECTOR_MATERIAL_TEXTURE_INVALID');
 if(!Number.isSafeInteger(frame)||frame!==record.frame)throw Error('DIRECTOR_MATERIAL_STALE_FRAME');
 if(!validBounds(bounds)||bounds.some((x,i)=>x!==record.bounds[i]))throw Error('DIRECTOR_MATERIAL_BOUNDS_MISMATCH');
 return record;
}
/** Decorate one preserved factory result; no shader or renderer is copied. */
export function trackDirectorMaterialPass({canvas,pass}={}){
 const gl=canvas?.getContext?.('webgl2');
 registerDirectorMaterialOwner(canvas,{owner:pass,gl});let disposed=false,drawCount=0;
 return{evidence:{...pass.evidence,eventDirectorMaterial:{originalFactoryReused:true,
   runtimeTextureIdentityBridge:true,sourceBeforeAreaAndFront:true,shaderChanged:false,
   historicalLightV3Connected:false,historicalLightV3DrawCount:0,
   blocker:'SCALAR_CONTROL_SOURCE_REQUIRED',nvidiaHardwareVerified:false,visualQualityApproved:false}},
  get outputTexture(){if(disposed)throw Error('DIRECTOR_MATERIAL_DISPOSED');return pass.outputTexture;},
  get snapshotFrame(){if(disposed)throw Error('DIRECTOR_MATERIAL_DISPOSED');return pass.snapshotFrame;},
  draw(args){
   if(disposed)throw Error('DIRECTOR_MATERIAL_DISPOSED');
   clearDirectorMaterialFrame(canvas,pass);
   const result=pass.draw(args),record=publishDirectorMaterialFrame(canvas,{owner:pass,gl,
    texture:pass.outputTexture,frame:args?.frame,bounds:args?.bounds,diagnostic:result});
   drawCount++;
   return{...result,eventDirectorMaterial:{frame:record.frame,bounds:[...record.bounds],drawCount,
    actualCombinedTexture:true,textureIdentityStoredPrivately:true,finishedFrameOverlay:false,
    historicalLightV3Connected:false,historicalLightV3DrawCount:0,
    blocker:'SCALAR_CONTROL_SOURCE_REQUIRED',nvidiaHardwareVerified:false,visualQualityApproved:false}};
  },
  dispose(){if(disposed)return;releaseDirectorMaterialOwner(canvas,pass);disposed=true;pass.dispose();}};
}
