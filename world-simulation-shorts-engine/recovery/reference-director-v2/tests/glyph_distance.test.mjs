import test from 'node:test';
import assert from 'node:assert/strict';
import {glyphSquaredDistance} from '../glyph_distance.mjs';
test('single ink pixel produces exact Euclidean squared distances',()=>{
 const a=new Uint8Array(7*5);a[2*7+3]=255;const d=glyphSquaredDistance(a,7,5);
 for(let y=0;y<5;y++)for(let x=0;x<7;x++)assert.equal(d[y*7+x],(x-3)**2+(y-2)**2);
});
test('multiple disconnected ink islands match brute-force minimum, including empty rows',()=>{
 const a=new Uint8Array(19*13),points=[[1,2],[14,4],[7,11]];for(const [x,y]of points)a[y*19+x]=255;
 const d=glyphSquaredDistance(a,19,13);for(let y=0;y<13;y++)for(let x=0;x<19;x++)assert.equal(d[y*19+x],Math.min(...points.map(([u,v])=>(x-u)**2+(y-v)**2)));
});
test('fully inked atlas remains zero and antialias ink coverage counts as ink',()=>{
 assert.ok(glyphSquaredDistance(new Uint8Array(30).fill(1),6,5).every(d=>d===0));
});
test('empty, mismatched and over-budget glyph atlas inputs fail explicitly',()=>{
 assert.throws(()=>glyphSquaredDistance(new Uint8Array(4),2,2),/EMPTY_INK/);
 assert.throws(()=>glyphSquaredDistance(new Uint8Array(4),3,2),/DIMENSIONS/);
 assert.throws(()=>glyphSquaredDistance(new Uint8Array(4),2000,2000),/DIMENSIONS/);
});
