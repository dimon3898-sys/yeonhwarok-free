/** Random access to validated, source-bound display geometry. No opacity morph. */
export const CONTINUOUS_PROFILE='HISTORICAL_CONTINUOUS_V1';
/** Derived rings contain sub-pixel edges. The legacy source validator's fixed
 * cross-product epsilon marks distinct nearby edges as intersecting. Keep that
 * source contract unchanged; validate derived rings with scale-relative proper
 * intersections, while GEOS independently checks full OGC topology at compile
 * and evidence-gate time. No input rings are repaired or weakened. */
export function validateDerivedGeometry(g){
 if(!g||!['Polygon','MultiPolygon'].includes(g.type))throw Error('CONTINUOUS_GEOMETRY_TYPE');
 const parts=g.type==='Polygon'?[g.coordinates]:g.coordinates;
 let count=0;
 const orient=(a,b,c)=>{const x=(b[0]-a[0])*(c[1]-a[1]),y=(b[1]-a[1])*(c[0]-a[0]),v=x-y,tol=8*Number.EPSILON*(Math.abs(x)+Math.abs(y));return Math.abs(v)<=tol?0:Math.sign(v);};
 for(const p of parts){if(!p.length)throw Error('CONTINUOUS_OUTER_REQUIRED');for(const r of p){
  count+=r.length;if(r.length<4||JSON.stringify(r[0])!==JSON.stringify(r.at(-1)))throw Error('CONTINUOUS_CLOSED_RING');
  for(let i=0;i<r.length-1;i++){
   const a=r[i],b=r[i+1];if(a.length!==2||!a.every(Number.isFinite)||Math.abs(a[0])>=180||Math.abs(a[1])>=85||a[0]===b[0]&&a[1]===b[1])throw Error('CONTINUOUS_VERTEX');
   for(let j=i+2;j<r.length-1;j++){if(i===0&&j===r.length-2)continue;const c=r[j],d=r[j+1];if(orient(a,b,c)*orient(a,b,d)<0&&orient(c,d,a)*orient(c,d,b)<0)throw Error('CONTINUOUS_SELF_INTERSECTION');}
  }
 }}
 if(count>16384)throw Error('CONTINUOUS_VERTEX_CAPACITY');return true;
}
export function continuousTerritoryAt(spec,frame){
 if(spec?.profile!==CONTINUOUS_PROFILE)return null;
 const item=spec.items.filter(e=>frame>=e.startFrame).at(-1)??spec.items[0];
 const index=Math.max(0,Math.min(item.continuous.frames.length-1,frame-item.startFrame));
 return{...item.continuous.frames[index],fromStateId:item.fromStateId,toStateId:item.toStateId,
  stateId:index<Math.ceil((item.continuous.frames.length-1)/2)?item.fromStateId:item.toStateId,
  active:frame>=item.startFrame&&frame<item.endFrame,index,
  semantics:item.continuous.semantics};
}
export function applyContinuousTerritory(controls,spec,frame){
 const c=continuousTerritoryAt(spec,frame);if(!c)return controls;
 return{...controls,stateId:c.stateId,areas:c.geometry.coordinates.length?[{id:'CONTINUOUS_SOURCE_TERRITORY',state_id:c.stateId,geometry:c.geometry,alpha:1,coverage:1}]:[],
  continuousEvidence:{index:c.index,active:c.active,semantics:c.semantics,...c.audit}};
}
