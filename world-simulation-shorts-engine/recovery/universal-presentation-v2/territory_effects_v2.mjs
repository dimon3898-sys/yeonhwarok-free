/** Reuses the Area V3 drawing pass for geometric differences only. */
import {analyzeTerritoryChanges,multi} from './territory_delta_v2.mjs';
const check=(v,c)=>{if(!v)throw Error('TERRITORY_EFFECT_'+c);};
const cache=new Map(),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function validateTerritoryEffects(spec,scene){
 check(spec?.profile==='HISTORICAL_STATES_V2'&&Object.keys(spec).every(k=>['profile','config','items'].includes(k)),'PROFILE');
 check(scene.event_type==='WAR'&&!scene.routes?.length&&!scene.front_lines?.length&&Array.isArray(spec.items)&&spec.items.length===scene.time_steps.length-1,'TERRITORY_ONLY');
 const signature=JSON.stringify([scene.geometries,scene.areas,scene.time_steps.map(s=>({area_ids:s.area_ids,id:s.id}))]);
 let analysis=cache.get(signature);if(!analysis){analysis=analyzeTerritoryChanges(scene);if(cache.size>=4)cache.delete(cache.keys().next().value);cache.set(signature,analysis);}
 for(const [i,e]of spec.items.entries()){
  const d=analysis.changes[i],s=scene.time_steps[i+1];
  check(Object.keys(e).every(k=>['fromStateId','toStateId','startFrame','endFrame','strength','added','removed'].includes(k)),'FIELDS');
  check(e.fromStateId===d.fromStateId&&e.toStateId===d.toStateId&&same(e.added,d.added)&&same(e.removed,d.removed),'SOURCE_DIFFERENCE_BINDING');
  check(e.startFrame===s.start_frame&&Number.isSafeInteger(e.endFrame)&&e.endFrame>=e.startFrame+3&&e.endFrame<=s.start_frame+s.transition_frames,'TIMING');
  check(Number.isFinite(e.strength)&&e.strength>=0&&e.strength<=1,'STRENGTH');
 }return structuredClone(spec);
}
export function territoryEffectsAt(spec,frame){
 if(!spec)return[];const rows=[];
 for(const [index,e]of spec.items.entries()){
  if(!e.strength||frame<e.startFrame||frame>=e.endFrame)continue;
  const u=(frame-e.startFrame)/(e.endFrame-e.startFrame-1),smooth=u*u*u*(10+u*(-15+6*u));
  for(const [kind,alpha]of [['added',Math.sin(Math.PI*u)**2*e.strength],['removed',(1-smooth)*e.strength]]){
   if(alpha<=1e-10||!multi(e[kind]).length)continue;
   rows.push({id:'DERIVED_DELTA_'+index+'_'+kind,kind,stateId:e.toStateId,geometry:e[kind],alpha,coverage:1});
  }
 }return rows;
}
