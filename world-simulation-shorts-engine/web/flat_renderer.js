/** Optional PREMIUM FLAT / 2.5D renderer.
 * Actual Natural Earth vector coastlines and country polygons; an existing
 * licensed 8K surface raster is sampled in geographic UV space. The 2K topology
 * raster provides subtle material relief, not a surveyed DEM or invented terrain.
 * No sphere, atmospheric ray march, cloud shells or V3 post chain is constructed.
 */
import * as THREE from 'three';
import {createAircraftV3} from '/v3-src/aircraft_v3.js';
import {FlatSceneCore,FlatProjection,flatCoordinate,flatNumber,flatClamp,flatSmooth,flatWindow} from './flat_semantics.js';
import {drawAtmosphericVeil,mapTransitionOpacity,transitionAuditVisibility} from './map_transition.js';

const assetCache={countries:null,textures:new Map(),geometry:new Map()};
const COUNTRY_URL='/v3/assets/gis/countries_50m.geojson';
const DAY_URL='/v3/assets/v3/earth/earth-day-8k.jpg';
const TOPO_URL='/v3/assets/gis/earth-topology.png';
const KM_PER_DEGREE=111.195;

async function countries(){
 if(!assetCache.countries)assetCache.countries=fetch(COUNTRY_URL).then(r=>{if(!r.ok)throw Error('Natural Earth country asset missing');return r.json();});
 return assetCache.countries;
}
async function texture(url,srgb=false){
 if(!assetCache.textures.has(url))assetCache.textures.set(url,new THREE.TextureLoader().loadAsync(url).then(t=>{t.colorSpace=srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;t.wrapS=THREE.RepeatWrapping;t.wrapT=THREE.ClampToEdgeWrapping;t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;t.generateMipmaps=true;return t;}));
 return assetCache.textures.get(url);
}
const matchingCountry=(feature,id)=>['ISO_A3','ISO_A3_EH','ADM0_A3','ISO_A2','ADMIN','NAME','NAME_EN'].some(k=>String(feature.properties[k]).toUpperCase()===String(id).toUpperCase());
const countryName=feature=>feature.properties.ADMIN||feature.properties.NAME;

