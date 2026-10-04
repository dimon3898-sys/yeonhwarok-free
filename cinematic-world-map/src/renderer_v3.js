import * as THREE from 'three';
import {geo,clamp,smooth} from './core_v1_preserved.js';
import {CameraController,RouteAnimator,EntityAnimator,SceneManager,CITIES,GreatCircleArc} from './engine_v3.js';
const ease=(t,a,b)=>smooth((t-a)/(b-a));
const win=(t,a,b,c,d)=>ease(t,a,b)*(1-ease(t,c,d));
const vertex=`varying vec3 vP;varying vec3 vN;void main(){vP=position;vN=normal;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const surfaceFragment=`
precision highp float;varying vec3 vP,vN;uniform sampler2D uDay,uNight,uTopo,uCloud;uniform vec3 uSun,uMoon,uCamera,uCityA,uCityB,uCityC;uniform float uTime;uniform vec3 uFocus;
vec2 geoUV(vec3 n){return vec2(atan(-n.z,n.x)/6.283185307+.5,asin(clamp(n.y,-1.,1.))/3.141592654+.5);}
void main(){vec3 n=normalize(vP);vec2 uv=geoUV(n);vec3 day=texture2D(uDay,uv).rgb;vec3 night=texture2D(uNight,uv).rgb;
float h=texture2D(uTopo,uv).r;float dx=texture2D(uTopo,uv+vec2(1./2048.,0)).r-h;float dy=texture2D(uTopo,uv+vec2(0,1./1024.)).r-h;
vec3 east=normalize(vec3(-n.z,0.,n.x));vec3 north=normalize(cross(n,east));vec3 normal=normalize(n+east*dx*.12+north*dy*.10);
float nd=dot(normal,uSun);float land=smoothstep(.005,.025,max(day.r,day.g)-day.b*.70);
float cloudDistance=-dot(n,uSun)+sqrt(max(0.,pow(dot(n,uSun),2.)+pow(1.+6./6371.,2.)-1.));vec2 cloudUV=geoUV(normalize(n+uSun*cloudDistance));cloudUV.x-=uTime*.000015;
float cs=pow(texture2D(uCloud,cloudUV).r,1.5)*.54;
vec3 diffuse=day*vec3(.83,.91,1.01)*(max(nd,0.)*1.55*(1.-cs)+.018+max(dot(normal,uMoon),0.)*.055);
vec3 ocean=day*vec3(.48,.69,.97)*(max(nd,0.)*1.10*(1.-cs)+.015+max(dot(normal,uMoon),0.)*.045);diffuse=mix(ocean,diffuse,land);
vec3 view=normalize(uCamera-vP);float spec=pow(max(dot(reflect(-uSun,normal),view),0.),95.)*(1.-land)*max(nd,0.)*.45;
float city=max(night.r-night.b*.52,night.g-night.b*.38);city=pow(max(city-.001,0.),.82);float dark=1.-smoothstep(-.07,.18,dot(n,uSun));
float seoul=exp(-pow(acos(clamp(dot(n,uCityA),-1.,1.))/.023,2.));
float tokyo=exp(-pow(acos(clamp(dot(n,uCityB),-1.,1.))/.034,2.));
float singapore=exp(-pow(acos(clamp(dot(n,uCityC),-1.,1.))/.012,2.));
float focus=1.+seoul*uFocus.x+tokyo*uFocus.y+singapore*uFocus.z;
vec3 lights=vec3(1.,.46,.15)*city*dark*focus*.80;
gl_FragColor=vec4(diffuse+vec3(1.,.90,.74)*spec+lights,1.);
}`;
const cloudFragment=`precision highp float;varying vec3 vP,vN;uniform sampler2D uCloud;uniform vec3 uSun,uMoon;uniform float uTime,uLayer;
vec2 uvOf(vec3 n){return vec2(atan(-n.z,n.x)/6.283185307+.5,asin(clamp(n.y,-1.,1.))/3.141592654+.5);}
void main(){vec3 n=normalize(vP);vec2 uv=uvOf(n);uv.x-=uTime*.000015;float x=texture2D(uCloud,uv).r;float detail=texture2D(uCloud,uv+vec2(.00018,.00010)).r-x;float light=max(dot(normalize(n+vec3(detail,-detail,detail)*.3),uSun),0.);float a=pow(x,1.4+uLayer)*mix(.35,.26,uLayer);if(a<.002)discard;vec3 col=vec3(.77,.85,.98)*(.025+max(dot(n,uMoon),0.)*.20+light*1.55);gl_FragColor=vec4(col,a);}`;
const postVertex=`varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}`;
// Licensed satellite cloud coverage controls this bounded 3D density field.
// The original noise adds cloud thickness only; it never changes geography.
const heroCloudFunctions=`
uniform sampler3D uCloudNoise;uniform sampler2D uVolumeCoverage;uniform float uHero;
float cloudDensity(vec3 p){
 float altitude=(length(p)-1.)*6371.;
 if(altitude<4.5||altitude>11.)return 0.;
 vec3 n=normalize(p);vec2 uv=vec2(atan(-n.z,n.x)/6.283185307+.5,asin(clamp(n.y,-1.,1.))/3.141592654+.5);
 uv.x-=uTime*.000015;
 float coverage=smoothstep(.19,.69,texture2D(uVolumeCoverage,uv).r);
 if(coverage<.015)return 0.;
 float noise=.65*texture(uCloudNoise,p*12.).r+.25*texture(uCloudNoise,p*36.).r+.10*texture(uCloudNoise,p*108.).r;
 float h=(altitude-4.5)/6.5;
 float profile=smoothstep(.0,.20,h)*(1.-smoothstep(.42,1.,h));
 return coverage*profile*smoothstep(.24,.74,noise);
}
vec3 cloudVolume(vec3 color,vec3 ray){
 vec2 shell=hitSphere(uCamera,ray,1.+11./6371.);
 if(shell.y<=0.||shell.x>=shell.y)return color;
 float a=max(shell.x,0.),b=shell.y;
 vec2 inner=hitSphere(uCamera,ray,1.+4.5/6371.);
 if(inner.x>a)b=min(b,inner.x);
 float depth=texture2D(uDepth,vUv).r;
 if(depth<.999999){vec4 q=uInvP*vec4(vUv*2.-1.,depth*2.-1.,1.);b=min(b,length(q.xyz/q.w));}
 if(b<=a)return color;
 float ds=(b-a)/14.,trans=1.;vec3 cloud=vec3(0.);
 // Fixed per-pixel stratification avoids moving speckle during the shot.
 float jitter=fract(sin(dot(floor(vUv*uSize),vec2(12.9898,78.233)))*43758.5453);
 for(int i=0;i<14;i++){
  vec3 p=uCamera+ray*(a+(float(i)+jitter)*ds);float density=cloudDensity(p);
  if(density>.001){
   float sunOD=0.;float shadowStep=min(max(hitSphere(p,uSun,1.+11./6371.).y,0.),40./6371.)/4.;
   for(int j=0;j<4;j++)sunOD+=cloudDensity(p+uSun*(float(j)+.5)*shadowStep)*shadowStep;
   vec2 earth=hitSphere(p,uSun,1.);float daylight=(earth.x>0.&&earth.y>0.)?0.:1.;
   float alpha=1.-exp(-density*ds*1800.*uHero);
   float phase=.8+.35*pow(max(dot(ray,uSun),0.),4.);
   vec3 light=vec3(.009,.016,.028)+vec3(.96,.87,.74)*daylight*exp(-sunOD*1800.)*phase*.90+vec3(.13,.20,.32)*max(dot(normalize(p),uMoon),0.);
   cloud+=trans*alpha*light;trans*=1.-alpha;
  }
 }
 return color*trans+cloud;
}`;
const postFragment=`
precision highp float;varying vec2 vUv;uniform sampler2D uImage,uDepth;uniform mat4 uInvP,uCameraWorld,uPreviousVP,uNextVP;uniform vec3 uCamera,uSun,uMoon;uniform vec2 uSize,uEntityScreen,uEntityMotion;uniform float uTime,uEntityRadius,uEntityVisible;
const float PI=3.14159265359;const float RA=1.0156961;const vec3 BETA=vec3(36.95,86.01,210.88);
vec2 hitSphere(vec3 p,vec3 d,float r){float b=dot(p,d),q=b*b-dot(p,p)+r*r;if(q<0.)return vec2(1e8,-1e8);float a=sqrt(q);return vec2(-b-a,-b+a);}
float density(vec3 p){return exp(clamp((1.-length(p))*796.375,-80.,.0));}
float lightDepth(vec3 p,vec3 light){vec2 earth=hitSphere(p,light,1.);if(earth.x>0.&&earth.y>0.)return 10.;vec2 h=hitSphere(p,light,RA);float ds=max(h.y,0.)/4.;float od=0.;for(int j=0;j<4;j++){vec3 q=p+light*(float(j)+.5)*ds;if(length(q)<1.)return 10.;od+=density(q)*ds;}return od;}
vec3 film(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
void main(){vec4 q=uInvP*vec4(vUv*2.-1.,1.,1.);vec3 dir=normalize((uCameraWorld*vec4(normalize(q.xyz/q.w),0.)).xyz);float z=texture2D(uDepth,vUv).x;vec4 dp0=uInvP*vec4(vUv*2.-1.,z*2.-1.,1.);vec4 wp=uCameraWorld*vec4(dp0.xyz/dp0.w,1.);vec4 prev=uPreviousVP*wp,next=uNextVP*wp;vec2 motion=(next.xy/next.w-prev.xy/prev.w)*.5;float local=uEntityVisible*exp(-dot((vUv-uEntityScreen)*uSize,(vUv-uEntityScreen)*uSize)/max(uEntityRadius*uEntityRadius,1.));motion=mix(motion,uEntityMotion,local);float ml=length(motion*uSize);motion*=min(1.,16.*uSize.x/2160./max(ml,.00001));vec3 color=vec3(0.);float weight=0.;for(int k=0;k<7;k++){float f=float(k)/6.-.5;float w=exp(-f*f*8.);color+=texture2D(uImage,clamp(vUv+motion*f,vec2(0.),vec2(1.))).rgb*w;weight+=w;}color/=weight;
vec2 h=hitSphere(uCamera,dir,RA);if(h.y>0.&&h.x<h.y){float a=max(h.x,0.),b=h.y;vec2 ground=hitSphere(uCamera,dir,1.);if(ground.x>0.&&ground.x<b)b=ground.x;float depth=texture2D(uDepth,vUv).x;if(depth<.999999){vec4 dp=uInvP*vec4(vUv*2.-1.,depth*2.-1.,1.);b=min(b,length(dp.xyz/dp.w));}b=max(a,b);
float ds=(b-a)/12.,viewOD=0.;vec3 scatter=vec3(0.);float mu=dot(dir,uSun),phase=3./(16.*PI)*(1.+mu*mu);
for(int i=0;i<12;i++){vec3 p=uCamera+dir*(a+(float(i)+.5)*ds);float rho=density(p);viewOD+=rho*ds*.5;float sod=lightDepth(p,uSun);vec3 trans=exp(-BETA*(viewOD+sod));scatter+=trans*rho*ds*BETA*phase*6.5*vec3(1.,.97,.93);float mod=lightDepth(p,uMoon);float mm=dot(dir,uMoon);float mp=3./(16.*PI)*(1.+mm*mm);scatter+=exp(-BETA*(viewOD+mod))*rho*ds*BETA*mp*.65*vec3(.78,.86,1.);viewOD+=rho*ds*.5;}
color=color*exp(-BETA*viewOD)+scatter+vec3(.002,.006,.014)*(1.-exp(-viewOD*80.));
}
vec3 bloom=vec3(0.);for(int j=0;j<8;j++){float a=float(j)*.78539816;vec2 delta=vec2(cos(a),sin(a))*3.5/uSize;vec3 c=texture2D(uImage,vUv+delta).rgb;bloom+=max(c-vec3(1.6),vec3(0.));}color+=bloom*.015;
float v=smoothstep(.84,.18,distance(vUv,vec2(.5,.49)));color*=.86+.14*v;
color=film(color*1.23);color=pow(color,vec3(1./2.2));float noise=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233))+uTime*.031)*43758.5453)-.5;color+=noise/600.;gl_FragColor=vec4(color,1.);
}`;

export class EarthRenderer{
 constructor(scene){this.scene=scene;this.groups={};for(const key of ['space','terrain','cityLights','cloud','atmosphere','routes','entities','effects']){this.groups[key]=new THREE.Group();this.groups[key].name=key;scene.add(this.groups[key])}}
 async init(){const loader=new THREE.TextureLoader();const [day,night,cloud,topo]=await Promise.all(['earth-day-8k.jpg','earth-night-8k.jpg','earth-clouds-8k.jpg'].map(n=>loader.loadAsync('./assets/v3/earth/'+n)).concat(loader.loadAsync('./assets/gis/earth-topology.png')));for(const t of [day,night,cloud,topo]){t.wrapS=THREE.RepeatWrapping;t.anisotropy=16}day.colorSpace=THREE.SRGBColorSpace;night.colorSpace=THREE.SRGBColorSpace;
 this.sun=geo(18,-12);this.moon=geo(132,45);this.surface=new THREE.ShaderMaterial({uniforms:{uDay:{value:day},uNight:{value:night},uTopo:{value:topo},uCloud:{value:cloud},uSun:{value:this.sun},uMoon:{value:this.moon},uCamera:{value:new THREE.Vector3()},uTime:{value:0},uFocus:{value:new THREE.Vector3()},uCityA:{value:geo(CITIES.SEOUL.lon,CITIES.SEOUL.lat)},uCityB:{value:geo(CITIES.TOKYO.lon,CITIES.TOKYO.lat)},uCityC:{value:geo(CITIES.SINGAPORE.lon,CITIES.SINGAPORE.lat)}},vertexShader:vertex,fragmentShader:surfaceFragment});
 this.earth=new THREE.Mesh(new THREE.SphereGeometry(1,512,256),this.surface);this.groups.terrain.add(this.earth);
 this.cloudMat=new THREE.ShaderMaterial({uniforms:{uCloud:{value:cloud},uSun:{value:this.sun},uMoon:{value:this.moon},uTime:{value:0},uLayer:{value:0}},vertexShader:vertex,fragmentShader:cloudFragment,transparent:true,depthWrite:false});this.cloud=new THREE.Mesh(new THREE.SphereGeometry(1+4.5/6371,512,256),this.cloudMat);this.groups.cloud.add(this.cloud);this.highCloudMat=this.cloudMat.clone();this.highCloudMat.uniforms.uLayer.value=1;this.highCloud=new THREE.Mesh(new THREE.SphereGeometry(1+7.5/6371,512,256),this.highCloudMat);this.groups.cloud.add(this.highCloud);
 let pts=[],rng=()=>{this.seed=(Math.imul(this.seed,1664525)+1013904223)>>>0;return this.seed/4294967296};this.seed=57191;for(let i=0;i<1100;i++){let p=geo(rng()*360-180,Math.asin(rng()*2-1)*180/Math.PI,16);pts.push(...p.toArray())}let geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.Float32BufferAttribute(pts,3));this.groups.space.add(new THREE.Points(geom,new THREE.PointsMaterial({color:0x566474,size:.007,sizeAttenuation:true,transparent:true,opacity:.25,depthWrite:false})));return this}
 update(t,camera){this.sun.copy(geo(18+5*win(t,12.8,14,15.6,16.7),-12));this.highCloudMat.uniforms.uSun.value.copy(this.sun);this.surface.uniforms.uTime.value=t;this.surface.uniforms.uCamera.value.copy(camera.position);this.cloudMat.uniforms.uTime.value=t;this.highCloudMat.uniforms.uTime.value=t;this.surface.uniforms.uFocus.value.set(1.6*win(t,.35,.8,2,3),1.4*win(t,5.6,6.6,7.7,8.8),1.7*win(t,16,16.8,18,19.3))}
}
export class RouteGraphics{
 constructor(map,routes){this.items=[];this.map=map;this.routes=routes;for(const [i,r] of routes.routes.entries())this.items.push(this.make(r.curve,i,false));this.network=[];for(const [a,b,start] of [[CITIES.TOKYO.airport,{lon:121.805,lat:31.15},8.35],[CITIES.TOKYO.airport,CITIES.SINGAPORE.airport,8.8]]){let arc=new GreatCircleArc(a,b);this.network.push({...this.make(arc,10+this.network.length,true),start})}
 for(const [a,b,start] of [[{lon:121.47,lat:31.23},CITIES.SEOUL.airport,18.7],[{lon:100.50,lat:13.76},CITIES.SINGAPORE.airport,19.0],[{lon:135.50,lat:34.69},CITIES.TOKYO.airport,19.2]])this.network.push({...this.make(new GreatCircleArc(a,b),20+this.network.length,true),start})}
 make(curve,index,faint){const m=new THREE.ShaderMaterial({uniforms:{uProgress:{value:0},uDone:{value:0},uFaint:{value:faint?1:0},uScale:{value:1}},vertexShader:`varying float vProgress;uniform float uScale,uFaint;void main(){vProgress=uv.x;vec3 p=position+normal*mix(.00032,.00018,uFaint)*(uScale-1.);gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.);}`,fragmentShader:`varying float vProgress;uniform float uProgress,uDone,uFaint;void main(){if(vProgress>uProgress)discard;float d=uProgress-vProgress;float tail=.15+.80*exp(-d*13.);float strength=mix(tail,.35,uDone);strength*=mix(1.,.12,uFaint);gl_FragColor=vec4(vec3(.20,.53,.85)*strength*2.7,1.);}`,depthWrite:true});const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,720,faint?.00018:.00032,8,false),m);this.map.groups.routes.add(mesh);let glow=new THREE.Mesh(new THREE.TubeGeometry(curve,720,faint?.00035:.00090,8,false),new THREE.ShaderMaterial({uniforms:m.uniforms,vertexShader:m.vertexShader,fragmentShader:`varying float vProgress;uniform float uProgress,uDone,uFaint;void main(){if(vProgress>uProgress)discard;float d=uProgress-vProgress;float a=(.016+.022*exp(-d*14.))*mix(1.,.15,uFaint);gl_FragColor=vec4(.12,.40,.72,a);}`,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending}));this.map.groups.routes.add(glow);mesh.userData.glow=glow;let head=new THREE.Mesh(new THREE.SphereGeometry(.00045,24,16),new THREE.MeshBasicMaterial({color:new THREE.Color(2.8,4,4.5)}));this.map.groups.routes.add(head);return {curve,mesh,head,mat:m,index,faint}}
 update(t){this.items.forEach((item,i)=>{let r=this.routes.routes[i],p=this.routes.progress(t,r);item.mesh.visible=t>=r.start;item.mesh.userData.glow.visible=item.mesh.visible;item.mat.uniforms.uProgress.value=p;item.mat.uniforms.uDone.value=ease(t,r.end,r.end+.7);item.mat.uniforms.uScale.value=1-.50*win(t,12.8,14,15.6,16.7);item.head.visible=t>=r.start&&t<r.end;item.head.position.copy(r.curve.getPoint(Math.min(1,p+.007)))});for(const n of this.network){let alpha=ease(t,n.start,n.start+1.0)*(n.start<10?1-ease(t,9.5,10.8):1);n.mesh.visible=alpha>.001;n.mesh.userData.glow.visible=n.mesh.visible;n.mat.uniforms.uProgress.value=alpha;n.head.visible=false}}
}
export class EffectsEngine{
 constructor(map){this.map=map;this.items=[];for(const [name,start] of [['SEOUL',.9],['TOKYO',7.1],['SINGAPORE',17.25]]){const city=CITIES[name],group=new THREE.Group(),normal=geo(city.lon,city.lat);group.position.copy(normal.clone().multiplyScalar(1.0003));group.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),normal);map.groups.effects.add(group);const mat=new THREE.ShaderMaterial({uniforms:{uAge:{value:-1}},vertexShader:`varying vec2 vXY;void main(){vXY=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,fragmentShader:`varying vec2 vXY;uniform float uAge;void main(){float q=length(vXY);float r=.002+uAge*.010;float pulse=exp(-pow((q-r)/.00075,2.))*(1.-uAge)*.22;float core=exp(-q*q/.000002)*exp(-uAge*4.)*.65;float a=pulse+core;if(a<.002)discard;gl_FragColor=vec4(vec3(1.,.48,.13)*(pulse+core)*2.0,a);}`,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending});group.add(new THREE.Mesh(new THREE.PlaneGeometry(.032,.032),mat));this.items.push({group,mat,start})}}
 update(t){for(const item of this.items){let age=(t-item.start)/1.4;item.group.visible=age>=0&&age<=1;item.mat.uniforms.uAge.value=age}}
}
export class Renderer{
 constructor(){const query=new URLSearchParams(location.search);this.w=Number(query.get('width')||2160);this.h=Math.round(this.w*16/9);this.scene=new THREE.Scene();this.scene.background=new THREE.Color(.00008,.00015,.0004);this.camera=new THREE.PerspectiveCamera(44,9/16,.00001,30);this.routes=new RouteAnimator();this.cam=new CameraController(this.camera,this.routes);this.scenes=new SceneManager();this.map=new EarthRenderer(this.scene);this.gl=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});this.gl.setSize(this.w,this.h);this.gl.setPixelRatio(1);this.gl.outputColorSpace=THREE.LinearSRGBColorSpace;this.gl.toneMapping=THREE.NoToneMapping;this.target=new THREE.WebGLRenderTarget(this.w,this.h,{type:THREE.HalfFloatType,samples:2});this.target.depthTexture=new THREE.DepthTexture(this.w,this.h,THREE.UnsignedIntType);this.canvas=document.createElement('canvas');this.canvas.width=this.w;this.canvas.height=this.h;document.body.append(this.canvas);this.ctx=this.canvas.getContext('2d',{alpha:false});this.accum=document.createElement('canvas');this.accum.width=this.w;this.accum.height=this.h;this.actx=this.accum.getContext('2d',{alpha:false});this.labels=[]}
 async init(){await this.map.init();this.graphics=new RouteGraphics(this.map,this.routes);this.entities=new EntityAnimator(this.routes);this.map.groups.entities.add(this.entities.model);this.effects=new EffectsEngine(this.map);this.hemi=new THREE.HemisphereLight(0xbbcee2,0x33251b,.75);this.scene.add(this.hemi);let sun=new THREE.DirectionalLight(0xfff1dc,3.1);sun.position.copy(this.map.sun.clone().multiplyScalar(10));this.scene.add(sun);this.sunLight=sun;let moon=new THREE.DirectionalLight(0xbecfe3,.85);moon.position.copy(this.map.moon.clone().multiplyScalar(10));this.scene.add(moon);this.moonLight=moon;this.postMat=new THREE.ShaderMaterial({uniforms:{uImage:{value:this.target.texture},uDepth:{value:this.target.depthTexture},uInvP:{value:this.camera.projectionMatrixInverse},uCameraWorld:{value:this.camera.matrixWorld},uCamera:{value:this.camera.position},uSun:{value:this.map.sun},uMoon:{value:this.map.moon},uSize:{value:new THREE.Vector2(this.w,this.h)},uTime:{value:0},uPreviousVP:{value:new THREE.Matrix4()},uNextVP:{value:new THREE.Matrix4()},uEntityScreen:{value:new THREE.Vector2()},uEntityMotion:{value:new THREE.Vector2()},uEntityRadius:{value:1},uEntityVisible:{value:0}},vertexShader:postVertex,fragmentShader:postFragment,depthWrite:false,depthTest:false});this.postScene=new THREE.Scene();this.postScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.postMat));this.postCam=new THREE.Camera();await document.fonts.load("300 100px 'Open Sans'");await document.fonts.ready;if(!document.fonts.check("300 100px 'Open Sans'"))throw Error("V3 city label font did not load");return this}
 prepareMotionBlur(t){const positions=[];for(const delta of [-1/120,1/120]){let time=clamp(t+delta,0,20);this.cam.update(time);let vp=new THREE.Matrix4().multiplyMatrices(this.camera.projectionMatrix,this.camera.matrixWorldInverse);this.postMat.uniforms[delta<0?'uPreviousVP':'uNextVP'].value.copy(vp);let r=this.routes.active(time),p=this.routes.progress(time,r),v=r.curve.getPoint(p).project(this.camera);positions.push(new THREE.Vector2(v.x*.5+.5,v.y*.5+.5))}this.cam.update(t);this.entities.update(t,this.camera);let v=this.entities.model.position.clone().project(this.camera),screen=new THREE.Vector2(v.x*.5+.5,v.y*.5+.5);this.postMat.uniforms.uEntityScreen.value.copy(screen);this.postMat.uniforms.uEntityMotion.value.copy(positions[1].sub(positions[0]));this.postMat.uniforms.uEntityRadius.value=this.entities.model.scale.x*.9/this.camera.position.distanceTo(this.entities.model.position)*this.h/(2*Math.tan(this.camera.fov*Math.PI/360));this.postMat.uniforms.uEntityVisible.value=this.entities.model.visible?1:0}
 updateAircraftLighting(t){const p=this.entities.model.position,n=p.clone().normalize(),horizon=Math.sqrt(Math.max(0,1-1/p.lengthSq())),hero=win(t,12.8,14,15.6,16.7);const transmission=direction=>smooth((n.dot(direction)+horizon+.00465)/.0093);this.sunLight.position.copy(this.map.sun.clone().multiplyScalar(10));this.sunLight.intensity=3.1*transmission(this.map.sun);this.moonLight.intensity=(.85-.25*hero)*transmission(this.map.moon);this.hemi.intensity=.75-.58*hero;this.hemi.position.copy(n)}
 prepareHeroLighting(t){
  const amount=win(t,12.8,14,15.6,16.7);
  // Leave the reviewed first ten seconds' complete render state untouched.
  if(!this.heroLighting&&amount<=0)return;
  if(!this.heroLighting){
   const materials=new Map(),parts=[];
   this.entities.model.traverse(mesh=>{if(!mesh.isMesh)return;const original=mesh.material;
    if(!materials.has(original)){
     const physical=new THREE.MeshPhysicalMaterial();
     THREE.MeshStandardMaterial.prototype.copy.call(physical,original);
     physical.defines={STANDARD:'',PHYSICAL:''};
     physical.clearcoat=.65;physical.clearcoatRoughness=.14;physical.ior=1.48;
     physical.name=original.name+'_HERO_COATING';materials.set(original,physical);
    }
    parts.push({mesh,original,physical:materials.get(original)});
   });
   const cubeTarget=new THREE.WebGLCubeRenderTarget(128,{type:THREE.HalfFloatType,
    generateMipmaps:true,minFilter:THREE.LinearMipmapLinearFilter});
   const cube=new THREE.CubeCamera(.00015,30,cubeTarget);
   const noiseSize=64,noiseData=new Uint8Array(noiseSize**3);let seed=57391;
   for(let i=0;i<noiseData.length;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;noiseData[i]=seed>>>24;}
   const noise=new THREE.Data3DTexture(noiseData,noiseSize,noiseSize,noiseSize);
   Object.assign(noise,{format:THREE.RedFormat,type:THREE.UnsignedByteType,minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter,wrapS:THREE.RepeatWrapping,wrapT:THREE.RepeatWrapping,wrapR:THREE.RepeatWrapping,unpackAlignment:1});noise.needsUpdate=true;
   const heroPost=new THREE.ShaderMaterial({uniforms:{...this.postMat.uniforms,uHero:{value:0},uCloudNoise:{value:noise},uVolumeCoverage:this.map.cloudMat.uniforms.uCloud},
    glslVersion:THREE.GLSL3,vertexShader:postVertex,
    fragmentShader:'out highp vec4 cloudOutput;\n#define gl_FragColor cloudOutput\n'+postFragment
      .replace('void main(){vec4 q=uInvP',heroCloudFunctions+'\nvoid main(){vec4 q=uInvP')
      .replace('vec2 h=hitSphere(uCamera,dir,RA);','color=cloudVolume(color,dir);vec2 h=hitSphere(uCamera,dir,RA);')
      .replace('phase*6.5*vec3', 'phase*(6.5-3.2*uHero)*vec3')
      .replace('mp*.65*vec3', 'mp*(.65-.45*uHero)*vec3'),depthWrite:false,depthTest:false});
   const shells=[this.map.cloud,this.map.highCloud].map(mesh=>{
    const original=mesh.material;
    const fading=new THREE.ShaderMaterial({uniforms:{...original.uniforms,uShellFade:{value:1}},
     vertexShader:vertex,fragmentShader:cloudFragment
      .replace('uniform float uTime,uLayer;','uniform float uTime,uLayer,uShellFade;')
      .replace('gl_FragColor=vec4(col,a);','gl_FragColor=vec4(col,a*uShellFade);'),
     transparent:true,depthWrite:false});
    return {mesh,original,fading};
   });
   this.heroLighting={parts,cube,cubeTarget,heroPost,shells};
   this.sunLight.shadow.mapSize.set(1024,1024);
   Object.assign(this.sunLight.shadow.camera,{left:-.034,right:.034,top:.034,bottom:-.034,near:.05,far:1});
   this.sunLight.shadow.camera.updateProjectionMatrix();
   this.sunLight.shadow.bias=-.000001;this.sunLight.shadow.normalBias=.000003;
   this.sunLight.shadow.radius=1.5;
   this.moonLight.shadow.mapSize.set(512,512);
   Object.assign(this.moonLight.shadow.camera,{left:-.034,right:.034,top:.034,bottom:-.034,near:.05,far:1});
   this.moonLight.shadow.camera.updateProjectionMatrix();
   this.moonLight.shadow.bias=-.000001;this.moonLight.shadow.normalBias=.000003;
  }
  const hero=this.heroLighting,p=this.entities.model.position;
  hero.heroPost.uniforms.uHero.value=amount;
  this.postScene.children[0].material=amount>0?hero.heroPost:this.postMat;
  for(const {mesh,original,fading} of hero.shells){
   mesh.material=amount>0?fading:original;fading.uniforms.uShellFade.value=1-amount;
   mesh.visible=amount<.999;
  }
  this.gl.shadowMap.enabled=amount>0;this.gl.shadowMap.type=THREE.PCFSoftShadowMap;
  this.sunLight.castShadow=amount>0;
  this.moonLight.castShadow=amount>0;
  if(amount>0){
   this.sunLight.position.copy(p).addScaledVector(this.map.sun,.5);
   this.sunLight.target.position.copy(p);this.sunLight.target.updateMatrixWorld();
   this.moonLight.position.copy(p).addScaledVector(this.map.moon,.5);
   this.moonLight.target.position.copy(p);this.moonLight.target.updateMatrixWorld();
   for(const {mesh,physical} of hero.parts){mesh.material=physical;mesh.castShadow=true;mesh.receiveShadow=true;
    physical.opacity=this.entities.model.userData.alpha;physical.clearcoat=.65*amount;
    physical.envMap=hero.cubeTarget.texture;physical.envMapIntensity=.5*amount;
   }
   this.moonLight.intensity=(.85-.13*amount)*smooth((p.clone().normalize().dot(this.map.moon)+Math.sqrt(Math.max(0,1-1/p.lengthSq()))+.00465)/.0093);
   const visible=this.entities.model.visible;this.entities.model.visible=false;
   const previousTarget=this.gl.getRenderTarget();this.gl.shadowMap.enabled=false;
   for(const {mesh,fading} of hero.shells){mesh.visible=true;fading.uniforms.uShellFade.value=1;}
   hero.cube.position.copy(p);hero.cube.update(this.gl,this.scene);
   for(const {mesh,fading} of hero.shells){mesh.visible=amount<.999;fading.uniforms.uShellFade.value=1-amount;}
   this.gl.shadowMap.enabled=true;this.gl.setRenderTarget(previousTarget);this.entities.model.visible=visible;
  }else{
   for(const {mesh,original} of hero.parts){mesh.material=original;mesh.castShadow=false;mesh.receiveShadow=false;original.opacity=this.entities.model.userData.alpha;}
   this.sunLight.target.position.set(0,0,0);this.sunLight.target.updateMatrixWorld();
   this.moonLight.position.copy(this.map.moon.clone().multiplyScalar(10));
   this.moonLight.target.position.set(0,0,0);this.moonLight.target.updateMatrixWorld();
  }
 }
 sceneAt(t){this.prepareMotionBlur(t);this.map.update(t,this.camera);this.graphics.update(t);this.entities.update(t,this.camera);this.effects.update(t);this.updateAircraftLighting(t);this.prepareHeroLighting(t);this.postMat.uniforms.uTime.value=t;this.gl.setRenderTarget(this.target);this.gl.render(this.scene,this.camera);this.gl.setRenderTarget(null);this.gl.render(this.postScene,this.postCam)}
 project(point){let v=point.clone().project(this.camera);let n=point.clone().normalize(),visible=n.dot(this.camera.position.clone().sub(point))>0;return {x:(v.x*.5+.5)*this.w,y:(.5-v.y*.5)*this.h,visible:visible&&v.z<1}}
 overlay(t){this.labels=[];let c=this.ctx,scale=this.w/1080;const letter=(str,x,y,size,opacity)=>{c.save();c.globalAlpha=opacity;c.fillStyle='#e2e8ed';c.font=`300 ${size*scale}px 'Open Sans','DejaVu Sans',sans-serif`;let spacing=2.7*scale,width=[...str].reduce((s,ch)=>s+c.measureText(ch).width+spacing,0)-spacing;x=clamp(x,this.w*.12+width*.5,this.w*.84-width*.5);c.shadowColor="rgba(0,0,0,.6)";c.shadowBlur=4*scale;c.shadowOffsetY=1.5*scale;let bx=x-width*.5;for(const ch of str){c.fillText(ch,bx,y);bx+=c.measureText(ch).width+spacing}c.restore();this.labels.push({text:str,x:x-width/2,y:y-size*scale,width,height:size*1.2*scale})};for(const [name,start,stop] of [['SEOUL',.75,5.2],['TOKYO',5.7,10.8],['SINGAPORE',16.1,20.5]]){let alpha=Math.max(win(t,start,start+.65,stop-.5,stop),ease(t,18.2,19.2));if(alpha<.01)continue;let city=CITIES[name],p=this.project(geo(city.lon,city.lat,1.004));if(!p.visible||p.x<this.w*.08||p.x>this.w*.92||p.y<this.h*.18||p.y>this.h*.76)continue;let overview=ease(t,18.2,19.2);let x=clamp(p.x+(170*(1-overview)+(name==='SEOUL'?-80:name==='TOKYO'?80:0)*overview)*scale,this.w*.23,this.w*.77),y=p.y+(name==='SEOUL'?140-178*overview:140-88*overview)*scale;letter(name,x,y,50,alpha*.98)}
 if(t>18.6){letter('ONE CONNECTED WORLD',this.w*.5,this.h*.80,23,ease(t,18.6,19.5)*.70)}
 }
 drawInsert(t){const slot=this.scenes.active(t);if(!slot)return false;const source=typeof slot.source==='function'?slot.source(t-slot.start):slot.source;const sw=source?.videoWidth||source?.naturalWidth||source?.width,sh=source?.videoHeight||source?.naturalHeight||source?.height;if(!sw||!sh)throw Error('Cinematic insert requires prepared frame');const s=Math.max(this.w/sw,this.h/sh);this.ctx.drawImage(source,(this.w-sw*s)/2,(this.h-sh*s)/2,sw*s,sh*s);return true}
 frame(t,samples=1){for(let s=0;s<samples;s++){this.sceneAt(clamp(t+(samples>1?(s/(samples-1)-.5)/60:0),0,20));this.actx.globalAlpha=1/(s+1);this.actx.drawImage(this.gl.domElement,0,0)}this.ctx.globalAlpha=1;this.ctx.drawImage(this.accum,0,0);this.cam.update(t);this.entities.update(t,this.camera);if(!this.drawInsert(t))this.overlay(t);return this.canvas}
 audit(t){let aircraft=this.project(this.entities.model.position),p=this.cam.values(t);return {t,shot:this.scenes.shot(t).name,cameraPosition:this.camera.position.toArray(),cameraQuaternion:this.camera.quaternion.toArray(),routeProgress:this.routes.routes.map(r=>this.routes.progress(t,r)),aircraft:{...aircraft,visible:this.entities.model.visible,radius:this.entities.model.position.length()},labels:this.labels,textClipped:this.labels.filter(x=>x.x<0||x.y<0||x.x+x.width>this.w||x.y+x.height>this.h),webglError:this.gl.getContext().getError(),sourceTextureSize:[8192,4096]}}
}
const app=new Renderer();await app.init();window.app=app;window.renderFrame=(t,samples=1)=>app.frame(t,samples);window.ready=true;
