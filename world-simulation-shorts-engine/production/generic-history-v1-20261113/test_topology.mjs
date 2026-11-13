import fs from 'node:fs';import assert from 'node:assert/strict';
import {validateAreaGeometry} from '../../web/map_infographic_v1/area_core_v3.mjs';
const ring=(a,b,c,d)=>[[a,b],[c,b],[c,d],[a,d],[a,b]],multi=(...p)=>({type:'MultiPolygon',coordinates:p}),checks=[];
function check(n,f){f();checks.push(n);}
check('isolated common point valid, coordinates unchanged',()=>{const g=multi([ring(0,0,1,1)],[ring(1,1,2,2)]);assert.deepEqual(validateAreaGeometry(g),g);});
check('shared edge still invalid',()=>assert.throws(()=>validateAreaGeometry(multi([ring(0,0,1,1)],[ring(1,0,2,1)]))));
check('overlapping parts and containment invalid',()=>{for(const r of [ring(.5,.5,1.5,1.5),ring(.2,.2,.8,.8)])assert.throws(()=>validateAreaGeometry(multi([ring(0,0,1,1)],[r])));});
check('valid island in a hole preserved',()=>{const g=multi([ring(0,0,10,10),ring(2,2,8,8)],[ring(3,3,4,4)]);assert.deepEqual(validateAreaGeometry(g),g);});
check('crossing a hole boundary rejected',()=>assert.throws(()=>validateAreaGeometry(multi([ring(0,0,10,10),ring(2,2,8,8)],[ring(1,3,4,4)]))));
check('self-intersecting ring still rejected',()=>assert.throws(()=>validateAreaGeometry({type:'Polygon',coordinates:[[[0,0],[2,2],[0,2],[2,0],[0,0]]]})));
check('all retained eight source geometries preserved exactly',()=>{const x=JSON.parse(fs.readFileSync(new URL('../mongol-empire-6s-20261113/source/CLIOPATRIA_MONGOL_1206_1259.geojson',import.meta.url)));for(const f of x.features)assert.deepEqual(validateAreaGeometry(f.geometry),f.geometry);});
console.log(JSON.stringify({status:'PASS',scope:'new isolated-point/hole multipart admission; no geometry repair',checks},null,2));
