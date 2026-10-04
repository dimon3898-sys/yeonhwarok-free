// Input equivalence only. Never invokes a WebGL draw or creates a video.
// Run AFTER the production render, not concurrently with it:
// node tools/compare_render_state_v3.mjs --previous=/path/to/frozen-copy \
//   --manifest=outputs/segment_source_manifest.json --start=0 --seconds=5 \
//   --output=outputs/v3_early_input_equivalence.json
import {chromium} from 'playwright';
import {readFile, writeFile, mkdir, access} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const root=path.resolve(import.meta.dirname,'..');
const changing=['src/engine_v3.js','src/renderer_v3.js'];
const required=['src/aircraft_v3.js','src/core_v1_preserved.js','index_v3.html',
  'tools/render_v3.mjs','assets/v3/fonts/OpenSans-Light.ttf',
  'assets/v3/earth/earth-day-8k.jpg','assets/v3/earth/earth-night-8k.jpg',
  'assets/v3/earth/earth-clouds-8k.jpg','assets/gis/earth-topology.png',...changing];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const args={};
for(let i=2;i<process.argv.length;i++) {
  const a=process.argv[i];if(!a.startsWith('--'))throw Error('Expected --key=value');
  const eq=a.indexOf('='),key=a.slice(2,eq<0?undefined:eq);
  const value=eq<0?process.argv[++i]:a.slice(eq+1);
  if(!['previous','manifest','start','seconds','output'].includes(key)||!value||value.startsWith('--'))
    throw Error('Invalid argument '+a);
  args[key]=value;
}
for(const k of ['previous','manifest','output'])if(!args[k])throw Error('Missing --'+k);
const previous=path.resolve(root,args.previous),manifestPath=path.resolve(root,args.manifest);
const output=path.resolve(root,args.output),outputs=path.join(root,'outputs');
if(!output.startsWith(outputs+path.sep))throw Error('Output must be a new file in outputs/');
let outputExists=false;try{await access(output);outputExists=true}catch(e){if(e.code!=='ENOENT')throw e}
if(outputExists)throw Error('Refusing existing output '+output);
const report={scope:'Input state equivalence, not newly rendered RGB hash',
  exactInputsEqual:false,complete:false,manifest:path.relative(root,manifestPath),
  previousDirectory:previous,mismatches:[],limitations:[
    'WebGL render is replaced by matrix updates; shaders are not compiled/drawn and no RGB comparison is performed.',
    'Canvas image/text draw commands are recorded without drawing; real loaded-font measureText is retained.',
    'Open Sans availability is stabilized explicitly in both pages; historical font-loading timing is not reconstructed.',
    'Same current browser/Three.js runtime is used for both pages; this does not reconstruct a historical browser/driver.',
    'All geometry bytes are hashed once and checked against their copied bytes at every pose; mutation fails closed.',
    'Only the sampled interval and its recorded shutter inputs are covered; later shots and continuous unsampled time are not certified.',
  ]};
let browser;

