import test from 'node:test';
import assert from 'node:assert/strict';
import {validateAreaGeometry} from '../../../web/map_infographic_v1/area_core_v3.mjs';

// Synthetic capacity fixture only; this is not a historical territory.
const ring = Array.from({length:4134},(_,i)=>[20+10*Math.cos(i/4134*Math.PI*2),20+10*Math.sin(i/4134*Math.PI*2)]);
ring.push([...ring[0]]);
const geometry={type:'Polygon',coordinates:[ring]};

test('source-native capacity retains a supplied ring beyond the legacy limit without changing coordinates',()=>{
 const result=validateAreaGeometry(geometry,{maxCoordinates:8192});
 assert.deepEqual(result,geometry);
 assert.equal(result.coordinates[0].length,4135);
 assert(Object.isFrozen(result));
});
test('all legacy callers retain the original 4096 limit',()=>{
 assert.throws(()=>validateAreaGeometry(geometry),/AREA_GEOMETRY_CAPACITY_EXCEEDED/);
});
test('new capacity remains bounded and does not permit invalid topology',()=>{
 assert.throws(()=>validateAreaGeometry(geometry,{maxCoordinates:8193}),/AREA_GEOMETRY_CAPACITY_PROFILE_INVALID/);
 assert.throws(()=>validateAreaGeometry({type:'Polygon',coordinates:[[[0,0],[2,2],[0,2],[2,0],[0,0]]]},{maxCoordinates:8192}),/AREA_RING_SELF_INTERSECTION/);
});