const surfaceVertex=`
 varying vec2 vMap;
 void main(){vMap=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}
`;
const surfaceFragment=`
 precision highp float;
 varying vec2 vMap;
 uniform sampler2D uDay,uTopo,uTerrain;
 uniform vec4 uTerrainBounds;
 uniform vec2 uTerrainTexel;
 uniform float uHasTerrain;
 uniform float uMercator,uLand,uTintOpacity,uFocusStrength,uFocusRadius,uClock;
 uniform vec3 uTint;
 uniform vec2 uFocus;
 const float PI=3.141592653589793;
 vec2 geographicUV(vec2 p){float lat=mix(p.y,(2.0*atan(exp(p.y*PI/180.0))-PI*.5)*180.0/PI,uMercator);return vec2(fract((p.x+180.0)/360.0),(lat+90.0)/180.0);}
 float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
 vec3 focusGrade(vec3 color){
  float d=length((vMap-uFocus)/max(.25,uFocusRadius));
  float focus=exp(-d*d*.62);
  float dim=1.-uFocusStrength*(1.-focus)*.72;
  float saturation=1.-uFocusStrength*(1.-focus)*.30;
  return mix(vec3(dot(color,vec3(.2126,.7152,.0722))),color,saturation)*dim*(1.+uFocusStrength*focus*.20);
 }
 void main(){
  // The ocean has no surface-image lookup or relief calculation: geographic
  // land masking comes from the exact vector polygons drawn above this plane.
  if(uLand<.5){
   float variation=.94+.035*sin(vMap.x*.12+vMap.y*.08);
   vec3 ocean=focusGrade(vec3(.007,.026,.060)*variation);
   ocean+=vec3((fract(gl_FragCoord.x*.75487766+gl_FragCoord.y*.56984029)-.5)/1700.);
   gl_FragColor=vec4(ocean,1.);
   #include <colorspace_fragment>
   return;
  }
  vec2 uv=geographicUV(vMap);vec2 texel=vec2(1.0/8192.0,1.0/4096.0);
  vec3 source,neighbors;
  float latitude=mix(vMap.y,(2.0*atan(exp(vMap.y*PI/180.0))-PI*.5)*180.0/PI,uMercator);
  vec2 terrainUV=(vec2(vMap.x,latitude)-uTerrainBounds.xy)/(uTerrainBounds.zw-uTerrainBounds.xy);
  if(uHasTerrain>.5&&terrainUV.x>=0.&&terrainUV.x<=1.&&terrainUV.y>=0.&&terrainUV.y<=1.){
   source=texture2D(uTerrain,terrainUV).rgb;
   neighbors=(texture2D(uTerrain,terrainUV+vec2(uTerrainTexel.x,0.)).rgb+texture2D(uTerrain,terrainUV-vec2(uTerrainTexel.x,0.)).rgb+texture2D(uTerrain,terrainUV+vec2(0.,uTerrainTexel.y)).rgb+texture2D(uTerrain,terrainUV-vec2(0.,uTerrainTexel.y)).rgb)*.25;
  }else{
   source=texture2D(uDay,uv).rgb;
   neighbors=(texture2D(uDay,uv+vec2(texel.x,0.)).rgb+texture2D(uDay,uv-vec2(texel.x,0.)).rgb+texture2D(uDay,uv+vec2(0.,texel.y)).rgb+texture2D(uDay,uv-vec2(0.,texel.y)).rgb)*.25;
  }
  source=max(vec3(.0),source+(source-neighbors)*.46);
  float gray=dot(source,vec3(.2126,.7152,.0722));
  source=max(vec3(.0),mix(vec3(gray),source,1.32));
  vec2 topopixel=vec2(1./2048.,1./1024.);
  float elevation=texture2D(uTopo,uv).r;
  vec2 derivative=vec2(texture2D(uTopo,uv+vec2(topopixel.x,0.)).r-elevation,texture2D(uTopo,uv+vec2(0.,topopixel.y)).r-elevation)*2.;
  vec3 normal=normalize(vec3(-derivative*4.2,1.));
  float hill=.83+.24*max(0.,dot(normal,normalize(vec3(-.45,.62,1.))));
  vec3 land=source*.63*hill*vec3(1.025,1.025,.93)+vec3(.002,.004,.001);
  vec3 color=land;
  color=mix(color,uTint,uTintOpacity*uLand*.85);
  color=focusGrade(color);
  color+=vec3((fract(gl_FragCoord.x*.75487766+gl_FragCoord.y*.56984029)-.5)/1400.);
  gl_FragColor=vec4(color,1.);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
 }
`;
const ribbonVertex=`
 attribute vec2 aNormal;
 attribute float aSide,aProgress;
 uniform float uWidth;
 varying float vProgress,vSide;
 void main(){vec3 p=position;p.xy+=aNormal*aSide*uWidth;vProgress=aProgress;vSide=aSide;gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.);}
`;
const ribbonFragment=`
 precision highp float;
 uniform vec3 uColor;uniform float uOpacity,uProgress,uTail,uCompleted,uGlow;
 varying float vProgress,vSide;
 void main(){
  if(vProgress>uProgress+.00005)discard;
  float edge=pow(max(0.,1.-abs(vSide)),mix(.18,1.6,uGlow));
  float trail=smoothstep(uProgress-uTail,uProgress,vProgress);
  float alpha=uOpacity*edge*mix(.75,.99,trail);
  alpha=mix(alpha,uOpacity*.66,uCompleted);
  gl_FragColor=vec4(mix(uColor,vec3(1.),max(0.,1.-abs(vSide))*.23*(1.-uGlow)),alpha);
  #include <colorspace_fragment>
 }
`;
function ribbonGeometry(points,closed=false){
 const positions=[],normals=[],sides=[],progress=[],indices=[];
 const distances=[0];for(let i=1;i<points.length;i++)distances.push(distances.at(-1)+points[i].distanceTo(points[i-1]));
 const total=Math.max(.00001,distances.at(-1));
 for(let i=0;i<points.length;i++){
  const previous=points[Math.max(0,i-1)],next=points[Math.min(points.length-1,i+1)],delta=next.clone().sub(previous);
  const n=new THREE.Vector2(-delta.y,delta.x).normalize();
  for(const side of [-1,1]){positions.push(...points[i].toArray());normals.push(n.x,n.y);sides.push(side);progress.push(distances[i]/total);}
  if(i<points.length-1){const k=i*2;indices.push(k,k+1,k+2,k+1,k+3,k+2);}
 }
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.setAttribute('aNormal',new THREE.Float32BufferAttribute(normals,2));g.setAttribute('aSide',new THREE.Float32BufferAttribute(sides,1));g.setAttribute('aProgress',new THREE.Float32BufferAttribute(progress,1));g.setIndex(indices);return g;
}
function ribbonMaterial(color,width,opacity=.7,glow=0){return new THREE.ShaderMaterial({vertexShader:ribbonVertex,fragmentShader:ribbonFragment,uniforms:{uColor:{value:new THREE.Color(color)},uWidth:{value:width},uOpacity:{value:opacity},uProgress:{value:1},uTail:{value:2},uCompleted:{value:1},uGlow:{value:glow}},transparent:true,depthWrite:false,side:THREE.DoubleSide,toneMapped:false});}
function landMaterial(day,topo,projection,terrain=null,bounds=null){return new THREE.ShaderMaterial({vertexShader:surfaceVertex,fragmentShader:surfaceFragment,uniforms:{uDay:{value:day},uTopo:{value:topo},uTerrain:{value:terrain||day},uTerrainBounds:{value:new THREE.Vector4(...(bounds||[-180,-90,180,90]))},uTerrainTexel:{value:new THREE.Vector2(1/(terrain?.image.width||8192),1/(terrain?.image.height||4096))},uHasTerrain:{value:terrain?1:0},uMercator:{value:projection.kind==='LOCAL_MERCATOR'?1:0},uLand:{value:1},uTint:{value:new THREE.Color('#c99e5b')},uTintOpacity:{value:0},uFocus:{value:new THREE.Vector2()},uFocusStrength:{value:0},uFocusRadius:{value:5},uClock:{value:0}},depthWrite:true,side:THREE.DoubleSide,toneMapped:false});}
function projectRing(ring,projection){
 const result=ring.map(c=>projection.point(c));
 for(let i=1;i<result.length;i++){while(result[i].x-result[i-1].x>180)result[i].x-=360;while(result[i].x-result[i-1].x< -180)result[i].x+=360;}
 const mean=result.reduce((v,p)=>v+p.x,0)/result.length,shift=Math.round((projection.center.lon-mean)/360)*360;
 for(const p of result)p.x+=shift;
 return result;
}
function projectedGeometry(feature,projection,extent){
 const key=`${feature.properties.NE_ID}:${projection.kind}:${Math.floor(projection.center.lon/45)}:${extent.join(',')}`;
 if(assetCache.geometry.has(key))return assetCache.geometry.get(key);
 const shapes=[],rings=[],polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
 for(const polygon of polygons){
  const outer=projectRing(polygon[0],projection);if(outer.length<4)continue;
  const box=new THREE.Box3().setFromPoints(outer);
  if(box.max.x<extent[0]||box.min.x>extent[1]||box.max.y<extent[2]||box.min.y>extent[3]||box.max.x-box.min.x>240)continue;
  const shape=new THREE.Shape(outer.map(p=>new THREE.Vector2(p.x,p.y)));
  rings.push(outer.map(p=>new THREE.Vector3(p.x,p.y,.014)));
  for(const hole of polygon.slice(1)){const pts=projectRing(hole,projection);shape.holes.push(new THREE.Path(pts.map(p=>new THREE.Vector2(p.x,p.y))));rings.push(pts.map(p=>new THREE.Vector3(p.x,p.y,.014)));}
  shapes.push(shape);
 }
 const result={geometry:shapes.length?new THREE.ShapeGeometry(shapes,12):null,rings};assetCache.geometry.set(key,result);return result;
}

