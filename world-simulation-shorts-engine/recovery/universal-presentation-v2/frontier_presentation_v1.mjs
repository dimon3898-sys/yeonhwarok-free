/** Presentation masks derived from the already-qualified current geometry. */
import clip from '../../web/vendor/polygon-clipping/0.15.7/polygon-clipping.mjs';
import {continuousTerritoryAt} from './continuous_territory_runtime.mjs';
import {multi,geometry,areaKm2} from './territory_delta_v2.mjs';
export const FRONTIER_VISUAL_PROFILE='FRONTIER_LIGHT_V1';
const cache=new WeakMap();
export function frontierPresentationAt(spec,frame){
 const state=continuousTerritoryAt(spec,frame),item=spec.items.filter(e=>frame>=e.startFrame).at(-1)??spec.items[0];
 if(frame<item.startFrame)return[];
 let rows=cache.get(item);if(!rows){rows=new Map();cache.set(item,rows);}
 let masks=rows.get(state.index);
 if(!masks){
  // Only the portion that actually exists NOW receives the new/retreat color.
  masks=['added','removed'].map(kind=>({kind,geometry:geometry(clip.intersection(multi(state.geometry),multi(item[kind])))}));
  rows.set(state.index,masks);
 }
 const settle=Math.max(0,Math.min(1,(frame-item.endFrame+1)/18)),decay=1-.45*settle*settle*(3-2*settle);
 const result=masks.filter(x=>multi(x.geometry).length).map(x=>({id:'VISIBLE_'+x.kind.toUpperCase(),kind:'visible_'+x.kind,stateId:state.stateId,geometry:x.geometry,alpha:decay,coverage:1}));
 if(state.active&&state.boundaryAlpha>0&&multi(state.boundaryBand).length){
  // Relative changed area is a visual-attention policy, never historical importance.
  // Preserve every component; emphasize the dominant one and gently dim the rest.
  const parts=multi(state.boundaryBand).map((p,i)=>({i,geometry:geometry([p]),area:areaKm2(geometry([p]))})).sort((a,b)=>b.area-a.area||a.i-b.i);
  const largest=parts[0].area;
  for(const priority of ['PRIMARY','CONTEXT']){const selected=parts.filter(part=>(part.area>=largest*.45?'PRIMARY':'CONTEXT')===priority);if(selected.length)result.push({id:'MOVING_BOUNDARY_'+priority,kind:'moving_boundary',stateId:state.stateId,geometry:geometry(selected.flatMap(x=>multi(x.geometry))),alpha:state.boundaryAlpha*(priority==='PRIMARY'?1:.42),coverage:1,priority});}
 }
 return result;
}
