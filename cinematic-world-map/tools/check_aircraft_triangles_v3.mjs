// Check complete triangle surfaces, including triangle interiors, against Earth.
import * as THREE from 'three';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {RouteAnimator,EntityAnimator} from '../src/engine_v3.js';
const routes=new RouteAnimator(),entity=new EntityAnimator(routes),parts=[];
entity.model.traverse(m=>{if(!m.isMesh)return;const a=m.geometry.attributes.position,index=m.geometry.index,vertices=[];for(let i=0;i<a.count;i++)vertices.push(new THREE.Vector3().fromBufferAttribute(a,i));const triangles=[];for(let i=0;i<(index?index.count:a.count);i+=3)triangles.push(index?[index.getX(i),index.getX(i+1),index.getX(i+2)]:[i,i+1,i+2]);parts.push({mesh:m,vertices,triangles})});
const triangle=new THREE.Triangle(),origin=new THREE.Vector3(),closest=new THREE.Vector3();
let testedPoses=0,testedTriangles=0,min={clearanceKm:Infinity},violations=[];
const stamp=Date.now();
for(let tick=0;tick<=1200;tick++) {
  const t=tick/60;entity.update(t);
  if(!entity.model.visible)continue;
  testedPoses++;
  for(let part=0;part<parts.length;part++) {
    const item=parts[part],world=item.vertices.map(v=>v.clone().applyMatrix4(item.mesh.matrixWorld));
    for(let face=0;face<item.triangles.length;face++) {
      const [a,b,c]=item.triangles[face];triangle.set(world[a],world[b],world[c]);triangle.closestPointToPoint(origin,closest);
      const clearanceKm=(closest.length()-1)*6371;testedTriangles++;
      if(clearanceKm<min.clearanceKm)min={clearanceKm,t,part,face,point:closest.toArray()};
      if(clearanceKm<0)violations.push({t,part,face,clearanceKm});
    }
  }
}
const sourceHashes={};for(const file of ['src/aircraft_v3.js','src/engine_v3.js','src/core_v1_preserved.js','tools/check_aircraft_triangles_v3.mjs'])sourceHashes[file]=createHash('sha256').update(await readFile(file)).digest('hex');
const report={sourceHashes,scope:'All visible aircraft mesh triangle surfaces at every 1/60-second pose from 0 through 20 seconds. Exact closest point includes triangle interiors and edges. It does not prove continuous-time intervals or intersections with cloud layers.',visibilityThreshold:.005,parts:parts.length,testedPoses,testedTriangles,minimumMeasuredTriangleClearanceKm:min,earthIntersections:violations,elapsedSeconds:(Date.now()-stamp)/1000};
const dest=process.argv[2]||'outputs/v3_aircraft_triangle_validation.json';await writeFile(dest,JSON.stringify(report,null,2),{flag:'wx'});
console.log(JSON.stringify({...report,sourceHashes:undefined,earthIntersections:violations.length},null,2));if(violations.length)process.exitCode=1;