// Executed in each page, independently, after all source/assets/fonts load.
async function installProbe() {
  const app=window.app;
  if(!app?.gl||!app.scene||!app.postScene||!app.target)throw Error('Unsupported app interface');
  const THREE=await import('/node_modules/three/build/three.module.js');
  if(!app.scene.background?.isColor||!app.postMat.uniforms.uSize.value?.isVector2)
    throw Error('Expected current Color background/Vector2 target interface');
  const digest=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',
    typeof text==='string'?new TextEncoder().encode(text):text))).map(x=>x.toString(16).padStart(2,'0')).join('');
  const numberBuffer=new ArrayBuffer(8),numberView=new DataView(numberBuffer);
  function exactNumber(n) {
    // Three uses Infinity for an unrestricted BufferGeometry drawRange.count.
    // Encode that sentinel exactly; numerical pose validity is checked separately.
    if(Number.isNaN(n))throw Error('NaN input state number');
    numberView.setFloat64(0,n,true);
    return numberView.getUint32(0,false).toString(16).padStart(8,'0')
      +numberView.getUint32(4,false).toString(16).padStart(8,'0');
  }
  function canonical(v) {
    if(typeof v==='number')return ['float64-le',exactNumber(v)];
    if(v===undefined)return ['undefined'];
    if(v===null||typeof v==='string'||typeof v==='boolean')return v;
    if(Array.isArray(v))return v.map(canonical);
    if(typeof v!=='object')throw Error('Unsupported canonical type '+typeof v);
    return Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])]));
  }
  const encode=v=>JSON.stringify(canonical(v));
  const geometryMemo=new WeakMap(),materialShaderMemo=new WeakMap();
  const staticGeometry=[],staticShaders=[],bufferChecks=[];
  const objectPaths=new WeakMap(),targetRoles=new WeakMap(),textureRoles=new WeakMap();
  targetRoles.set(app.target,'primary-target');
  for(const [i,t] of (app.target.textures||[app.target.texture]).entries())
    textureRoles.set(t,'primary-color-'+i);
  if(app.target.depthTexture)textureRoles.set(app.target.depthTexture,'primary-depth');
  function register(object,p) {
    if(!object)return;objectPaths.set(object,p);
    object.children?.forEach((child,i)=>register(child,p+'/children/'+i));
  }
  register(app.scene,'scene');register(app.postScene,'postScene');
  register(app.camera,'camera');register(app.postCam,'postCamera');
  const className=v=>v?.constructor?.name||'Object';
  const isPlain=v=>v&&Object.getPrototypeOf(v)===Object.prototype;
  function bytesOf(a) {return new Uint8Array(a.buffer,a.byteOffset,a.byteLength)}
  function hexBytes(a){return Array.from(bytesOf(a)).map(x=>x.toString(16).padStart(2,'0')).join('')}
  function attributeProperties(attr) {
    if(!attr)return null;
    const array=attr.isInterleavedBufferAttribute?attr.data.array:attr.array;
    return {type:className(attr),arrayType:className(array),itemSize:attr.itemSize,count:attr.count,
      normalized:attr.normalized,gpuType:attr.gpuType,usage:attr.usage,
      dataUsage:attr.data?.usage,stride:attr.data?.stride,offset:attr.offset,
      divisor:attr.meshPerAttribute,byteLength:array.byteLength};
  }
  function imageState(image) {
    if(image==null)return image;
    if(Array.isArray(image))return image.map(imageState);
    if(image instanceof HTMLImageElement)return {kind:'HTMLImageElement',src:image.src,
      currentSrc:image.currentSrc,width:image.width,height:image.height,
      naturalWidth:image.naturalWidth,naturalHeight:image.naturalHeight,complete:image.complete};
    if(image instanceof HTMLCanvasElement||image instanceof HTMLVideoElement)
      throw Error('Pixel-dependent canvas/video texture is unsupported');
    if(typeof ImageBitmap!=='undefined'&&image instanceof ImageBitmap)
      throw Error('ImageBitmap without an authorized byte/source identity is unsupported');
    if(isPlain(image))return value(image);
    throw Error('Unsupported texture image '+className(image));
  }
  function textureState(t) {
    if(t.isRenderTargetTexture&&!textureRoles.has(t))throw Error('Unregistered render-target texture');
    const keys=['mapping','channel','wrapS','wrapT','wrapR','magFilter','minFilter','anisotropy',
      'format','type','internalFormat','colorSpace','flipY','generateMipmaps','premultiplyAlpha',
      'unpackAlignment','compareFunction','matrixAutoUpdate','rotation','version',
      'isCubeTexture','isDepthTexture','isDataTexture','isRenderTargetTexture'];
    return {kind:className(t),role:textureRoles.get(t)||'source-image',
      properties:Object.fromEntries(keys.map(k=>[k,value(t[k])])),
      offset:value(t.offset),repeat:value(t.repeat),center:value(t.center),matrix:value(t.matrix),
      image:imageState(t.image),mipmaps:value(t.mipmaps),sourceVersion:t.source?.version};
  }
  function value(v,seen=new Set()) {
    if(v===undefined||v===null||['number','string','boolean'].includes(typeof v))return v;
    if(typeof v==='function')return {functionBody:Function.prototype.toString.call(v)};
    if(ArrayBuffer.isView(v))return {arrayType:className(v),byteLength:v.byteLength,bytes:hexBytes(v)};
    if(v instanceof ArrayBuffer)return {arrayType:'ArrayBuffer',bytes:hexBytes(new Uint8Array(v))};
    if(v.isTexture)return textureState(v);
    if(v.isColor)return {kind:'Color',rgb:[v.r,v.g,v.b]};
    if(v.isVector2||v.isVector3||v.isVector4||v.isQuaternion||v.isEuler)
      return {kind:className(v),values:v.toArray()};
    if(v.isMatrix3||v.isMatrix4)return {kind:className(v),elements:Array.from(v.elements)};
    if(v.isPlane)return {kind:'Plane',normal:value(v.normal),constant:v.constant};
    if(v.isBox3)return {kind:'Box3',min:value(v.min),max:value(v.max)};
    if(v.isSphere)return {kind:'Sphere',center:value(v.center),radius:v.radius};
    if(v.isObject3D) {
      const ref=objectPaths.get(v);if(!ref)throw Error('Unregistered Object3D reference');
      return {objectReference:ref};
    }
    if(seen.has(v))throw Error('Unsupported cyclic input object');
    seen.add(v);
    let result;
    if(Array.isArray(v))result=v.map(x=>value(x,seen));
    else if(isPlain(v))result=Object.fromEntries(Object.keys(v).filter(k=>!['id','uuid'].includes(k))
      .sort().map(k=>[k,value(v[k],seen)]));
    else throw Error('Unsupported input object '+className(v));
    seen.delete(v);return result;
  }
  async function attributeState(attr,label) {
    if(!attr)return null;
    const array=attr.isInterleavedBufferAttribute?attr.data.array:attr.array;
    if(!ArrayBuffer.isView(array))throw Error('Unsupported attribute store '+label);
    const copy=bytesOf(array).slice();
    bufferChecks.push({label,attr,array,copy,version:attr.version,
      data:attr.data,dataVersion:attr.data?.version});
    return {...attributeProperties(attr),sha256:await digest(copy)};
  }
  async function prepareGeometry(g,label) {
    if(geometryMemo.has(g))return;
    const attrs={};
    for(const k of Object.keys(g.attributes).sort())attrs[k]=await attributeState(g.attributes[k],label+'/'+k);
    const morph={};
    for(const k of Object.keys(g.morphAttributes||{}).sort()) {
      morph[k]=[];for(let i=0;i<g.morphAttributes[k].length;i++)
        morph[k].push(await attributeState(g.morphAttributes[k][i],label+'/morph/'+k+'/'+i));
    }
    const description={type:g.type,attributes:attrs,index:await attributeState(g.index,label+'/index'),
      morphAttributes:morph,morphTargetsRelative:g.morphTargetsRelative};
    const hash=await digest(encode(description));
    geometryMemo.set(g,{hash,attributeKeys:Object.keys(g.attributes).sort(),
      attrRefs:Object.fromEntries(Object.entries(g.attributes)),indexRef:g.index,
      morphKeys:Object.keys(g.morphAttributes||{}).sort(),
      morphRefs:Object.fromEntries(Object.entries(g.morphAttributes||{}).map(([k,v])=>[k,v.slice()]))});
    staticGeometry.push({firstTreePath:label,sha256:hash,description});
  }
  async function prepareMaterial(m,label) {
    if(materialShaderMemo.has(m))return;
    if(m.onBeforeCompile!==THREE.Material.prototype.onBeforeCompile
      ||m.customProgramCacheKey!==THREE.Material.prototype.customProgramCacheKey)
      throw Error('Custom compile/cache hook needs an actual shader proof: '+label);
    const description={type:m.type,vertexShader:m.vertexShader,fragmentShader:m.fragmentShader,
      glslVersion:m.glslVersion,onBeforeCompile:String(m.onBeforeCompile),
      customProgramCacheKey:String(m.customProgramCacheKey)};
    const hash=await digest(encode(description));materialShaderMemo.set(m,{hash,description});
    staticShaders.push({firstTreePath:label,sha256:hash,description});
  }
  for(const graph of [app.scene,app.postScene]) {
    const nodes=[];graph.traverse(o=>nodes.push(o));
    for(const o of nodes) {
      const label=objectPaths.get(o);
      if(o.onBeforeRender!==THREE.Object3D.prototype.onBeforeRender
        ||o.onAfterRender!==THREE.Object3D.prototype.onAfterRender)
        throw Error('Custom render hook is not executed by this probe: '+label);
      if(o.geometry)await prepareGeometry(o.geometry,label+'/geometry');
      for(const [i,m] of (o.material?(Array.isArray(o.material)?o.material:[o.material]):[]).entries())
        await prepareMaterial(m,label+'/material/'+i);
    }
  }
  function checkGeometryBytes() {
    for(const c of bufferChecks) {
      const current=c.attr.isInterleavedBufferAttribute?c.attr.data.array:c.attr.array;
      if(current!==c.array||c.attr.version!==c.version||c.attr.data!==c.data
        ||c.attr.data?.version!==c.dataVersion)throw Error('Geometry store/version changed '+c.label);
      const bytes=bytesOf(current);if(bytes.length!==c.copy.length)throw Error('Geometry length changed '+c.label);
      // Hash once, then exact bytes every pose, including silently modified arrays.
      let i=0;
      if(bytes.byteOffset%4===0) {
        const words=new Uint32Array(bytes.buffer,bytes.byteOffset,Math.floor(bytes.length/4));
        const baseline=new Uint32Array(c.copy.buffer,0,words.length);
        for(let j=0;j<words.length;j++)if(words[j]!==baseline[j])throw Error('Geometry bytes changed '+c.label);
        i=words.length*4;
      }
      for(;i<bytes.length;i++)if(bytes[i]!==c.copy[i])throw Error('Geometry bytes changed '+c.label);
    }
  }
  function geometryState(g) {
    const memo=geometryMemo.get(g);if(!memo)throw Error('New unregistered geometry');
    const keys=Object.keys(g.attributes).sort();
    if(JSON.stringify(keys)!==JSON.stringify(memo.attributeKeys)||g.index!==memo.indexRef
      ||keys.some(k=>g.attributes[k]!==memo.attrRefs[k]))throw Error('Geometry attributes replaced');
    const morphKeys=Object.keys(g.morphAttributes||{}).sort();
    if(JSON.stringify(morphKeys)!==JSON.stringify(memo.morphKeys)
      ||morphKeys.some(k=>g.morphAttributes[k].length!==memo.morphRefs[k].length
        ||g.morphAttributes[k].some((v,i)=>v!==memo.morphRefs[k][i])))throw Error('Morph attributes replaced');
    return {dataSHA256:memo.hash,
      attributes:Object.fromEntries(keys.map(k=>[k,attributeProperties(g.attributes[k])])),
      index:attributeProperties(g.index),
      morphAttributes:Object.fromEntries(morphKeys.map(k=>[k,g.morphAttributes[k].map(attributeProperties)])),
      drawRange:value(g.drawRange),groups:value(g.groups),
      morphTargetsRelative:g.morphTargetsRelative,instanceCount:g.instanceCount,
      boundingBox:value(g.boundingBox),boundingSphere:value(g.boundingSphere)};
  }
  function materialState(m) {
    const memo=materialShaderMemo.get(m);if(!memo)throw Error('New unregistered material');
    if(m.onBeforeCompile!==THREE.Material.prototype.onBeforeCompile
      ||m.customProgramCacheKey!==THREE.Material.prototype.customProgramCacheKey)
      throw Error('Custom compile/cache hook appeared during sampled interval');
    const shader={type:m.type,vertexShader:m.vertexShader,fragmentShader:m.fragmentShader,
      glslVersion:m.glslVersion,onBeforeCompile:String(m.onBeforeCompile),customProgramCacheKey:String(m.customProgramCacheKey)};
    if(encode(shader)!==encode(memo.description))throw Error('Shader/callback mutated during sampled interval');
    const props={};
    for(const k of Object.keys(m).sort()) {
      if(['id','uuid','name','_listeners','vertexShader','fragmentShader','onBeforeCompile','customProgramCacheKey'].includes(k))continue;
      props[k]=value(m[k]);
    }
    // Include relevant prototype getters, including alphaTest and PBR options.
    for(const k of ['alphaTest','opacity','transparent','blending','blendSrc','blendDst','blendEquation',
      'blendSrcAlpha','blendDstAlpha','blendEquationAlpha','depthFunc','depthTest','depthWrite','colorWrite',
      'side','shadowSide','premultipliedAlpha','polygonOffset','polygonOffsetFactor','polygonOffsetUnits',
      'toneMapped','dithering','vertexColors','fog','metalness','roughness','transmission','thickness',
      'ior','reflectivity','clearcoat','clearcoatRoughness','sheen','iridescence','envMapIntensity'])
      props[k]=value(m[k]);
    return {shaderSHA256:memo.hash,properties:props};
  }
  function transformState(o) {
    return {type:o.type,position:value(o.position),rotation:value(o.rotation),quaternion:value(o.quaternion),
      scale:value(o.scale),matrix:value(o.matrix),matrixWorld:value(o.matrixWorld),up:value(o.up),
      visible:o.visible,layers:o.layers?.mask,renderOrder:o.renderOrder,frustumCulled:o.frustumCulled,
      castShadow:o.castShadow,receiveShadow:o.receiveShadow,matrixAutoUpdate:o.matrixAutoUpdate,
      matrixWorldAutoUpdate:o.matrixWorldAutoUpdate,matrixWorldNeedsUpdate:o.matrixWorldNeedsUpdate,
      userData:value(o.userData),onBeforeRender:String(o.onBeforeRender),onAfterRender:String(o.onAfterRender)};
  }
  function cameraState(c) {
    return {...transformState(c),matrixWorldInverse:value(c.matrixWorldInverse),projectionMatrix:value(c.projectionMatrix),
      projectionMatrixInverse:value(c.projectionMatrixInverse),fov:c.fov,aspect:c.aspect,near:c.near,far:c.far,
      zoom:c.zoom,focus:c.focus,filmGauge:c.filmGauge,filmOffset:c.filmOffset,view:value(c.view),
      left:c.left,right:c.right,top:c.top,bottom:c.bottom};
  }
  function lightState(l) {
    const s=l.shadow;
    return {color:value(l.color),groundColor:value(l.groundColor),intensity:l.intensity,
      distance:l.distance,decay:l.decay,angle:l.angle,penumbra:l.penumbra,width:l.width,height:l.height,
      target:l.target?transformState(l.target):null,
      shadow:s?{camera:cameraState(s.camera),bias:s.bias,normalBias:s.normalBias,radius:s.radius,
        blurSamples:s.blurSamples,mapSize:value(s.mapSize),matrix:value(s.matrix),autoUpdate:s.autoUpdate,
        needsUpdate:s.needsUpdate,map:s.map?targetState(s.map):null,mapPass:s.mapPass?targetState(s.mapPass):null}:null};
  }
  function graphState(o) {
    if(o.onBeforeRender!==THREE.Object3D.prototype.onBeforeRender
      ||o.onAfterRender!==THREE.Object3D.prototype.onAfterRender)
      throw Error('Custom render hook appeared during sampled interval');
    const state=transformState(o);
    if(o.isScene)Object.assign(state,{background:value(o.background),environment:value(o.environment),
      fog:value(o.fog),backgroundBlurriness:o.backgroundBlurriness,backgroundIntensity:o.backgroundIntensity,
      backgroundRotation:value(o.backgroundRotation),environmentIntensity:o.environmentIntensity,
      environmentRotation:value(o.environmentRotation),overrideMaterial:o.overrideMaterial?materialState(o.overrideMaterial):null});
    if(o.geometry)state.geometry=geometryState(o.geometry);
    if(o.material)state.materials=(Array.isArray(o.material)?o.material:[o.material]).map(materialState);
    if(o.isLight)state.light=lightState(o);
    for(const k of ['morphTargetInfluences','morphTargetDictionary','instanceMatrix','instanceColor'])
      if(o[k]!==undefined) {
        if(k==='instanceMatrix'||k==='instanceColor')throw Error('Instanced object not covered by this probe');
        state[k]=value(o[k]);
      }
    if(o.isSkinnedMesh)throw Error('Skinned geometry not covered by this probe');
    if(o.isBatchedMesh)throw Error('Batched geometry not covered by this probe');
    state.children=o.children.map(graphState);return state;
  }
  function targetState(t) {
    const role=targetRoles.get(t);if(!role)throw Error('Unregistered render target');
    return {role,width:t.width,height:t.height,depth:t.depth,samples:t.samples,depthBuffer:t.depthBuffer,
      stencilBuffer:t.stencilBuffer,resolveDepthBuffer:t.resolveDepthBuffer,resolveStencilBuffer:t.resolveStencilBuffer,
      viewport:value(t.viewport),scissor:value(t.scissor),scissorTest:t.scissorTest,
      textures:(t.textures||[t.texture]).map(textureState),depthTexture:t.depthTexture?textureState(t.depthTexture):null};
  }
  function rendererState() {
    const gl=app.gl,ctx=gl.getContext(),size=gl.getSize(app.postMat.uniforms.uSize.value.clone()),
      draw=gl.getDrawingBufferSize(app.postMat.uniforms.uSize.value.clone());
    const target=gl.getRenderTarget();
    if(target&&!targetRoles.has(target))throw Error('Unregistered current render target');
    const capabilityKeys=['isWebGL2','precision','logarithmicDepthBuffer','reverseDepthBuffer',
      'maxTextures','maxVertexTextures','maxTextureSize','maxCubemapSize','maxAttributes',
      'maxVertexUniforms','maxVaryings','maxFragmentUniforms','maxSamples'];
    return {size:value(size),drawingBufferSize:value(draw),pixelRatio:gl.getPixelRatio(),
      outputColorSpace:gl.outputColorSpace,toneMapping:gl.toneMapping,toneMappingExposure:gl.toneMappingExposure,
      autoClear:gl.autoClear,autoClearColor:gl.autoClearColor,autoClearDepth:gl.autoClearDepth,
      autoClearStencil:gl.autoClearStencil,sortObjects:gl.sortObjects,localClippingEnabled:gl.localClippingEnabled,
      clippingPlanes:value(gl.clippingPlanes),shadowMap:{enabled:gl.shadowMap.enabled,type:gl.shadowMap.type,
        autoUpdate:gl.shadowMap.autoUpdate,needsUpdate:gl.shadowMap.needsUpdate},
      contextAttributes:value(ctx.getContextAttributes()),
      capabilities:Object.fromEntries(capabilityKeys.map(k=>[k,value(gl.capabilities[k])])),
      clearColor:value(gl.getClearColor(app.scene.background.clone())),clearAlpha:gl.getClearAlpha(),
      currentTarget:target?targetRoles.get(target):'default-framebuffer',target:targetState(app.target),
      canvas:[gl.domElement.width,gl.domElement.height]};
  }
  let renderCalls=[],canvasCalls=[];
  app.gl.render=(scene,camera)=>{
    scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
    renderCalls.push({scene:graphState(scene),camera:cameraState(camera),renderer:rendererState()});
  };
  function canvasStyle(c) {
    const keys=['font','fontKerning','fontStretch','fontVariantCaps','textRendering','letterSpacing',
      'wordSpacing','direction','textAlign','textBaseline','globalAlpha','globalCompositeOperation',
      'fillStyle','strokeStyle','shadowColor','shadowBlur','shadowOffsetX','shadowOffsetY','filter',
      'imageSmoothingEnabled','imageSmoothingQuality','lineWidth','lineCap','lineJoin','miterLimit'];
    const fields=Object.fromEntries(keys.map(k=>[k,value(c[k])]));
    fields.transform=Array.from(c.getTransform().toFloat64Array());return fields;
  }
  function canvasImage(source) {
    if(source===app.gl.domElement)return {role:'webgl-input',width:source.width,height:source.height};
    if(source===app.accum)return {role:'temporal-accumulation',width:source.width,height:source.height};
    throw Error('Unexpected pixel-dependent overlay image');
  }
  for(const [label,c] of [['output',app.ctx],['accumulation',app.actx]]) {
    c.drawImage=(source,...args)=>canvasCalls.push({context:label,call:'drawImage',image:canvasImage(source),args,style:canvasStyle(c)});
    for(const method of ['fillText','strokeText'])
      c[method]=(...args)=>canvasCalls.push({context:label,call:method,args,style:canvasStyle(c)});
    const measure=c.measureText.bind(c);
    c.measureText=(text)=>{
      const metric=measure(text),keys=['width','actualBoundingBoxLeft','actualBoundingBoxRight',
        'fontBoundingBoxAscent','fontBoundingBoxDescent','actualBoundingBoxAscent','actualBoundingBoxDescent',
        'emHeightAscent','emHeightDescent','hangingBaseline','alphabeticBaseline','ideographicBaseline'];
      canvasCalls.push({context:label,call:'measureText',text,style:canvasStyle(c),
        metrics:Object.fromEntries(keys.map(k=>[k,metric[k]]))});return metric;
    };
    // Fail closed if a later implementation needs pixels or extra 2D painting.
    for(const method of ['getImageData','putImageData','fillRect','strokeRect','clearRect','fill','stroke'])
      c[method]=()=>{throw Error('Unsupported pixel-dependent/additional canvas operation '+method)};
  }
  const staticState={geometry:staticGeometry,shaders:staticShaders,
    overlayBody:String(app.overlay),projectBody:String(app.project),drawInsertBody:String(app.drawInsert),
    fontFaces:Array.from(document.fonts).map(f=>({family:f.family,style:f.style,weight:f.weight,
      stretch:f.stretch,unicodeRange:f.unicodeRange,display:f.display,status:f.status})),
    dimensions:{width:app.w,height:app.h,outputCanvas:[app.canvas.width,app.canvas.height],
      accumulationCanvas:[app.accum.width,app.accum.height]}};
  window.__v3InputProbe={
    async sample(t) {
      if(app.scenes.active(t))throw Error('Active external cinematic insert is outside this proof');
      renderCalls=[];canvasCalls=[];app.frame(t,1);checkGeometryBytes();
      const components={renderCalls,finalScene:graphState(app.scene),finalPostScene:graphState(app.postScene),
        camera:cameraState(app.camera),postCamera:cameraState(app.postCam),
        postMaterial:materialState(app.postMat),renderer:rendererState(),labels:value(app.labels),
        canvasCalls,finalCanvasStyles:{output:canvasStyle(app.ctx),accumulation:canvasStyle(app.actx)},
        routeProgress:app.routes.routes.map(r=>app.routes.progress(t,r)),shot:app.scenes.shot(t),
        dimensions:staticState.dimensions};
      const componentHashes={};
      for(const [k,v] of Object.entries(components))componentHashes[k]=await digest(encode(v));
      // The browser hashes the complete exact state before discarding it.
      // Returning raw state for 1,201 OLD + NEW poses exhausts Node's heap.
      // Keep the lossless SHA-256 fingerprints and differing component names.
      return {t,digest:await digest(encode(componentHashes)),componentHashes};
    },
  };
  return {staticSHA256:await digest(encode(staticState)),staticState,
    uniqueGeometries:staticGeometry.length,uniqueShaderMaterials:staticShaders.length,
    geometryByteStores:bufferChecks.length,
    geometryBytesCheckedPerPose:bufferChecks.reduce((n,c)=>n+c.copy.length,0)};
}

