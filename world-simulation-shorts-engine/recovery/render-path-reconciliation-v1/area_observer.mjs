export * from '/production-v3/reconciliation_parent_area.mjs';
import {createProductionAreaPass as createOriginal} from '/production-v3/reconciliation_parent_area.mjs';
import {observedFactory,observeExistingDraw} from '/reconciliation/pass_observer.mjs';
export function createProductionAreaPass(options){
 const owner=createOriginal(options);observedFactory('SUPPLIED_AREA_FRONT');
 return new Proxy(owner,{get(target,key){
  if(key==='draw')return args=>observeExistingDraw('SUPPLIED_AREA_FRONT',options.canvas,()=>target.draw(args));
  const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
 }});
}
