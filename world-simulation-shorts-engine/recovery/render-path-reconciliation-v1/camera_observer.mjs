export * from '/production-v3/reconciliation_parent_camera.mjs';
import {createProductionNativeCamera as createOriginal} from '/production-v3/reconciliation_parent_camera.mjs';
import {observedFactory,observeExistingDraw} from '/reconciliation/pass_observer.mjs';
export function createProductionNativeCamera(options){
 const owner=createOriginal(options);observedFactory('PRESERVED_V5_CAMERA');
 return new Proxy(owner,{get(target,key){
  if(key==='drawNative')return frame=>observeExistingDraw('PRESERVED_V5_CAMERA',document.querySelector('canvas'),()=>target.drawNative(frame));
  const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
 }});
}
