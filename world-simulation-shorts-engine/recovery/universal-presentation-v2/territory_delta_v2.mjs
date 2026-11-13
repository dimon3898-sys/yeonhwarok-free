/** Derived visual comparison of supplied GeoJSON. Never edits authoritative rings.
 * Polygon overlays are display differences, not intermediate historical states. */
import clip from '../../web/vendor/polygon-clipping/0.15.7/polygon-clipping.mjs';
import {mercatorY,geographicCameraFrame} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
const check=(v,c)=>{if(!v)throw Error('TERRITORY_DELTA_'+c);};
const rad=x=>x*Math.PI/180, R=6371.0088;
export const multi=g=>g.type==='Polygon'?[g.coordinates]:g.type==='MultiPolygon'?g.coordinates:(()=>{throw Error('TERRITORY_DELTA_POLYGON_REQUIRED');})();
export const geometry=coordinates=>({type:'MultiPolygon',coordinates});
export function stateGeometry(scene,step){
 const rows=step.area_ids.map(id=>{const a=scene.areas.find(a=>a.id===id);check(a,'AREA_REQUIRED');const g=scene.geometries.find(g=>g.id===a.geometry_ref);check(g,'GEOMETRY_REQUIRED');return g.geometry;});
 check(rows.length,'STATE_REQUIRED');
 return geometry(clip.union(...rows.map(multi)));
}
export function boundsOf(g){
 const points=multi(g).flat(2);if(!points.length)return null;
 return points.reduce((b,p)=>[Math.min(b[0],p[0]),Math.min(b[1],p[1]),Math.max(b[2],p[0]),Math.max(b[3],p[1])],[Infinity,Infinity,-Infinity,-Infinity]);
}
function domain(g){
 let count=0;
 for(const p of multi(g))for(const r of p){check(r.length>=4,'RING_REQUIRED');for(let i=0;i<r.length;i++){
  const q=r[i];check(q.length===2&&q.every(Number.isFinite)&&Math.abs(q[0])<180&&Math.abs(q[1])<85,'DOMAIN');
  if(i)check(Math.abs(q[0]-r[i-1][0])<180,'ANTIMERIDIAN_UNSUPPORTED');count++;
 }}check(count<=100000,'VERTEX_CAPACITY');
}
/** Surface integral on a sphere along the supplied straight lon/lat segments.
 * Reported as a spherical estimate, not surveyed or ellipsoidal territory area. */
export function areaKm2(g){
 const ringArea=r=>{let v=0;for(let i=1;i<r.length;i++){const a=r[i-1],b=r[i],p=rad(a[1]),q=rad(b[1]);
  const mean=Math.abs(q-p)<1e-14?Math.sin(p):(Math.cos(p)-Math.cos(q))/(q-p);v+=rad(b[0]-a[0])*mean;
 }return Math.abs(v)*R*R;};
 return multi(g).reduce((sum,p)=>sum+Math.max(0,ringArea(p[0])-p.slice(1).reduce((n,r)=>n+ringArea(r),0)),0);
}
const planarRing=r=>{let a=0;for(let i=1;i<r.length;i++)a+=r[i-1][0]*r[i][1]-r[i][0]*r[i-1][1];return Math.abs(a)/2;};
const planarArea=m=>m.reduce((s,p)=>s+planarRing(p[0])-p.slice(1).reduce((s,r)=>s+planarRing(r),0),0);
export function screenFraction(g,pose){
 if(!multi(g).length)return 0;const project=geographicCameraFrame(pose).project;
 const projected=multi(g).map(p=>p.map(r=>r.map(project)));
 const cropped=clip.intersection(projected,[[[0,0],[1080,0],[1080,1920],[0,1920],[0,0]]]);
 return Math.max(0,Math.min(1,planarArea(cropped)/(1080*1920)));
}
export function centroidOf(g){
 if(!multi(g).length)return null;let sx=0,sy=0,total=0;
 // Equal-area lon/sin(lat) centroid; a framing statistic, not an event location.
 for(const p of multi(g))for(const [j,r] of p.entries()){
  const q=r.map(([x,y])=>[rad(x),Math.sin(rad(y))]);let cross=0,x=0,y=0;
  for(let i=1;i<q.length;i++){const a=q[i-1],b=q[i],c=a[0]*b[1]-b[0]*a[1];cross+=c;x+=(a[0]+b[0])*c;y+=(a[1]+b[1])*c;}
  if(Math.abs(cross)<1e-20)continue;const weight=(j?-1:1)*Math.abs(cross)/2;
  sx+=x/(3*cross)*weight;sy+=y/(3*cross)*weight;total+=weight;
 }return total>0?[sx/total*180/Math.PI,Math.asin(Math.max(-1,Math.min(1,sy/total)))*180/Math.PI]:null;
}
export function analyzeTerritoryChanges(scene){
 check(scene?.time_steps?.length>=2&&scene.time_steps.length<=8,'STATE_COUNT');
 const states=scene.time_steps.map(step=>{for(const id of step.area_ids){const a=scene.areas.find(x=>x.id===id);domain(scene.geometries.find(g=>g.id===a.geometry_ref).geometry);}return stateGeometry(scene,step);});
 const changes=states.slice(1).map((next,j)=>{
  const previous=states[j],added=geometry(clip.difference(multi(next),multi(previous))),removed=geometry(clip.difference(multi(previous),multi(next)));
  const changed=geometry(clip.union(multi(added),multi(removed))),union=geometry(clip.union(multi(previous),multi(next)));
  const beforeKm2=areaKm2(previous),afterKm2=areaKm2(next),addedKm2=areaKm2(added),removedKm2=areaKm2(removed),changedKm2=addedKm2+removedKm2;
  check(Math.abs(afterKm2-beforeKm2-addedKm2+removedKm2)<=Math.max(1e-4,areaKm2(union)*1e-8),'AREA_CONSERVATION');
  return{fromStateId:scene.time_steps[j].id,toStateId:scene.time_steps[j+1].id,added,removed,changed,beforeKm2,afterKm2,addedKm2,removedKm2,netKm2:afterKm2-beforeKm2,changedKm2,ratio:changedKm2/Math.max(1e-12,areaKm2(union)),center:centroidOf(changed),bounds:boundsOf(changed),parts:multi(changed).length};
 });
 return{schema:'TERRITORY_DELTA_V2',areaMethod:'SPHERICAL_SURFACE_INTEGRAL_STRAIGHT_GEOJSON_EDGES_R6371.0088_KM',historicalImportanceInferred:false,sourceGeometryChanged:false,states,changes};
}