function shipModel(){
 const group=new THREE.Group();group.name='CIVILIAN_CARGO_SHIP_3D_FLAT';
 const hull=new THREE.MeshStandardMaterial({color:0x284557,roughness:.45,metalness:.28});
 const deck=new THREE.MeshStandardMaterial({color:0xb6b29e,roughness:.7});
 const ivory=new THREE.MeshStandardMaterial({color:0xe5e6df,roughness:.4,metalness:.18});
 const shape=new THREE.Shape();shape.moveTo(-.21,-.70);shape.lineTo(-.27,-.55);shape.lineTo(-.25,.45);shape.quadraticCurveTo(-.20,.69,0,.84);shape.quadraticCurveTo(.20,.69,.25,.45);shape.lineTo(.27,-.55);shape.lineTo(.21,-.70);shape.closePath();
 const geometry=new THREE.ExtrudeGeometry(shape,{depth:.14,bevelEnabled:true,bevelSize:.022,bevelThickness:.025,bevelSegments:3,curveSegments:18});geometry.translate(0,0,-.05);group.add(new THREE.Mesh(geometry,hull));
 const floor=new THREE.Mesh(new THREE.ShapeGeometry(shape,18),deck);floor.position.z=.105;group.add(floor);
 const colors=[0x547783,0xa68664,0x708a72,0x8b9ba1];
 for(let y=-.25,j=0;y<.44;y+=.18,j++)for(let x=-.14,k=0;x<.15;x+=.14,k++){
  const container=new THREE.Mesh(new THREE.BoxGeometry(.125,.156,.14),new THREE.MeshStandardMaterial({color:colors[(j+k)%4],roughness:.7,metalness:.15}));container.position.set(x,y,.19);group.add(container);
 }
 const house=new THREE.Mesh(new THREE.BoxGeometry(.38,.18,.20),ivory);house.position.set(0,-.47,.23);group.add(house);
 const bridge=new THREE.Mesh(new THREE.BoxGeometry(.40,.065,.075),ivory);bridge.position.set(0,-.45,.365);group.add(bridge);
 const glass=new THREE.Mesh(new THREE.BoxGeometry(.35,.008,.028),new THREE.MeshStandardMaterial({color:0x1a3e52,roughness:.16,metalness:.6}));glass.position.set(0,-.41,.37);group.add(glass);return group;
}
function vehicleModel(){
 const group=new THREE.Group(),silver=new THREE.MeshStandardMaterial({color:0xe0e2da,roughness:.35,metalness:.3}),dark=new THREE.MeshStandardMaterial({color:0x213b47,roughness:.5});
 const body=new THREE.Mesh(new THREE.BoxGeometry(.54,1,.25),silver);body.position.z=.16;group.add(body);
 const cabin=new THREE.Mesh(new THREE.BoxGeometry(.46,.36,.24),silver);cabin.position.set(0,.21,.38);group.add(cabin);
 const windscreen=new THREE.Mesh(new THREE.BoxGeometry(.42,.012,.12),dark);windscreen.position.set(0,.40,.40);group.add(windscreen);
 for(const x of [-.28,.28])for(const y of [-.30,.30]){const wheel=new THREE.Mesh(new THREE.CylinderGeometry(.12,.12,.08,16),dark);wheel.rotation.z=Math.PI/2;wheel.position.set(x,y,.12);group.add(wheel);}return group;
}
function markerModel(type){
 const group=new THREE.Group(),body=new THREE.MeshStandardMaterial({color:0xd5a160,roughness:.36,metalness:.3});
 const base=new THREE.Mesh(new THREE.CylinderGeometry(.15,.19,.035,32),body);base.rotation.x=Math.PI/2;base.position.z=.04;group.add(base);
 const cap=new THREE.Mesh(new THREE.SphereGeometry(.10,24,16),new THREE.MeshStandardMaterial({color:0xffe6bd,emissive:0x493721,roughness:.25}));cap.position.z=.15;group.add(cap);
 if(type==='port'){const dock=new THREE.Mesh(new THREE.BoxGeometry(.11,.4,.045),body);dock.position.set(.22,0,.04);group.add(dock);}return group;
}
const discTexture=(()=>{let result;return ()=>{if(result)return result;const size=64,data=new Uint8Array(size*size*4);for(let y=0;y<size;y++)for(let x=0;x<size;x++){const d=Math.hypot((x-size/2)/(size/2),(y-size/2)/(size/2)),i=(y*size+x)*4;data[i]=data[i+1]=data[i+2]=255;data[i+3]=Math.round(255*Math.exp(-d*d*6)*Math.max(0,1-d));}result=new THREE.DataTexture(data,size,size);result.needsUpdate=true;return result;};})();
function shadowMesh(){return new THREE.Mesh(new THREE.PlaneGeometry(1.3,1.9),new THREE.MeshBasicMaterial({map:discTexture(),color:0x07121b,transparent:true,opacity:.27,depthWrite:false}));}

