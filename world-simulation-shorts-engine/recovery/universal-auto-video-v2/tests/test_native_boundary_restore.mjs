/** Focused geometry and mock-GL lifecycle tests. These are not GPU evidence. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {compileNativeBoundaryGeometry,createNativeBoundaryRestore,MAX_NATIVE_BOUNDARY_SEGMENTS}
 from '../native_boundary_restore.mjs';
const KEY='a'.repeat(64),OTHER='b'.repeat(64);
const segments=()=>[{a:[4,5],b:[20,17],radiusPx:2,sourceId:'ACTUAL_NATIVE_COUNTRY'}];
function mockGL({alpha=false}={}){
 const calls={copies:0,draws:0,uploads:0,deleted:[]},state={active:'ORIGINAL_UNIT',draw:'ORIGINAL_DRAW',read:'ORIGINAL_READ'},
  constants=['NO_ERROR','VERTEX_SHADER','FRAGMENT_SHADER','COMPILE_STATUS','LINK_STATUS','TEXTURE0','TEXTURE_2D',
   'PIXEL_UNPACK_BUFFER','TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER','NEAREST','TEXTURE_WRAP_S','TEXTURE_WRAP_T',
   'CLAMP_TO_EDGE','RGB8','ARRAY_BUFFER','FLOAT','STATIC_DRAW','DITHER','READ_FRAMEBUFFER','DRAW_FRAMEBUFFER','BACK',
   'BLEND','CULL_FACE','DEPTH_TEST','POLYGON_OFFSET_FILL','SAMPLE_ALPHA_TO_COVERAGE','SAMPLE_COVERAGE','SCISSOR_TEST',
   'STENCIL_TEST','RASTERIZER_DISCARD','TRIANGLES'];
 let object=0,error=0;
 const gl={drawingBufferWidth:32,drawingBufferHeight:24,calls,state,
  ...Object.fromEntries(constants.map((key,index)=>[key,index])),
  getContextAttributes:()=>({alpha}),getShaderParameter:()=>true,getProgramParameter:()=>true,
  getShaderInfoLog:()=>'',getProgramInfoLog:()=>'',getUniformLocation:(_program,key)=>key,
  getError:()=>{const result=error;error=0;return result;},failWithError:()=>{error=1282;},
  activeTexture:value=>{state.active=value;},bindFramebuffer:(target,value)=>{
   state[target===gl.READ_FRAMEBUFFER?'read':'draw']=value;
  },copyTexSubImage2D:()=>{calls.copies++;if(gl.throwOnCopy)throw Error('SIMULATED_COPY_FAILURE');},
  texStorage2D:(_target,_levels,format,width,height)=>{
   assert.equal(format,gl.RGB8,'Opaque native framebuffer must use compatible RGB8 snapshot');
   calls.allocation={format,width,height};
  },bufferData:(_target,data)=>{calls.uploads++;calls.uploadBytes=data.byteLength;},
  drawArrays:(_mode,_first,count)=>{calls.draws++;calls.vertices=count;if(gl.throwOnDraw)throw Error('SIMULATED_DRAW_FAILURE');},
  readPixels:()=>{throw Error('CPU_IMAGE_READBACK_FORBIDDEN');}
 };
 for(const name of ['createProgram','createShader','createTexture','createVertexArray','createBuffer'])gl[name]=()=>({id:++object});
 for(const name of ['deleteProgram','deleteShader','deleteTexture','deleteVertexArray','deleteBuffer'])gl[name]=value=>calls.deleted.push({name,value});
 for(const name of ['shaderSource','compileShader','attachShader','linkProgram','bindTexture','bindSampler','bindBuffer',
  'texParameteri','bindVertexArray','enableVertexAttribArray','vertexAttribPointer','vertexAttribDivisor',
  'disable','readBuffer','drawBuffers','viewport','colorMask','useProgram','uniform1i','uniform2f'])gl[name]=()=>{};
 const helpers={captureFlowNativeGlState:()=>structuredClone(state),restoreFlowNativeGlState:(_gl,saved)=>{
  for(const key of Object.keys(state))delete state[key];Object.assign(state,structuredClone(saved));
 }};
 return {gl,state,helpers};
}
async function create(options={}){
 const mock=mockGL(options),pass=await createNativeBoundaryRestore({gl:mock.gl,width:32,height:24,stateHelpers:mock.helpers});
 return {...mock,pass};
}

test('finite native support is copied unchanged with one conservative pixel and bounded oriented quads',()=>{
 const original=segments(),before=structuredClone(original),result=compileNativeBoundaryGeometry(original);
 assert.deepEqual(original,before);assert.deepEqual(result.records,[{a:[4,5],b:[20,17],radius:3}]);
 assert.equal(result.vertexCount,6);assert.equal(result.vertices.length,42);assert.equal(result.vertexBufferBytes,168);
 for(let cursor=0;cursor<result.vertices.length;cursor+=7){
  assert.deepEqual(Array.from(result.vertices.slice(cursor+2,cursor+6)),[4,5,20,17]);
  assert.equal(result.vertices[cursor+6],3);
 }
 // The rectangle extends a support radius beyond both native segment ends.
 const t=[.8,.6],a=[4,5],b=[20,17],positions=Array.from({length:6},(_,i)=>Array.from(result.vertices.slice(i*7,i*7+2)));
 assert.ok(Math.min(...positions.map(p=>(p[0]-a[0])*t[0]+(p[1]-a[1])*t[1]))<=-2.999);
 assert.ok(Math.max(...positions.map(p=>(p[0]-b[0])*t[0]+(p[1]-b[1])*t[1]))>=2.999);
});

test('zero-length native edges retain finite circular support and legacy array contract',()=>{
 const result=compileNativeBoundaryGeometry([[10,10,10,10,0]]);
 assert.equal(result.records[0].radius,1);assert.equal(result.vertexCount,6);
 const x=[],y=[];for(let i=0;i<42;i+=7){x.push(result.vertices[i]);y.push(result.vertices[i+1]);}
 assert.deepEqual([Math.min(...x),Math.max(...x),Math.min(...y),Math.max(...y)],[9,11,9,11]);
});

test('invalid support and oversized geometry are rejected rather than repaired',()=>{
 for(const input of [null,{},[{a:[NaN,0],b:[1,2],radiusPx:1}],[{a:[0,0],b:[1,2],radiusPx:-1}],
  [{a:[0,0],b:[1,2],radiusPx:65}],Array.from({length:MAX_NATIVE_BOUNDARY_SEGMENTS+1},()=>segments()[0])])
  assert.throws(()=>compileNativeBoundaryGeometry(input),/NATIVE_BOUNDARY/);
 assert.equal(compileNativeBoundaryGeometry([]).vertexCount,0);
});

test('opaque RGB8 GPU snapshot, lower-left copy and limited draw preserve native GL state',async()=>{
 const {pass,gl,state}=await create(),before=structuredClone(state);
 assert.deepEqual(gl.calls.allocation,{format:gl.RGB8,width:32,height:24});
 pass.capture({key:KEY});const result=pass.restore({key:KEY,segments:segments()});
 assert.equal(gl.calls.copies,1);assert.equal(gl.calls.draws,1);assert.equal(gl.calls.vertices,6);
 assert.equal(result.snapshotBytes,32*24*3);assert.equal(result.snapshotFormat,'RGB8');assert.equal(result.opaqueAlpha,1);
 assert.equal(result.cpuImageReadback,false);assert.equal(result.actualNvidiaVerified,false);assert.deepEqual(state,before);
 assert.equal(result.protectedCorridorMaterial,'ORIGINAL_NATIVE_TERRAIN_AND_BOUNDARY_NOT_PURE_ASTRA');pass.dispose();
});

test('same immutable view/reveal key reuses one snapshot and geometry upload, not frame history',async()=>{
 const {pass,gl}=await create();pass.capture({key:KEY});pass.restore({key:KEY,segments:segments()});
 assert.equal(pass.capture({key:KEY}).cacheHit,true);pass.restore({key:KEY,segments:segments()});
 assert.equal(gl.calls.copies,1);assert.equal(gl.calls.uploads,1);assert.equal(gl.calls.draws,2);
 assert.equal(pass.evidence.captureCacheHits,1);assert.equal(pass.evidence.frameHistoryRetained,false);
 pass.capture({key:OTHER});pass.restore({key:OTHER,segments:[{a:[1,2],b:[3,4],radiusPx:3}]});
 assert.equal(gl.calls.copies,2);assert.equal(gl.calls.uploads,2);pass.dispose();
});

test('stale keys and changed native geometry under one key fail before drawing',async()=>{
 const {pass,gl}=await create();assert.throws(()=>pass.restore({key:KEY,segments:segments()}),/KEY_MISMATCH/);
 pass.capture({key:KEY});pass.restore({key:KEY,segments:segments()});
 assert.throws(()=>pass.restore({key:OTHER,segments:segments()}),/KEY_MISMATCH/);
 assert.throws(()=>pass.restore({key:KEY,segments:[{a:[4,5],b:[21,17],radiusPx:2}]}),/GEOMETRY_CHANGED/);
 assert.equal(gl.calls.draws,1);for(const key of [undefined,'camera/pipeline','a'.repeat(63),'A'.repeat(64)])
  assert.throws(()=>pass.capture({key}),/IMMUTABLE_KEY/);pass.dispose();
});

test('failed copy invalidates old snapshot and restores state without silent fallback',async()=>{
 const {pass,gl,state}=await create(),before=structuredClone(state);pass.capture({key:KEY});
 gl.throwOnCopy=true;assert.throws(()=>pass.capture({key:OTHER}),/SIMULATED_COPY_FAILURE/);
 assert.deepEqual(state,before);assert.equal(pass.evidence.snapshotKey,null);
 assert.throws(()=>pass.restore({key:KEY,segments:segments()}),/KEY_MISMATCH/);pass.dispose();
});

test('draw failure preserves original GL state and never increments successful restores',async()=>{
 const {pass,gl,state}=await create(),before=structuredClone(state);pass.capture({key:KEY});gl.throwOnDraw=true;
 assert.throws(()=>pass.restore({key:KEY,segments:segments()}),/SIMULATED_DRAW_FAILURE/);
 assert.deepEqual(state,before);assert.equal(pass.evidence.restores,0);pass.dispose();
});

test('transparent canvases, excessive image allocation, resize and disposed use fail explicitly',async()=>{
 const transparent=mockGL({alpha:true});await assert.rejects(createNativeBoundaryRestore({gl:transparent.gl,width:32,height:24,stateHelpers:transparent.helpers}),/OPAQUE_RGB8/);
 const huge=mockGL();huge.gl.drawingBufferWidth=4096;huge.gl.drawingBufferHeight=4096;
 await assert.rejects(createNativeBoundaryRestore({gl:huge.gl,width:4096,height:4096,stateHelpers:huge.helpers}),/BOUNDED_DRAWING_BUFFER/);
 const {pass,gl}=await create();gl.drawingBufferWidth=31;assert.throws(()=>pass.capture({key:KEY}),/DRAWING_BUFFER_CHANGED/);
 pass.dispose();pass.dispose();assert.throws(()=>pass.capture({key:KEY}),/DISPOSED/);
});

test('empty actual geometry performs no restore draw or fabricated border',async()=>{
 const {pass,gl}=await create();pass.capture({key:KEY});const result=pass.restore({key:KEY,segments:[]});
 assert.equal(gl.calls.draws,0);assert.equal(result.segmentCount,0);pass.dispose();
});