function small(value) {
  const s=JSON.stringify(value);return s?.length>280?s.slice(0,280)+'…':value;
}
function differences(a,b,prefix='',out=[]) {
  if(out.length>=16)return out;
  if(Object.is(a,b))return out;
  if(a===null||b===null||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b)) {
    out.push({path:prefix,previous:small(a),current:small(b)});return out;
  }
  const keys=[...new Set([...Object.keys(a),...Object.keys(b)])].sort();
  for(const key of keys) {
    differences(a[key],b[key],prefix+'/'+key,out);if(out.length>=16)break;
  }
  return out;
}

try {
  const manifest=JSON.parse(await readFile(manifestPath,'utf8'));
  if(!manifest.complete||!manifest.sourceHashes)throw Error('Completed frozen source manifest required');
  for(const file of required)if(!manifest.sourceHashes[file])throw Error('Manifest missing '+file);
  const start=Number(args.start??0),seconds=Number(args.seconds??5),fps=Number(manifest.fps),poseHz=120;
  if(![start,seconds,fps].every(Number.isFinite)||start<0||seconds<=0||fps!==30
    ||Math.abs(start-manifest.start)>1e-9||Math.abs(seconds-manifest.seconds)>1e-9
    ||Math.abs(seconds*fps-manifest.frames)>1e-9||manifest.temporalSceneSamples!==1)
    throw Error('Requested interval must equal a complete 30fps, one-scene-sample segment manifest');
  if(start+seconds>20||!Number.isInteger(start*poseHz)||!Number.isInteger(seconds*poseHz))
    throw Error('Interval must fit 0..20 and the exact 120Hz pose grid');
  const [width,height]=manifest.internalResolution||[];
  if(width!==2160||height!==3840)throw Error('Expected frozen 2160x3840 internal manifest');
  const currentBytes={},currentHashes={},previousHashes={...manifest.sourceHashes},oldBytes={};
  for(const [file,expected] of Object.entries(manifest.sourceHashes)) {
    if(!/^[a-f0-9]{64}$/.test(expected))throw Error('Invalid manifest digest '+file);
    const full=path.resolve(root,file);if(!full.startsWith(root+path.sep))throw Error('Unsafe manifest path '+file);
    const bytes=await readFile(full);currentHashes[file]=sha(bytes);
    if(!changing.includes(file)&&currentHashes[file]!==expected)throw Error('Unchanged source/asset mismatch '+file);
    if(changing.includes(file))currentBytes[file]=bytes;
  }
  for(const file of changing) {
    oldBytes[file]=await readFile(path.join(previous,file));
    if(sha(oldBytes[file])!==manifest.sourceHashes[file])throw Error('Snapshot does not match frozen manifest '+file);
  }
  report.previousSourceHashes=previousHashes;report.currentSourceHashes=currentHashes;
  report.changedSources=changing.map(file=>({file,previous:previousHashes[file],current:currentHashes[file],
    changed:previousHashes[file]!==currentHashes[file]}));
  report.unchangedManifestSourcesVerified=Object.keys(manifest.sourceHashes).filter(f=>!changing.includes(f));
  const times=Array.from({length:seconds*poseHz+1},(_,i)=>(start*poseHz+i)/poseHz);
  report.sampling={start,end:start+seconds,poseHz,poseCount:times.length,nominalFps:fps,
    nominalFrameCount:manifest.frames,nominalFrameEnd:start+(manifest.frames-1)/fps,
    shutterOffsetsSeconds:[-1/120,1/120],frameSceneSamples:1,endpointIncluded:true,
    earliestPreparedTime:Math.max(0,start-1/120),latestPreparedTime:Math.min(20,start+seconds+1/120)};
  report.fingerprinting={hash:'SHA-256',numbers:'Exact IEEE-754 Float64 little-endian bits',
    geometry:'Actual typed-array bytes, attribute schema and index; immutable bytes checked at every pose',
    poses:'SHA-256 of sorted component hashes for every 120Hz sample and both recorded render passes',
    excludedIdentityFields:['id','uuid','Object3D.name','Material.name']};
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,
    args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  report.browserVersion=browser.version();
  async function collect(label,isPrevious) {
    const context=await browser.newContext({viewport:{width:1080,height:1920}}),page=await context.newPage();
    const errors=[],pending=[],httpHashes={},resourceHashes={};
    try {
      if(isPrevious)for(const file of changing)
        await page.route(url=>url.pathname==='/'+file,route=>route.fulfill({status:200,
          contentType:'text/javascript; charset=utf-8',body:oldBytes[file]}));
      page.on('pageerror',e=>errors.push(e.message));
      page.on('requestfailed',request=>errors.push('Request failed '+request.url()));
      page.on('response',response=>{
        const url=new URL(response.url()),file=url.pathname.slice(1);
        if(url.origin!=='http://127.0.0.1:8030') {
          errors.push('Unexpected non-local resource');return;
        }
        if(response.status()>=400)errors.push(file+' HTTP '+response.status());
        if(response.status()>=200&&response.status()<300)pending.push(response.body().then(bytes=>{
          const bodyHash=sha(bytes);
          if(resourceHashes[file]&&resourceHashes[file]!==bodyHash)
            errors.push(label+' runtime resource bytes changed during collection '+file);
          resourceHashes[file]=bodyHash;
          if(Object.hasOwn(manifest.sourceHashes,file)) {
            httpHashes[file]=resourceHashes[file];
            const expected=isPrevious?previousHashes[file]:currentHashes[file];
            if(httpHashes[file]!==expected)errors.push(label+' HTTP bytes mismatch '+file);
          }
        }).catch(error=>errors.push(label+' HTTP body read failed '+file+': '+error.message)));
      });
      await page.goto('http://127.0.0.1:8030/index_v3.html?width='+width,{waitUntil:'load'});
      await page.waitForFunction(()=>window.ready&&window.app,{timeout:90000});
      await page.evaluate(async()=>{await document.fonts.load("300 100px 'Open Sans'");await document.fonts.ready});
      await Promise.all(pending);if(errors.length)throw Error(errors.join('; '));
      const metadata=await page.evaluate(installProbe),samples=[];
      for(let i=0;i<times.length;i+=30) {
        const chunk=times.slice(i,i+30);
        let watchdog;
        try {
          samples.push(...await Promise.race([
            page.evaluate(async chunk=>{
              const rows=[];for(const t of chunk)rows.push(await window.__v3InputProbe.sample(t));return rows;
            },chunk),
            new Promise((_,reject)=>{watchdog=setTimeout(()=>reject(Error(
              label+' input collection exceeded 120 seconds for poses '+i+'..'+(i+chunk.length-1))),120000)}),
          ]));
        } finally {clearTimeout(watchdog)}
        report[isPrevious?'testedPreviousPoseCount':'testedCurrentPoseCount']=samples.length;
        console.log(label+' input poses '+samples.length+'/'+times.length);
      }
      await Promise.all(pending);if(errors.length)throw Error(errors.join('; '));
      for(const file of required.filter(f=>f!=='tools/render_v3.mjs'))
        if(!httpHashes[file])throw Error(label+' required asset/module not verified over HTTP '+file);
      return {metadata,samples,httpHashes,resourceHashes};
    } finally {await context.close()}
  }
  // Exactly one browser, OLD page/context closed before NEW starts.
  const old=await collect('OLD',true),now=await collect('NEW',false);
  report.previousStaticSHA256=old.metadata.staticSHA256;report.currentStaticSHA256=now.metadata.staticSHA256;
  report.staticInputsEqual=old.metadata.staticSHA256===now.metadata.staticSHA256;
  report.previousHTTPHashes=old.httpHashes;report.currentHTTPHashes=now.httpHashes;
  report.previousRuntimeResourceHashes=old.resourceHashes;report.currentRuntimeResourceHashes=now.resourceHashes;
  const resourceNames=[...new Set([...Object.keys(old.resourceHashes),...Object.keys(now.resourceHashes)])];
  const dependencyMismatches=resourceNames.filter(file=>!changing.includes(file)
    &&old.resourceHashes[file]!==now.resourceHashes[file]);
  report.runtimeResourcesEqual=dependencyMismatches.length===0;
  if(dependencyMismatches.length)report.mismatches.push({kind:'runtime-resources',files:dependencyMismatches});
  report.staticCoverage={uniqueGeometries:old.metadata.uniqueGeometries,
    uniqueShaderMaterials:old.metadata.uniqueShaderMaterials,geometryByteStores:old.metadata.geometryByteStores,
    geometryBytesCheckedPerPose:old.metadata.geometryBytesCheckedPerPose};
  if(!report.staticInputsEqual)report.mismatches.push({kind:'static',
    differences:differences(old.metadata.staticState,now.metadata.staticState)});
  report.poses=[];
  for(let i=0;i<times.length;i++) {
    const a=old.samples[i],b=now.samples[i],equal=a.digest===b.digest;
    report.poses.push({t:times[i],exactInputsEqual:equal,previousSHA256:a.digest,currentSHA256:b.digest});
    if(!equal)report.mismatches.push({kind:'pose',t:times[i],
      components:Object.keys(a.componentHashes).filter(k=>a.componentHashes[k]!==b.componentHashes[k]),
      rawValuesRetained:false});
  }
  // A renderer/source edit during the proof invalidates the result.
  for(const [file,before] of Object.entries(currentHashes))
    if(sha(await readFile(path.join(root,file)))!==before)throw Error('Current source changed during proof '+file);
  for(const file of changing)
    if(sha(await readFile(path.join(previous,file)))!==previousHashes[file])throw Error('Frozen snapshot changed during proof '+file);
  report.complete=true;report.testedPoseCount=times.length;
  report.exactInputsEqual=report.staticInputsEqual&&report.mismatches.length===0;
} catch(error) {
  report.error={name:error.name,message:error.message};report.exactInputsEqual=false;process.exitCode=1;
} finally {
  if(browser)await browser.close();
}
await mkdir(path.dirname(output),{recursive:true});
await writeFile(output,JSON.stringify(report,null,2),{flag:'wx'});
console.log(JSON.stringify({output,complete:report.complete,exactInputsEqual:report.exactInputsEqual,
  poses:report.testedPoseCount||0,mismatches:report.mismatches.length,error:report.error},null,2));
if(!report.exactInputsEqual)process.exitCode=1;