class FlatRoutesGraphics {
 constructor(renderer){
  this.renderer=renderer;this.items=renderer.core.routes.map(route=>{
   const steps=Math.max(96,Math.min(640,Math.round(route.total*500))),points=Array.from({length:steps+1},(_,i)=>route.point(i/steps));
   const g=ribbonGeometry(points),color=route.spec.color||'#b8f0f6';
   const mat=ribbonMaterial(color,.012,route.faint?.36:.95,0),glowMat=ribbonMaterial(color,.035,route.faint?.055:.12,1);
   if(!route.faint)mat.uniforms.uColor.value.lerp(new THREE.Color('#e1fbff'),.70);
   mat.uniforms.uTail.value=route.faint?.40:.22;glowMat.uniforms.uTail.value=.18;
   const mesh=new THREE.Mesh(g,mat),glow=new THREE.Mesh(g,glowMat);mesh.renderOrder=4;glow.renderOrder=3;
   const head=new THREE.Mesh(new THREE.SphereGeometry(.035,20,12),new THREE.MeshBasicMaterial({color:0xecffff,toneMapped:false}));head.renderOrder=5;
   const headTrail=[1/100,1/60].map((lag,i)=>{const ghost=new THREE.Mesh(head.geometry,new THREE.MeshBasicMaterial({color:0xc4f5f9,transparent:true,opacity:i===0?.12:.05,depthWrite:false,toneMapped:false}));renderer.world.add(ghost);return {ghost,lag};});
   renderer.world.add(glow,mesh,head);
   return {route,mesh,glow,head,headTrail,mat,glowMat};
  });
 }
 update(t){
  const scale=this.renderer.core.cam.current.span/this.renderer.w;
  for(const item of this.items){
   const {route,mesh,glow,head,mat,glowMat}=item,p=this.renderer.core.routeProgress(route,t),shown=route.shown(t);
   const heldComplete=flatNumber(route.spec.progress_start)>=.999999&&flatNumber(route.spec.progress_end,1)>=.999999;
   const completed=heldComplete||p>=.999999&&t>=route.end,done=heldComplete?1:flatSmooth((t-route.end)/.35);
   mesh.visible=glow.visible=shown&&p>0;
   for(const m of [mat,glowMat]){m.uniforms.uProgress.value=p;m.uniforms.uCompleted.value=done;}
   mat.uniforms.uOpacity.value=route.faint?.35:completed?.50:.98;
   glowMat.uniforms.uOpacity.value=route.faint?.05:completed?.04:.14;
   mat.uniforms.uWidth.value=scale*(route.faint?2.3:completed?2.5:5.0);glowMat.uniforms.uWidth.value=scale*(route.faint?5.5:completed?6.5:10.5);
   head.visible=shown&&!route.faint&&t<route.end&&p<.999999;
   head.position.copy(route.point(p,.055));head.scale.setScalar(scale*4.7/.035);
   for(const {ghost,lag} of item.headTrail){ghost.visible=head.visible;ghost.position.copy(route.point(this.renderer.core.routeProgress(route,Math.max(0,t-lag)),.052));ghost.scale.setScalar(scale*4.5/.035);}
  }
 }
}

class FlatEntitiesGraphics {
 constructor(renderer){
  this.renderer=renderer;this.items=renderer.core.entities.map(spec=>{
   const model=spec.type==='aircraft'?createAircraftV3():spec.type==='cargo_ship'?shipModel():spec.type==='vehicle'?vehicleModel():markerModel(spec.type);
   model.traverse(o=>{if(o.isMesh){for(const material of Array.isArray(o.material)?o.material:[o.material]){material.transparent=true;material.depthWrite=true;}}});
   const shadow=shadowMesh();shadow.renderOrder=2;renderer.world.add(shadow,model);
   const ghosts=[1/100,1/60].map((lag,index)=>{
    const ghost=model.clone(true),materials=new Map();
    ghost.traverse(o=>{if(o.isMesh){const clone=m=>{if(!materials.has(m)){const copy=m.clone();copy.transparent=true;copy.depthWrite=false;copy.opacity=index===0?.06:.03;materials.set(m,copy);}return materials.get(m);};o.material=Array.isArray(o.material)?o.material.map(clone):clone(o.material);}});
    renderer.world.add(ghost);return {model:ghost,lag,opacity:index===0?.06:.03};
   });
   return {spec,model,shadow,ghosts,bounds:new THREE.Box3().setFromObject(model)};
  });
 }
 update(t,poses){
  const renderer=this.renderer,scale=renderer.core.cam.current.span/renderer.w;
  for(const [i,item] of this.items.entries()){
   const pose=poses[i],{spec,model,shadow}=item;
   const pixels=flatNumber(spec.screen_size,spec.type==='aircraft'?74:spec.type==='cargo_ship'?65:spec.type==='vehicle'?45:22)*(renderer.w/1080);
   const worldScale=pixels*scale/(spec.type==='aircraft'?1.45:spec.type==='cargo_ship'?1.54:1.0);
   model.visible=shadow.visible=pose.visible;model.position.copy(pose.position);model.scale.setScalar(worldScale);
   const heading=Math.atan2(-pose.tangent.x,pose.tangent.y);
   model.rotation.set(0,spec.type==='aircraft'?.065*Math.sin(t*1.3):0,heading);
   model.position.z=Math.max(.16,worldScale*.13+.045);
   shadow.position.set(pose.position.x+worldScale*.11,pose.position.y-worldScale*.17,.020);
   shadow.rotation.z=heading;shadow.scale.set(worldScale*.90,worldScale*.86,1);shadow.material.opacity=.24*pose.alpha;
   model.traverse(o=>{if(o.isMesh)for(const material of Array.isArray(o.material)?o.material:[o.material])material.opacity=pose.alpha;});
   model.userData.alpha=pose.alpha;model.updateMatrixWorld(true);
   for(const ghost of item.ghosts){
    const before=renderer.core.entityPose(spec,Math.max(0,t-ghost.lag));
    const movement=renderer.core.project(before.position),current=renderer.core.project(pose.position);
    ghost.model.visible=model.visible&&Math.hypot(movement.x-current.x,movement.y-current.y)>.50;
    ghost.model.position.copy(before.position);ghost.model.position.z=model.position.z;ghost.model.scale.copy(model.scale);
    ghost.model.rotation.set(0,spec.type==='aircraft'?.065*Math.sin((t-ghost.lag)*1.3):0,Math.atan2(-before.tangent.x,before.tangent.y));
    ghost.model.traverse(o=>{if(o.isMesh)for(const material of Array.isArray(o.material)?o.material:[o.material])material.opacity=ghost.opacity*pose.alpha;});
   }
  }
 }
}

