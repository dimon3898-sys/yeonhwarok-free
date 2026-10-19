export * from '/reference/reconciliation_parent_source.mjs';
import {createReferenceTerrainMaterialPassV4 as createOriginal} from '/reference/reconciliation_parent_source.mjs';
import {observedFactory,observeExistingDraw} from '/reconciliation/pass_observer.mjs';
export async function createReferenceTerrainMaterialPassV4(options){
 const owner=await createOriginal(options);observedFactory('ASTRA_REFERENCE_SOURCE');
 return new Proxy(owner,{get(target,key){
  if(key==='draw')return args=>observeExistingDraw('ASTRA_REFERENCE_SOURCE',options.canvas,()=>target.draw(args));
  const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
 }});
}
export const createMapTerrainMaterialPassV4=createReferenceTerrainMaterialPassV4;
