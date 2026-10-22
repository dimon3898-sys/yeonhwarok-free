import test from 'node:test';
import assert from 'node:assert/strict';
import {sourcePolygonHasCoverage} from '../source_geometry_contract.mjs';
test('explicit GEOS empty masks are no-draw without mutation',()=>{
 for(const geometry of [null,{type:'Polygon',coordinates:[]},{type:'Polygon',coordinates:[[]]},{type:'MultiPolygon',coordinates:[]}]){
  const before=JSON.stringify(geometry);assert.equal(sourcePolygonHasCoverage(geometry),false);assert.equal(JSON.stringify(geometry),before);
 }
});
test('actual nonempty polygon and multipolygon remain native triangulator inputs',()=>{
 const ring=[[0,0],[1,0],[1,1],[0,0]];
 assert.equal(sourcePolygonHasCoverage({type:'Polygon',coordinates:[ring]}),true);
 assert.equal(sourcePolygonHasCoverage({type:'MultiPolygon',coordinates:[[ring]]}),true);
});
test('malformed nonempty rings are never silently dropped as empty',()=>{
 assert.equal(sourcePolygonHasCoverage({type:'Polygon',coordinates:[[[0,0],[1,1]]]}),true);
 assert.equal(sourcePolygonHasCoverage({type:'MultiPolygon',coordinates:[[]]}),true);
 assert.throws(()=>sourcePolygonHasCoverage({type:'LineString',coordinates:[]}),/SOURCE_POLYGON_GEOMETRY_REQUIRED/);
 assert.throws(()=>sourcePolygonHasCoverage({type:'Polygon',coordinates:null}),/SOURCE_POLYGON_GEOMETRY_REQUIRED/);
});