const vfxVertex=`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const vfxFragment=`
 precision highp float;varying vec2 vUv;uniform float uAge,uKind,uOpacity;uniform vec3 uColor;
 const float PI=3.14159265359;
 void main(){
  vec2 p=vUv*2.-1.;float radius=length(p),angle=atan(p.y,p.x),alpha=0.;
  float ring=1.-smoothstep(.012,.030,abs(radius-(.14+.66*uAge)));
  if(uKind<.5){float aura=exp(-radius*radius*12.)*(1.-uAge);alpha=ring*.24+aura*.30;}
  else if(uKind<1.5){float sweep=mod(angle-uAge*PI*2.+PI*4.,PI*2.);alpha=exp(-sweep*3.0)*smoothstep(.9,.1,radius)*.32+ring*.09;}
  else if(uKind<2.5){float chevrons=(1.-smoothstep(.04,.07,abs(abs(p.x)-(.20+.14*sin(uAge*PI)))))*(1.-smoothstep(.28,.35,abs(p.y)));alpha=chevrons*.32+exp(-radius*radius*10.)*.11;}
  else if(uKind<3.5){float core=exp(-radius*radius*(50.+uAge*40.))*(1.-uAge);alpha=ring*.28+core*.45;}
  else if(uKind<4.5){alpha=ring*.36;}
  else{alpha=smoothstep(.9,.65,radius)*.12;}
  if(radius>1.)discard;gl_FragColor=vec4(uColor,alpha*uOpacity);
  #include <colorspace_fragment>
 }
