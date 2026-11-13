import {CONTINUOUS_PROFILE,continuousTerritoryAt,validateDerivedGeometry} from './continuous_territory_runtime.mjs';
/** Reuses the Area V3 drawing pass for geometric differences only. */
import {analyzeTerritoryChanges,multi} from './territory_delta_v2.mjs';
const check=(v,c)=>{if(!v)throw Error('TERRITORY_EFFECT_'+c);};
const cache=new Map(),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function validateTerritoryEffects(spec,scene){
 check(['HISTORICAL_STATES_V2','HISTORICAL_STATES_V3',CONTINUOUS_PROFILE].includes(spec?.profile)&&Object.keys(spec).every(k=>['profile','config','items'].includes(k)),'PROFILE');
 check(scene.event_type==='WAR'&&!scene.routes?.length&&!scene.front_lines?.length&&Array.isArray(spec.items)&&spec.items.length===scene.time_steps.length-1,'TERRITORY_ONLY');
 const signature=JSON.stringify([scene.geometries,scene.areas,scene.time_steps.map(s=>({area_ids:s.area_ids,id:s.id}))]);
 let analysis=cache.get(signature);if(!analysis){analysis=analyzeTerritoryChanges(scene);if(cache.size>=4)cache.delete(cache.keys().next().value);cache.set(signature,analysis);}
 for(const [i,e]of spec.items.entries()){
  const d=analysis.changes[i],s=scene.time_steps[i+1];
  check(Object.keys(e).every(k=>['fromStateId','toStateId','startFrame','endFrame','strength','added','removed',...(spec.profile===CONTINUOUS_PROFILE?['continuous']:[])].includes(k)),'FIELDS');
  check(e.fromStateId===d.fromStateId&&e.toStateId===d.toStateId&&same(e.added,d.added)&&same(e.removed,d.removed),'SOURCE_DIFFERENCE_BINDING');
  check(e.startFrame===s.start_frame&&Number.isSafeInteger(e.endFrame)&&e.endFrame>=e.startFrame+3&&e.endFrame<=s.start_frame+s.transition_frames,'TIMING');
  if(spec.profile===CONTINUOUS_PROFILE){const c=e.continuous;check(c?.schema==='CONTINUOUS_TERRITORY_V1'&&c.semantics==='GEOMETRIC_VISUAL_INTERPOLATION_NOT_HISTORICAL_ROUTE'&&c.frames?.length===e.endFrame-e.startFrame,'CONTINUOUS_CONTRACT');check(same(c.frames[0].geometry,analysis.states[i])&&same(c.frames.at(-1).geometry,analysis.states[i+1]),'CONTINUOUS_ENDPOINTS');for(const [fi,f] of c.frames.entries()){check(f.alpha===1&&f.audit?.valid===true&&Number.isFinite(f.boundaryAlpha)&&f.boundaryAlpha>=0&&f.boundaryAlpha<=1,'CONTINUOUS_FRAME');for(const [gi,g] of [f.geometry,f.boundaryBand].entries())if(multi(g).length){try{validateDerivedGeometry(g);}catch(error){throw Error(error.message+"_TRANSITION_"+i+"_FRAME_"+fi+"_KIND_"+gi);}}}}
  check(Number.isFinite(e.strength)&&e.strength>=0&&e.strength<=1,'STRENGTH');
 }return structuredClone(spec);
}
export function territoryEffectsAt(spec,frame){
 if(!spec)return[];if(spec.profile===CONTINUOUS_PROFILE){const c=continuousTerritoryAt(spec,frame);return c.active&&c.boundaryAlpha>0&&multi(c.boundaryBand).length?[{id:'MOVING_BOUNDARY',kind:'moving_boundary',stateId:c.stateId,geometry:c.boundaryBand,alpha:c.boundaryAlpha,coverage:1}]:[];}const rows=[];
 for(const [index,e]of spec.items.entries()){
  if(!e.strength||frame<e.startFrame||frame>=e.endFrame)continue;
  const u=(frame-e.startFrame)/(e.endFrame-e.startFrame-1),smooth=u*u*u*(10+u*(-15+6*u));
  for(const [kind,alpha]of [['added',Math.sin(Math.PI*u)**2*e.strength],['removed',(1-smooth)*e.strength]]){
   if(alpha<=1e-10||!multi(e[kind]).length)continue;
   rows.push({id:'DERIVED_DELTA_'+index+'_'+kind,kind,stateId:e.toStateId,geometry:e[kind],alpha,coverage:1});
  }
 }return rows;
}
