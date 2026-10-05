/** Optional v004 presentation of the preserved MASTER V3 Earth renderer.
 * Real sphere geometry, licensed textures, city lights, cloud shells, HDR,
 * atmosphere and temporal motion integration remain owned by the V3 adapter.
 */
import * as THREE from 'three';
import {SceneEarthRenderer} from './earth_adapter.js';
import {incomingGeographicTransition} from './geographic_polish_transition.js';
import {FlatSceneCore,flatCoordinate} from './flat_semantics.js';
import {polishFlatLabels,avoidCityLabelObstacles,flatPolishProjectedAircraftObstacles} from './flat_polish_renderer.js';

export const EARTH_POLISH_VERSION='v004';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)));
const smooth=v=>{v=clamp(v);return v*v*(3-2*v);};

export class SceneEarthPolishRenderer extends SceneEarthRenderer {
 constructor(scene,plan){
  if(scene.visual_polish?.version!==EARTH_POLISH_VERSION)throw Error('EARTH_POLISH_OPT_IN_V004_REQUIRED');
  super(scene,plan);this.polishReady=false;this.geographicHandoff=null;
 }
 async init(){
  await super.init();
  this.geographicHandoff=incomingGeographicTransition(this.sceneSpec,this.plan,this.w/this.h);
  if(this.geographicHandoff){
   const originalUpdate=this.cam.update.bind(this.cam);
   this.cam.update=t=>{const value=originalUpdate(t);this.registeredCameraAt(t);return value;};
  }
  if(this.geographicHandoff){
   const source=this.geographicHandoff.outgoing.flat_map?.terrain_texture;
   if(source){
    if(!Array.isArray(source.bounds)||source.bounds.length!==4)throw Error('V004_TERRAIN_SOURCE_BOUNDS_REQUIRED');
    this.handoffTerrain=await new THREE.TextureLoader().loadAsync(source.url);
    this.handoffTerrain.colorSpace=THREE.SRGBColorSpace;this.handoffTerrain.wrapS=THREE.ClampToEdgeWrapping;this.handoffTerrain.wrapT=THREE.ClampToEdgeWrapping;
   }
  }
  this.installPolishSurface();this.polishReady=true;this.frame(0);return this;
 }
 registeredCameraAt(t){
  const handoff=this.geographicHandoff;if(!handoff||t>=handoff.duration)return;
  const p=smooth(t/handoff.duration),source=handoff.camera,camera=this.camera;
  camera.position.lerpVectors(source.position,camera.position.clone(),p);
  camera.quaternion.slerpQuaternions(source.quaternion,camera.quaternion.clone(),p);
  camera.up.copy(source.up).lerp(camera.up,p).normalize();
  camera.fov=source.fov+(camera.fov-source.fov)*p;
  camera.near=Math.min(.02,Math.max(.00001,(camera.position.length()-1)*.05));
  camera.updateProjectionMatrix();camera.updateMatrixWorld(true);
 }
 installPolishSurface(){
  const material=this.map.surface;
  const original='vec3 readable=day*vec3(.78,.87,.97)*uReadability;';
  if(!material.fragmentShader.includes(original))throw Error('V004_EARTH_READABILITY_SHADER_CONTRACT_CHANGED');
  material.uniforms.uPolishCoast={value:.07};
  material.fragmentShader=material.fragmentShader.replace('uniform float uTime,uReadability,uExposure,uCityGain;','uniform float uTime,uReadability,uExposure,uCityGain,uPolishCoast;').replace(original,`
   // A bounded surface lift respects the existing land mask and relief. It does
   // not brighten the cloud shell or add fog over the useful geography.
   vec3 readable=day*mix(vec3(.62,.79,.94),vec3(.92,1.00,.91),land)*uReadability;
   float coast=abs(texture2D(uTopo,uv+vec2(1./2048.,0.)).r-texture2D(uTopo,uv-vec2(1./2048.,0.)).r)
              +abs(texture2D(uTopo,uv+vec2(0.,1./1024.)).r-texture2D(uTopo,uv-vec2(0.,1./1024.)).r);
   readable+=day*min(coast*1.8,.12)*uPolishCoast;
  `);
  if(this.geographicHandoff){
   const outgoing=this.geographicHandoff.outgoing,terrain=outgoing.flat_map?.terrain_texture;
   const focus=(outgoing.flat_map?.focus||[]).at(-1),p=this.geographicHandoff.warp.projection.point(focus?.coordinates||outgoing.coordinates);
   Object.assign(material.uniforms,{uPolishMaterialBlend:{value:0},uPolishTerrain:{value:this.handoffTerrain||material.uniforms.uDay.value},uPolishTerrainBounds:{value:new THREE.Vector4(...(terrain?.bounds||[-180,-90,180,90]))},uPolishHasTerrain:{value:this.handoffTerrain?1:0},uPolishTerrainTexel:{value:new THREE.Vector2(1/(this.handoffTerrain?.image.width||8192),1/(this.handoffTerrain?.image.height||4096))},uPolishFlatFocus:{value:new THREE.Vector2(p.x,p.y)},uPolishFlatFocusStrength:{value:Math.min(.25,(focus?.strength||0)*1.12)},uPolishFlatFocusRadius:{value:focus?.radius_degrees||5}});
   material.fragmentShader=material.fragmentShader.replace('void main(){',`
uniform sampler2D uPolishTerrain;
uniform vec4 uPolishTerrainBounds;
uniform vec2 uPolishTerrainTexel,uPolishFlatFocus;
uniform float uPolishMaterialBlend,uPolishHasTerrain,uPolishFlatFocusStrength,uPolishFlatFocusRadius;
vec3 polishInverseFilm(vec3 y){vec3 a=2.43*y-2.51,b=.59*y-.03,c=.14*y;return max(vec3(0.),(-b-sqrt(max(b*b-4.*a*c,vec3(0.))))/(2.*a));}
vec3 polishFlatMaterial(vec2 geographicUV,float land){
 vec2 ll=vec2(geographicUV.x*360.-180.,geographicUV.y*180.-90.);
 vec2 terrainUV=(ll-uPolishTerrainBounds.xy)/(uPolishTerrainBounds.zw-uPolishTerrainBounds.xy);
 vec2 texel=vec2(1./8192.,1./4096.);vec3 source=texture2D(uDay,geographicUV).rgb;
 vec3 neighbor=(texture2D(uDay,geographicUV+vec2(texel.x,0.)).rgb+texture2D(uDay,geographicUV-vec2(texel.x,0.)).rgb+texture2D(uDay,geographicUV+vec2(0.,texel.y)).rgb+texture2D(uDay,geographicUV-vec2(0.,texel.y)).rgb)*.25;
 if(uPolishHasTerrain>.5&&terrainUV.x>=0.&&terrainUV.x<=1.&&terrainUV.y>=0.&&terrainUV.y<=1.){
  float edge=min(min(ll.x-uPolishTerrainBounds.x,uPolishTerrainBounds.z-ll.x),min(ll.y-uPolishTerrainBounds.y,uPolishTerrainBounds.w-ll.y));
  float weight=smoothstep(0.,12.,edge);
  vec3 atlas=texture2D(uPolishTerrain,terrainUV).rgb,atlasNeighbor=(texture2D(uPolishTerrain,terrainUV+vec2(uPolishTerrainTexel.x,0.)).rgb+texture2D(uPolishTerrain,terrainUV-vec2(uPolishTerrainTexel.x,0.)).rgb+texture2D(uPolishTerrain,terrainUV+vec2(0.,uPolishTerrainTexel.y)).rgb+texture2D(uPolishTerrain,terrainUV-vec2(0.,uPolishTerrainTexel.y)).rgb)*.25;
  source=mix(source,atlas,weight);neighbor=mix(neighbor,atlasNeighbor,weight);
 }
 source=max(vec3(0.),source+(source-neighbor)*.56);float gray=dot(source,vec3(.2126,.7152,.0722));source=max(vec3(0.),mix(vec3(gray),source,1.40));source=max(vec3(0.),(source-vec3(.24))*1.10+vec3(.24));
 float elevation=texture2D(uTopo,geographicUV).r;vec2 derivative=vec2(texture2D(uTopo,geographicUV+vec2(1./2048.,0.)).r-elevation,texture2D(uTopo,geographicUV+vec2(0.,1./1024.)).r-elevation)*2.;
 float hill=.83+.24*max(0.,dot(normalize(vec3(-derivative*4.2,1.)),normalize(vec3(-.45,.62,1.))));
 vec3 earthColor=source*.60*hill*vec3(1.,1.04,.92)+vec3(.002,.004,.001);
 vec2 map=vec2(ll.x,log(tan(.7853981633974483+clamp(ll.y,-80.,80.)*.0087266462599716))*57.29577951308232);
 vec3 oceanColor=vec3(.0045,.021,.053)*(.94+.035*sin(map.x*.12+map.y*.08));vec3 color=mix(oceanColor,earthColor,land);
 float focus=exp(-pow(length((map-uPolishFlatFocus)/max(.25,uPolishFlatFocusRadius)),2.)*.62);
 float saturation=1.-uPolishFlatFocusStrength*(1.-focus)*.30;
 color=mix(vec3(dot(color,vec3(.2126,.7152,.0722))),color,saturation)*(1.-uPolishFlatFocusStrength*(1.-focus)*.72)*(1.+uPolishFlatFocusStrength*focus*.20);
 // The V3 HDR film transform remains enabled. Its inverse registers the material
 // bridge to the flat renderer's linear terrain color, not a screen crossfade.
 return polishInverseFilm(clamp(color,vec3(0.),vec3(.94)))/1.23;
}
void main(){`);
   const final='gl_FragColor=vec4((diffuse+readable+vec3(1.,.90,.74)*spec+lights)*uExposure,1.);';
   if(!material.fragmentShader.includes(final))throw Error('V004_EARTH_MATERIAL_OUTPUT_CONTRACT_CHANGED');
   material.fragmentShader=material.fragmentShader.replace(final,'vec3 cinema=(diffuse+readable+vec3(1.,.90,.74)*spec+lights)*uExposure;gl_FragColor=vec4(mix(polishFlatMaterial(uv,land),cinema,uPolishMaterialBlend),1.);');
   const atmosphere='color=color*exp(-BETA*viewOD)+scatter+vec3(.002,.006,.014)*(1.-exp(-viewOD*80.));';
   if(!this.postMat.fragmentShader.includes(atmosphere))throw Error('V004_ATMOSPHERE_BLEND_CONTRACT_CHANGED');
   this.postMat.uniforms.uPolishAtmosphere={value:0};
   this.postMat.fragmentShader='uniform float uPolishAtmosphere;\n'+this.postMat.fragmentShader.replace(atmosphere,'color=mix(color,color*exp(-BETA*viewOD)+scatter+vec3(.002,.006,.014)*(1.-exp(-viewOD*80.)),uPolishAtmosphere);');this.postMat.needsUpdate=true;
  }
  material.needsUpdate=true;
 }
 lightingAt(t){
  const value=super.lightingAt(t);
  if(this.sceneSpec.visual_polish?.version!==EARTH_POLISH_VERSION)return value;
  // The initial geography bridge keeps the preceding map readable; the final
  // Earth retains warm night-light detail and a thin physical atmospheric rim.
  const geography=['GEOGRAPHY_READABILITY','DAY_DOCUMENTARY','DISASTER','WAR_SIMULATION'].includes(this.sceneSpec.lighting_preset);
  value.surfaceFill=Math.max(value.surfaceFill,geography?.15:.12);
  value.exposure=Math.max(value.exposure,geography?1.22:1.18);
  value.cloudOpacity=Math.min(value.cloudOpacity,.40);
  if(this.geographicHandoff)value.cloudOpacity*=smooth(t/this.geographicHandoff.duration);
  value.cityGain=Math.max(value.cityGain,1.03);
  return value;
 }
 mapAt(t){
  super.mapAt(t);if(!this.polishReady||!this.geographicHandoff)return;
  const amount=smooth(t/this.geographicHandoff.duration);
  this.map.surface.uniforms.uPolishMaterialBlend.value=amount;this.postMat.uniforms.uPolishAtmosphere.value=amount;
 }
 incomingCityBoxes(){
  if(!this.geographicHandoff)return [];
  if(this.handoffLabelBoxes)return this.handoffLabelBoxes;
  const outgoing=this.geographicHandoff.outgoing;
  const source={...outgoing,transition_out:'camera_continuity',labels:(outgoing.labels||[]).map(l=>({...l,persistent:l.end_time>=outgoing.duration-1e-6?true:l.persistent}))};
  const core=new FlatSceneCore(source,this.plan,{width:this.w,height:this.h,context:this.ctx});
  const lastTime=Math.max(0,outgoing.duration-1/Number(this.plan.fps||30));
  const frame=core.semanticFrame(lastTime),boxes=polishFlatLabels(frame.labels,this.w,this.h,this.ctx,{scene:outgoing});
  const projected=boxes.filter(b=>!b.information).map(b=>{
   const label=source.labels.find(l=>l.text===b.text&&l.coordinates);if(!label)return null;
   const point=this.geographicHandoff.warp.position(core.projection.point(label.coordinates),1),p=point.project(this.geographicHandoff.camera),anchor={x:(p.x*.5+.5)*this.w,y:(.5-p.y*.5)*this.h};
   return {...b,x:clamp(b.x+anchor.x-b.anchor.x,this.w*.09,this.w*.87-b.width),y:clamp(b.y+anchor.y-b.anchor.y,this.h*.13,this.h*.79-b.height),anchor};
  }).filter(Boolean);
  const project=point=>{const p=this.geographicHandoff.warp.position(point,1).project(this.geographicHandoff.camera);return {x:(p.x*.5+.5)*this.w,y:(.5-p.y*.5)*this.h,visible:p.z>=-1&&p.z<=1};};
  const obstacles=flatPolishProjectedAircraftObstacles(outgoing,this.plan,lastTime,this.w,this.h,{project});
  this.handoffLabelBoxes=avoidCityLabelObstacles(projected,obstacles,this.w,this.h);this.handoffObstacles=obstacles;
  return this.handoffLabelBoxes;
 }
 overlay(t){
  if(!this.polishReady)return super.overlay(t);
  this.labels=[];const c=this.ctx,scale=this.w/1080,placed=[];
  const handoff=this.geographicHandoff,blend=handoff?smooth(t/handoff.duration):1,incoming=this.incomingCityBoxes();
  const candidates=[...(this.sceneSpec.labels||[])];
  for(const e of this.sceneSpec.visual_events||[])if(['destination_preview','region_reveal','country_reveal'].includes(String(e.kind).toLowerCase())&&e.coordinates&&e.text)candidates.push({text:e.text,event_id:e.id,kind:'world_label',coordinates:e.coordinates,start_time:e.time,end_time:e.time+1.4,opacity:.96,offset_x:90,offset_y:110});
  for(const label of candidates){
   if(!label.text||!label.coordinates)continue;const start=Number(label.start_time||0),end=Number(label.end_time??this.duration);
   const hold=this.sceneSpec.scene_type==='FINAL_OVERVIEW'&&end>=this.duration-1e-6,fade=Math.min(.4,Math.max(.01,(end-start)/3));
   let opacity=t<start||t>end?0:smooth((t-start)/fade)*(hold?1:1-smooth((t-end+.4)/.4));
   const previous=incoming.find(b=>b.text===label.text),registered=previous&&handoff&&t<handoff.duration;
   if(registered)opacity=Math.max(opacity,previous.opacity*(1-blend));
   if(opacity<.01)continue;const q=flatCoordinate(label.coordinates),point=new THREE.Vector3(Math.cos(q.lat*Math.PI/180)*Math.cos(q.lon*Math.PI/180),Math.sin(q.lat*Math.PI/180),-Math.cos(q.lat*Math.PI/180)*Math.sin(q.lon*Math.PI/180)).multiplyScalar(1+.003*blend),p=this.project(point);
   if(!p.visible||p.x<this.w*.04||p.x>this.w*.96||p.y<this.h*.10||p.y>this.h*.78)continue;
   const font=Math.max(54,Number(label.size||46))*scale,spacing=1.8*scale;c.save();c.font=`400 ${font}px 'Noto Cinema'`;
   const width=c.measureText(label.text).width+Math.max(0,[...label.text].length-1)*spacing;
   let x=clamp(p.x+Number(label.offset_x??100)*scale,this.w*.13+width/2,this.w*.83-width/2)-width/2,y=clamp(p.y+Number(label.offset_y??110)*scale,this.h*.15+font,this.h*.78)-font;
   if(registered){x=previous.x+(x-previous.x)*blend;y=previous.y+(y-previous.y)*blend;}
   let box={text:label.text,event_id:label.event_id||null,kind:label.kind||'world_label',opacity:opacity*Number(label.opacity??.96),x,y,width,height:font*1.25,font,fontFamily:'Noto Cinema',anchor:p,incomingAircraftAvoidance:registered?previous.aircraftAvoidance:null};
   let tries=0;while(placed.some(b=>box.x<b.x+b.width+10*scale&&box.x+box.width>b.x-10*scale&&box.y<b.y+b.height+10*scale&&box.y+box.height>b.y-10*scale)&&tries++<4)box.y+=font*1.3;
   if(box.y+box.height>this.h*.82){c.restore();continue;}
   // A small feathered text shadow supports city names over dense amber lights.
   // It is local to the measured name box, never a map-wide opacity veil.
   c.save();c.translate(box.x+width/2,box.y+font*.65);c.scale((width+30*scale)/(font+20*scale),1);
   const radius=font*.92,shade=c.createRadialGradient(0,0,0,0,0,radius),support=.28*blend;
   shade.addColorStop(0,`rgba(3,12,22,${support})`);shade.addColorStop(.6,`rgba(3,12,22,${support*.7})`);shade.addColorStop(1,'rgba(3,12,22,0)');c.fillStyle=shade;c.fillRect(-radius,-radius,2*radius,2*radius);c.restore();
   c.globalAlpha=box.opacity;c.fillStyle=label.color||'#f3f1e5';c.shadowColor='rgba(6,22,31,.90)';c.shadowBlur=3*scale;c.shadowOffsetY=scale;c.strokeStyle='rgba(7,25,36,.78)';c.lineWidth=1.45*scale;
   let at=box.x;for(const ch of label.text){c.strokeText(ch,at,box.y+font);c.fillText(ch,at,box.y+font);at+=c.measureText(ch).width+spacing;}
   c.restore();this.labels.push(box);placed.push(box);
  }
  this.drawStoryInformation(t);
 }
 audit(t){
  const value=super.audit(t),handoff=this.geographicHandoff;
  value.registeredCameraPosition=this.camera.position.toArray();value.registeredCameraQuaternion=this.camera.quaternion.toArray();value.registeredCameraUnits='normalized_earth_radius';
  value.geographic_anchor_projections=(this.sceneSpec.labels||[]).filter(l=>l.coordinates).map(l=>{const q=flatCoordinate(l.coordinates),n=new THREE.Vector3(Math.cos(q.lat*Math.PI/180)*Math.cos(q.lon*Math.PI/180),Math.sin(q.lat*Math.PI/180),-Math.cos(q.lat*Math.PI/180)*Math.sin(q.lon*Math.PI/180));return {text:l.text,coordinates:l.coordinates,...this.project(n)};});
  value.visualPolish={version:EARTH_POLISH_VERSION,legacyOpaqueVeil:false,surfaceFill:this.currentLighting.surfaceFill,exposure:this.currentLighting.exposure,cloudOpacity:this.currentLighting.cloudOpacity,cityGain:this.currentLighting.cityGain,surfaceGeometry:'preserved_true_sphere',textureSampling:'unchanged_verified_geographic_UV',cityNameSupportMaxOpacity:.28,handoffObstacleScope:'Last actually encoded outgoing pose, reconstructed from source 3D models; not a pixel detection claim'};
  if(handoff)value.projectionTransition={kind:'REGISTERED_GEOMETRIC_TANGENT_TO_SPHERE',curvature:1,veil_opacity:0,phase:'sphere_camera_and_material_settle',settle_progress:smooth(t/handoff.duration),surface_material_blend:this.map.surface.uniforms.uPolishMaterialBlend.value,atmospheric_strength:this.postMat.uniforms.uPolishAtmosphere.value,source_terrain:this.sceneSpec.transition_in==='FLAT_TO_EARTH'?handoff.outgoing.flat_map?.terrain_texture?.url:null,atlas_geographic_edge_feather_degrees:12,anchor:handoff.warp.anchor,registeredCameraPosition:handoff.camera.position.toArray(),registeredCameraQuaternion:handoff.camera.quaternion.toArray(),registeredCameraWidth:handoff.width};
  return value;
 }
}