`;
class FlatEffectsGraphics {
 constructor(renderer){
  this.renderer=renderer;this.items=(renderer.sceneSpec.visual_events||[]).filter(e=>e.coordinates).map(event=>{
   const aliases={arrival:0,destination_pulse:0,city_focus:0,pulse:0,radar:1,warning:2,route_blocked:2,route_block:2,impact:3,shockwave:4,area_highlight:5,region_highlight:5};
   const kind=aliases[event.kind];if(kind===undefined)return null;
   const mat=new THREE.ShaderMaterial({vertexShader:vfxVertex,fragmentShader:vfxFragment,uniforms:{uAge:{value:0},uKind:{value:kind},uOpacity:{value:0},uColor:{value:new THREE.Color(kind===2?'#dfb079':kind===3?'#e8bc89':'#a6dadd')}},transparent:true,depthWrite:false,side:THREE.DoubleSide,toneMapped:false});
   const mesh=new THREE.Mesh(new THREE.PlaneGeometry(1,1),mat);mesh.renderOrder=6;mesh.position.copy(renderer.core.projection.point(event.coordinates,.07));renderer.world.add(mesh);
   let barrier=null;
   if(['route_blocked','route_block'].includes(event.kind)){
    barrier=new THREE.Group();const material=new THREE.MeshStandardMaterial({color:0xdfab70,roughness:.42,metalness:.25});
    for(const x of [-.32,.32]){const post=new THREE.Mesh(new THREE.CylinderGeometry(.022,.024,.20,12),material);post.rotation.x=Math.PI/2;post.position.set(x,0,.13);barrier.add(post);}
    const beam=new THREE.Mesh(new THREE.BoxGeometry(.75,.055,.055),material);beam.position.z=.21;barrier.add(beam);barrier.position.copy(mesh.position);renderer.world.add(barrier);
   }
   return {event,mesh,mat,barrier};
  }).filter(Boolean);
 }
 update(frame){
  const renderer=this.renderer,scale=renderer.core.cam.current.span/renderer.w;
  for(const item of this.items){
   const effect=frame.vfx.find(v=>v.event.id===item.event.id);
   item.mesh.visible=Boolean(effect?.visible);item.mat.uniforms.uAge.value=effect?.age||0;item.mat.uniforms.uOpacity.value=effect?.opacity||0;
   item.mesh.scale.setScalar(scale*250*(renderer.w/1080));
   if(item.barrier){item.barrier.visible=Boolean(effect?.visible&&effect.opacity>.01);item.barrier.scale.setScalar(scale*70*(renderer.w/1080));}
  }
 }
}

export class SceneFlatRenderer {
 constructor(scene,plan){
  this.sceneSpec=scene;this.plan=plan;this.duration=flatNumber(scene.duration);
  const query=new URLSearchParams(location.search);this.w=flatNumber(query.get('width')||2160,2160);this.h=Math.round(this.w*16/9);
  this.canvas=document.createElement('canvas');this.canvas.width=this.w;this.canvas.height=this.h;this.ctx=this.canvas.getContext('2d',{alpha:false});
  this.accum=document.createElement('canvas');this.accum.width=this.w;this.accum.height=this.h;this.actx=this.accum.getContext('2d',{alpha:false});
  this.labels=[];this.lastFrameTime=0;this.world=new THREE.Scene();this.world.background=new THREE.Color('#163847');
  this.gl=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'low-power'});
  this.gl.setPixelRatio(1);this.gl.setSize(this.w,this.h,false);this.gl.outputColorSpace=THREE.SRGBColorSpace;this.gl.toneMapping=THREE.NoToneMapping;
  this.gl.sortObjects=true;this.gl.shadowMap.enabled=false;
  document.body.append(this.canvas);
 }
 async init(){
  await Promise.all([document.fonts.load("300 100px 'Open Sans'"),document.fonts.load("400 68px 'Noto Cinema'",'세계 항로 서울')]);
  const roi=this.sceneSpec.flat_map?.terrain_texture;
  const [data,day,topo,terrain]=await Promise.all([countries(),texture(DAY_URL,true),texture(TOPO_URL),roi?texture(roi.url,true):Promise.resolve(null)]);
  this.data=data;this.day=day;this.topo=topo;
  this.terrain=terrain;this.terrainBounds=roi?.bounds||null;
  if(terrain&&(!Array.isArray(this.terrainBounds)||this.terrainBounds.length!==4||!(this.terrainBounds[0]<this.terrainBounds[2]&&this.terrainBounds[1]<this.terrainBounds[3])))throw Error('GEOGRAPHIC_TERRAIN_ATLAS_BOUNDS_REQUIRED');
  this.core=new FlatSceneCore(this.sceneSpec,this.plan,{width:this.w,height:this.h,context:this.ctx,countries:data});this.camera=this.core.camera;this.cam=this.core.cam;
  this.countryItems=[];this.materials=[];
  const start=this.core.projection.point(this.core.cam.start),end=this.core.projection.point(this.core.cam.end),span=Math.max(this.core.cam.start.span_degrees,this.core.cam.end.span_degrees),vertical=span*this.h/this.w;
  this.extent=[Math.min(start.x,end.x)-span*1.1,Math.max(start.x,end.x)+span*1.1,Math.min(start.y,end.y)-vertical*.8,Math.max(start.y,end.y)+vertical*.8];
  const oceanGeometry=new THREE.PlaneGeometry(this.extent[1]-this.extent[0],this.extent[3]-this.extent[2]);
  oceanGeometry.translate((this.extent[0]+this.extent[1])/2,(this.extent[2]+this.extent[3])/2,-.012);
  const oceanMaterial=landMaterial(day,topo,this.core.projection,terrain,this.terrainBounds);oceanMaterial.uniforms.uLand.value=0;this.materials.push(oceanMaterial);this.world.add(new THREE.Mesh(oceanGeometry,oceanMaterial));
  for(const feature of data.features){
   const cached=projectedGeometry(feature,this.core.projection,this.extent);if(!cached.geometry)continue;
   const material=landMaterial(day,topo,this.core.projection,terrain,this.terrainBounds);this.materials.push(material);
   const mesh=new THREE.Mesh(cached.geometry,material);mesh.renderOrder=1;this.world.add(mesh);
   const borderMaterial=ribbonMaterial('#a0b0a5',.003,.42,0);borderMaterial.uniforms.uTail.value=2;borderMaterial.uniforms.uCompleted.value=1;
   const borders=cached.rings.map(ring=>{const line=new THREE.Mesh(ribbonGeometry(ring,true),borderMaterial);line.renderOrder=2;this.world.add(line);return line;});
   this.countryItems.push({feature,material,borderMaterial,borders,name:countryName(feature)});
  }
  for(const highlight of this.core.countryTargets)if(!data.features.some(f=>matchingCountry(f,highlight.country)))throw Error('COUNTRY_HIGHLIGHT_ASSET_MISSING '+highlight.country);
  const sun=new THREE.DirectionalLight(0xffefce,2.0);sun.position.set(-15,24,50);this.world.add(sun);
  const fill=new THREE.HemisphereLight(0xd5e8ed,0x293b35,1.55);fill.position.set(0,0,100);this.world.add(fill);
  this.graphics=new FlatRoutesGraphics(this);this.entities=new FlatEntitiesGraphics(this);this.effects=new FlatEffectsGraphics(this);
  this.map={surface:{uniforms:{uDay:{value:day},uTopo:{value:topo}}}};
  this.frame(0);return this;
 }
 updateMap(t){
  const focus=(this.sceneSpec.flat_map?.focus||[]).filter(f=>t>=flatNumber(f.start_time)&&t<=flatNumber(f.end_time,this.duration)).at(-1);
  let point=this.core.projection.point(focus?.coordinates||this.sceneSpec.coordinates),strength=0,radius=5;
  if(focus){const start=flatNumber(focus.start_time),end=flatNumber(focus.end_time,this.duration);strength=flatNumber(focus.strength,.16)*flatWindow(t,start,end,.3,Boolean(focus.persistent||end>=this.duration));radius=flatNumber(focus.radius_degrees,5);}
  const pixel=this.core.cam.current.span/this.w;
  for(const material of this.materials){material.uniforms.uFocus.value.set(point.x,point.y);material.uniforms.uFocusStrength.value=strength;material.uniforms.uFocusRadius.value=radius;material.uniforms.uClock.value=t;}
  for(const item of this.countryItems){
   const highlight=this.core.countryTargets.filter(h=>matchingCountry(item.feature,h.country)&&t>=flatNumber(h.start_time)&&t<=flatNumber(h.end_time,this.duration)).at(-1);
   const weight=highlight?flatWindow(t,flatNumber(highlight.start_time),flatNumber(highlight.end_time,this.duration),.32,Boolean(highlight.persistent)) * flatNumber(highlight.opacity,.20):0;
   item.material.uniforms.uTintOpacity.value=weight;
   if(highlight)item.material.uniforms.uTint.value.set(highlight.color||'#d0ab6b');
   item.borderMaterial.uniforms.uWidth.value=pixel*(weight>0?3.0:1.40);
   item.borderMaterial.uniforms.uOpacity.value=.42+weight*1.6;
   item.borderMaterial.uniforms.uColor.value.set(highlight?.color||'#a0b0a5');
  }
 }
 drawOverlay(frame){
  const c=this.ctx,s=this.w/1080;
  this.labels=frame.labels;
  for(const label of frame.labels){
   c.save();c.globalAlpha=label.opacity;c.font=`${label.fontFamily==='Noto Cinema'?400:300} ${label.font}px '${label.fontFamily||'Open Sans'}'`;
   if(label.information){
    const pad=18*s,gradient=c.createLinearGradient(label.x-pad,label.y-pad,label.x+label.width+pad,label.y-pad);
    gradient.addColorStop(0,'rgba(9,29,39,.78)');gradient.addColorStop(.82,'rgba(9,29,39,.55)');gradient.addColorStop(1,'rgba(9,29,39,0)');
    c.fillStyle=gradient;c.fillRect(label.x-pad,label.y-8*s,label.width+2*pad,label.height+16*s);
   }else{
    c.strokeStyle='rgba(18,43,52,.45)';c.lineWidth=1.1*s;
    const edgeX=label.x+label.width*.36,edgeY=label.y+label.height+5*s;
    c.beginPath();c.moveTo(label.anchor.x,label.anchor.y);c.lineTo(label.anchor.x+(edgeX-label.anchor.x)*.35,edgeY);c.lineTo(edgeX,edgeY);c.stroke();
    c.fillStyle='#f2ce91';c.beginPath();c.arc(label.anchor.x,label.anchor.y,3.3*s,0,Math.PI*2);c.fill();
   }
   // Ivory names have a small dark edge: they remain readable over both warm
   // terrain and deep ocean without a glowing HUD, opaque plate or heavy font.
   c.fillStyle=label.color;c.shadowColor='rgba(6,22,31,.92)';c.shadowBlur=3.0*s;c.shadowOffsetY=1.0*s;
   if(!label.information){c.strokeStyle='rgba(7,25,36,.82)';c.lineWidth=3.0*s;let x=label.x;for(const ch of label.text){c.strokeText(ch,x,label.y+label.font);x+=c.measureText(ch).width+(label.spacing||0);}}
   let x=label.x;for(const ch of label.text){c.fillText(ch,x,label.y+label.font);x+=c.measureText(ch).width+(label.spacing||0);}c.restore();
  }
  // A very weak physical edge falloff, without atmospheric haze over geography.
  const shade=c.createRadialGradient(this.w*.48,this.h*.48,this.w*.25,this.w*.5,this.h*.5,this.h*.69);
  shade.addColorStop(0,'rgba(0,0,0,0)');shade.addColorStop(.7,'rgba(0,0,0,.015)');shade.addColorStop(1,'rgba(0,0,0,.12)');c.fillStyle=shade;c.fillRect(0,0,this.w,this.h);
 }
 sceneAt(t){
  const frame=this.core.semanticFrame(t);this.updateMap(t);this.graphics.update(t);this.entities.update(t,frame.entities);this.effects.update(frame);
  this.gl.render(this.world,this.camera);return frame;
 }
 frame(t,samples=1){
  t=flatClamp(t,0,this.duration);this.lastFrameTime=t;
  // Temporal integration only when requested; map/labels remain sharp at rest.
  for(let i=0;i<samples;i++){
   this.sceneAt(flatClamp(t+(samples>1?(i/(samples-1)-.5)/90:0),0,this.duration));
   this.actx.globalAlpha=1/(i+1);this.actx.drawImage(this.gl.domElement,0,0);
  }
  this.ctx.globalAlpha=1;this.ctx.drawImage(this.accum,0,0);
  this.currentFrame=this.core.semanticFrame(t);this.updateMap(t);this.graphics.update(t);this.entities.update(t,this.currentFrame.entities);this.effects.update(this.currentFrame);this.drawOverlay(this.currentFrame);
  this.transitionOpacity=mapTransitionOpacity(this.sceneSpec,t);
  drawAtmosphericVeil(this.ctx,this.w,this.h,this.transitionOpacity,flatNumber(this.sceneSpec.render_time_offset,this.sceneSpec.start_time)+t);
  return this.canvas;
 }
 project(point){return this.core.project(point);}
 audit(t){
  const f=this.currentFrame||this.core.semanticFrame(t),entityAudit=this.entities.items.map((item,index)=>{
   const pose=f.entities[index],model=item.model,p=this.core.project(model.position);
   const bounds=new THREE.Box3().setFromObject(model),points=[];
   for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z])points.push(this.core.project(new THREE.Vector3(x,y,z)));
   const radiusPixels=Math.max(...points.map(q=>Math.hypot(q.x-p.x,q.y-p.y)));
   const clipped=model.visible&&p.visible&&(p.x+radiusPixels<0||p.x-radiusPixels>this.w||p.y+radiusPixels<0||p.y-radiusPixels>this.h);
   return {id:item.spec.id,type:item.spec.type,route_id:pose.route?.id||null,visibility_role:item.spec.visibility_role,context_culled:false,position:model.position.toArray(),quaternion:model.quaternion.toArray(),radius:null,...p,visible:model.visible,screenVisible:p.visible&&p.x+radiusPixels>=0&&p.x-radiusPixels<=this.w&&p.y+radiusPixels>=0&&p.y-radiusPixels<=this.h,clipped,screenRadius:radiusPixels,cartographicScale:model.scale.x,minimumMapClearance:bounds.min.z,action:pose.mode};
  });
  const textures={uDay:{width:this.day.image.width,height:this.day.image.height,loaded:true},uTopo:{width:this.topo.image.width,height:this.topo.image.height,loaded:true}};
  if(this.terrain)textures.uTerrain={width:this.terrain.image.width,height:this.terrain.image.height,loaded:true,bounds:this.terrainBounds,url:this.sceneSpec.flat_map.terrain_texture.url};
  const missingTextures=Object.entries(textures).filter(([key,image])=>!image.loaded||!image.width||!image.height||(key==='uDay'&&(image.width!==8192||image.height!==4096))).map(([key])=>key);
  const activeFocus=(this.sceneSpec.flat_map?.focus||[]).filter(focus=>t>=flatNumber(focus.start_time)&&t<=flatNumber(focus.end_time,this.duration)).at(-1);
  let focusTargetBox=null;
  if(activeFocus&&this.materials[0].uniforms.uFocusStrength.value>.005){
   const point=this.core.projection.point(activeFocus.coordinates||this.sceneSpec.coordinates),radius=flatNumber(activeFocus.radius_degrees,5);
   const corners=[new THREE.Vector3(point.x-radius,point.y-radius,0),new THREE.Vector3(point.x+radius,point.y+radius,0)].map(p=>this.core.project(p));
   const left=Math.max(0,Math.min(...corners.map(p=>p.x))),right=Math.min(this.w,Math.max(...corners.map(p=>p.x))),top=Math.max(0,Math.min(...corners.map(p=>p.y))),bottom=Math.min(this.h,Math.max(...corners.map(p=>p.y)));
   if(right>left&&bottom>top)focusTargetBox={x:left,y:top,width:right-left,height:bottom-top};
  }
  const value={t,scene_id:this.sceneSpec.scene_id,render_mode:'FLAT_MAP_PREMIUM',shot:this.sceneSpec.camera_preset,lighting:this.sceneSpec.lighting_preset,lightingState:{preset:'FLAT_GEOGRAPHY_READABILITY',sunDirection:[-15,24,50],atmosphericHaze:0,cloudOpacity:0},cameraPosition:this.camera.position.toArray(),cameraQuaternion:this.camera.quaternion.toArray(),cameraFov:44,cameraSpanDegrees:this.core.cam.current.span,cameraCoordinateUnits:'projected_degrees_with_cartographic_z',projection:this.core.projection.kind,nextEventPreview:{weight:this.core.cam.current.previewWeight,event_time:this.sceneSpec.flat_map?.next_event?.event_time??null,lead_time:this.sceneSpec.flat_map?.next_event?.lead_time??null},routeProgress:this.core.routes.map(r=>({id:r.id,progress:this.core.routeProgress(r,t)})),routeDisplay:this.core.routes.map(r=>({id:r.id,physical_path_altitude_km:flatNumber(r.spec.altitude_km),overlay_altitude_km:null,display_role:'projected_geographic_surface_overlay'})),routeInsideEarth:false,routeDiscontinuities:this.core.routes.filter(r=>!r.point(this.core.routeProgress(r,t)).toArray().every(Number.isFinite)).map(r=>r.id),entities:entityAudit,entityClipped:entityAudit.filter(e=>e.clipped).map(e=>e.id),missingTextures,textures,countryOutlines:this.countryItems.map(i=>({name:i.name,source:'Natural Earth 1:50m public domain'})),countryHighlights:this.countryItems.filter(i=>i.material.uniforms.uTintOpacity.value>.005).map(i=>({name:i.name,opacity:i.material.uniforms.uTintOpacity.value,terrain_preserved:true})),focusTarget:activeFocus?.target_id||null,focusTargetBox,autoFocus:{strength:this.materials[0].uniforms.uFocusStrength.value,projectedCenter:this.materials[0].uniforms.uFocus.value.toArray(),radiusDegrees:this.materials[0].uniforms.uFocusRadius.value},labels:this.labels,textClipped:this.labels.filter(l=>l.x<0||l.y<0||l.x+l.width>this.w||l.y+l.height>this.h),webglError:this.gl.getContext().getError(),sourceTextureSize:[this.day.image.width,this.day.image.height],fontReady:document.fonts.check("300 100px 'Open Sans'")&&document.fonts.check("400 68px 'Noto Cinema'",'세계 항로 서울'),meaningfulEventsRendered:f.events,atmosphere:'NONE_FOR_GEOGRAPHIC_CLARITY',heroVolumetrics:false,entityScale:'cartographic_visual_proxy',renderResolution:[this.w,this.h],mapDataSource:COUNTRY_URL,surfaceDataSource:DAY_URL,terrainDataSource:this.sceneSpec.flat_map?.terrain_texture?.url||DAY_URL,reliefDataSource:TOPO_URL,reliefScope:'2K material bump and native-resolution terrain landcover raster; no surveyed DEM',cache:{projectedGeometryEntries:assetCache.geometry.size,textures:assetCache.textures.size},motionIntegrationTaps:1};
  value.mapCameraSpan=this.core.cam.current.span;
  value.cameraPositionUnits='projected_degrees';
  value.entityMotionSamples=3;
  value.motionBlurScope='Two weak past-pose samples on moving entities and route heads; geography and text are sharp. No global V3 seven-tap post chain.';
  return transitionAuditVisibility(value,mapTransitionOpacity(this.sceneSpec,t));
 }
 numericPreflight(fps=30){return this.core.numericPreflight(fps);}
}
