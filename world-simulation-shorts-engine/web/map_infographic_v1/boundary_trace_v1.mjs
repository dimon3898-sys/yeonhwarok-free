/** Opt-in native boundary reveal; reuses the existing directed line owner. */
import {compileEventIntent} from './event_contract_v1.mjs';
import {compileGeographicLinePrimitive,evaluateGeographicLineReveal} from './event_line_v1.mjs';
const check=(v,c)=>{if(!v)throw Error(c);};
export function validateBoundaryTrace(spec,{totalFrames,holdFrames=0}={}){
 check(spec&&typeof spec==='object'&&!Array.isArray(spec)&&Object.keys(spec).every(k=>['preset','countryIds','startFrame','endFrame','startVertex','direction','pathTiming'].includes(k)),'BOUNDARY_TRACE_FIELDS');
 check(spec.preset==='BOUNDARY_TRACE'&&spec.startVertex==='NORTHMOST'&&['FORWARD','REVERSE'].includes(spec.direction),'BOUNDARY_TRACE_PRESET');
 check(Array.isArray(spec.countryIds)&&spec.countryIds.length>0&&spec.countryIds.length<=256&&new Set(spec.countryIds).size===spec.countryIds.length&&spec.countryIds.every(x=>typeof x==='string'&&/^COUNTRY_[A-Z0-9_]+$/.test(x)),'BOUNDARY_TRACE_COUNTRIES');
 check(Number.isSafeInteger(spec.startFrame)&&Number.isSafeInteger(spec.endFrame)&&spec.startFrame>=0&&spec.endFrame>spec.startFrame&&spec.endFrame<totalFrames-holdFrames,'BOUNDARY_TRACE_TIMING');
 check(spec.pathTiming===undefined||['PARALLEL','LENGTH_WEIGHTED'].includes(spec.pathTiming),'BOUNDARY_TRACE_PATH_TIMING');
 return structuredClone(spec);
}
export function boundaryTraceFraction(spec,frame){
 check(Number.isSafeInteger(frame)&&frame>=0,'BOUNDARY_TRACE_FRAME');
 return Math.min(1,Math.max(0,(frame-spec.startFrame)/(spec.endFrame-spec.startFrame)));
}
export function compileBoundaryTrace(record,project,spec){
 const parts=(record.geometry_type??record.type)==='Polygon'?[record.coordinates]:record.coordinates;
 check(Array.isArray(parts)&&typeof project==='function','BOUNDARY_TRACE_GEOMETRY');
 return parts.flatMap(polygon=>polygon.map(ring=>{
  // Reorder only the boundary traversal; never change the source polygon.
  const pts=ring.slice(0,-1).map(p=>[...p]);check(pts.length>=3,'BOUNDARY_TRACE_RING');
  let first=0;for(let i=1;i<pts.length;i++)if(pts[i][1]>pts[first][1]||(pts[i][1]===pts[first][1]&&pts[i][0]<pts[first][0]))first=i;
  let ordered=[...pts.slice(first),...pts.slice(0,first)];if(spec.direction==='REVERSE')ordered=[ordered[0],...ordered.slice(1).reverse()];ordered.push([...ordered[0]]);
  const intent=compileEventIntent({data_mode:'PRODUCTION',line:{geometry:{type:'LineString',coordinates:ordered},direction:'FORWARD',style_role:'NATIVE_COUNTRY_BOUNDARY',source:{source_type:'REGISTERED_NATIVE_GEOMETRY',source_reference:record.source_id??record.id,verification_status:'VERIFIED'}}});
  return compileGeographicLinePrimitive(intent,{project});
 }));
}
export function boundaryTraceProgress(primitives,fraction,spec={}){
 check(Number.isFinite(fraction)&&fraction>=0&&fraction<=1,'BOUNDARY_TRACE_PROGRESS');
 const ordered=primitives.map((p,index)=>({p,index}));
 if(spec.pathTiming==='LENGTH_WEIGHTED')ordered.sort((a,b)=>b.p.totalLengthPixels-a.p.totalLengthPixels||a.index-b.index);
 const totalLength=ordered.reduce((s,{p})=>s+p.totalLengthPixels,0);let consumed=0;
 const paths=ordered.map(({p,index})=>{const progress=spec.pathTiming==='LENGTH_WEIGHTED'?Math.max(0,Math.min(1,(fraction*totalLength-consumed)/p.totalLengthPixels)):fraction;consumed+=p.totalLengthPixels;return{primitive:p,index,progress:fraction===1?1:progress};});
 return{paths,totalLength,visibleLength:paths.reduce((s,r)=>s+r.progress*r.primitive.totalLengthPixels,0),totalPaths:paths.length,completedPaths:paths.filter(r=>r.progress===1).length};
}
export function evaluateBoundaryTrace(primitives,fraction,spec={}){
 return boundaryTraceProgress(primitives,fraction,spec).paths.map(({primitive,progress})=>{const ring=evaluateGeographicLineReveal(primitive,progress).path.map(q=>[...q]);ring.closed=progress===1;return ring;}).filter(r=>r.length>=2);
}
