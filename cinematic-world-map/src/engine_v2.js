import * as THREE from 'three';
import * as V1 from './core_v1_preserved.js';
const {geo,clamp,smooth,GeodesicCurve}=V1;
const ease=(t,a,b)=>smooth((t-a)/(b-a));
const windowed=(t,a,b,c,d)=>ease(t,a,b)*(1-ease(t,c,d));
export const hubs={
 ICN:{lon:126.4407,lat:37.4602,name:'SEOUL',ko:'서울 · 인천',tag:'ICN',reveal:.65,color:0x9cdee4},
 NRT:{lon:140.3929,lat:35.7719,name:'TOKYO',ko:'도쿄 · 나리타',tag:'NRT',reveal:5.65,color:0xb5e7eb},
 SIN:{lon:103.9915,lat:1.3644,name:'SINGAPORE',ko:'싱가포르 · 창이',tag:'SIN',reveal:15.8,color:0xf0d4a3}
};
export const eventTimeline=[
 [0,'moving globe / opening hit'],[.4,'Seoul pulse / urban wake'],[1.15,'first route'],[1.8,'aircraft departure'],
 [2.75,'eastern destination hint'],[4.4,'flight acceleration / distance'],[5.9,'Tokyo reveal'],[7.1,'Tokyo arrival / settle'],
 [8.4,'network expansion'],[10.15,'Singapore leg reveal'],[12.2,'southbound scale shift'],[14.25,'curved horizon climax'],
 [16.3,'Singapore urban wake'],[17.2,'arrival resolve'],[18.35,'final pull-out'],[19.3,'network / final impact']
];
export const distanceKm=(a,b)=>6371.0088*Math.acos(clamp(geo(a.lon,a.lat).dot(geo(b.lon,b.lat)),-1,1));
const firstDistance=distanceKm(hubs.ICN,hubs.NRT),secondDistance=distanceKm(hubs.NRT,hubs.SIN);

export class SceneManager extends V1.SceneManager{
 constructor(){super();this.events=eventTimeline;this.beats=[
  [0,'ONE DEPARTURE','한 번의 출발, 어디까지 연결될까?'],
  [3.6,'EASTBOUND','첫 번째 연결, 도쿄로.'],
  [6.3,'THE FIRST ARRIVAL','도착은 끝이 아니다.'],
  [8.15,'THE WORLD KEEPS MOVING','하나의 항로가, 네트워크로.'],
  [10.15,'A NEW DIRECTION','다음 연결은, 싱가포르.'],
  [12.2,'ACROSS THE CURVE','지구의 곡면을 따라.'],
  [14.25,'BEYOND THE HORIZON','밤을 가로지르는 항로.'],
  [16.3,'THE NEXT ARRIVAL','싱가포르가 깨어난다.'],
  [18.35,'ONE CONNECTED WORLD','세 도시. 하나의 움직이는 세계.']
 ]}
 story(t){let i=0;while(i<this.beats.length-1&&t>=this.beats[i+1][0])i++;return {index:i,beat:this.beats[i],next:this.beats[i+1]?.[0]??22}}
}

export class CameraController extends V1.CameraController{
 constructor(camera){super(camera);this.keys=[
  [0,134,31,3.15,.18,-.34,-.055],
  [.75,130,36,2.04,.22,-.16,-.025],
  [1.65,127.0,37.8,.96,.14,-.04,.020],
  [2.65,128.3,37.0,.65,.17,-.05,.035],
  [4.1,132.0,37.2,.66,.20,.10,-.030],
  [5.4,137.2,37.4,.78,.25,.02,-.020],
  [6.7,140.4,35.7,.92,.22,-.04,.010],
  [7.55,139.5,36.2,.98,.18,-.04,.005],
  [8.3,135.5,30,1.55,.23,.22,-.020],
  [9.45,130,25,2.15,.14,-.06,-.035],
  [10.3,134,27,1.30,.22,-.15,-.035],
  [11.2,132,25,1.09,.26,-.12,-.025],
  [12.4,126,20.7,.94,.32,.12,.035],
  [13.9,119,12.5,1.12,.62,.12,.050],
  [14.85,114,7.8,1.48,1.10,.10,.035],
  [15.8,109,4.2,1.19,.70,-.18,-.030],
  [16.9,104.8,1.8,.89,.27,-.06,-.020],
  [17.65,104,1.7,1.06,.20,0,.015],
  [18.4,116,18,1.90,.14,.12,.025],
  [19.45,121.5,24.5,3.12,.10,.02,0],
  [20,123,26,3.2,.10,0,0]
 ]}
 follow_entity(routes){this.routes=routes;return this}
 update(t){let [lon,lat,h,tilt,yaw,roll]=this.values(t);let n=geo(lon,lat);
  if(this.routes){const r=this.routes.routes[t<10.15?0:1];const p=this.routes.progress(t,r);
   const weight=.48*(windowed(t,1.8,2.7,6.8,7.55)+windowed(t,10.15,11,16.5,17.2));
   n.lerp(r.curve.getPoint(p).normalize(),weight).normalize()}
  const east=new THREE.Vector3(-n.z,0,n.x).normalize().negate();
  // Longitude increases clockwise in this globe's z convention.
  const north=new THREE.Vector3().crossVectors(n,east).normalize();
  this.camera.position.copy(n.clone().multiplyScalar(1+h).addScaledVector(north,-tilt*h).addScaledVector(east,yaw*h));
  this.camera.up.copy(north.clone().applyAxisAngle(n,roll));this.camera.lookAt(n.clone().multiplyScalar(.96));this.camera.updateMatrixWorld();
  return {lon,lat,h}
 }
}

export class MapRenderer extends V1.MapRenderer{
 async init(){await super.init();const u=this.surfaceMaterial.uniforms;
  u.uFocus={value:geo(hubs.ICN.lon,hubs.ICN.lat)};u.uFocusAmt={value:0};u.uUrban={value:0};
  this.surfaceMaterial.fragmentShader=`precision highp float;
   varying vec3 vP;uniform sampler2D uMap,uTopo,uLights;uniform vec3 uSun,uCamera,uFocus;uniform float uFocusAmt,uUrban;
   void main(){
    vec3 n=normalize(vP);vec2 uv=vec2(atan(-n.z,n.x)/6.2831853+.5,asin(n.y)/3.14159265+.5);
    vec3 tex=texture2D(uMap,uv).rgb;float elev=texture2D(uTopo,uv).r;
    float dx=texture2D(uTopo,uv+vec2(.0005,0.)).r-elev;
    float dy=texture2D(uTopo,uv+vec2(0.,.001)).r-elev;
    vec3 normal=normalize(n+vec3(dx,dy,-dx)*.7);float light=max(dot(normal,uSun),0.);
    float lum=dot(tex,vec3(.23,.65,.12));float land=smoothstep(-.04,.08,max(tex.r,tex.g)-tex.b);
    vec3 ocean=vec3(.0025,.009,.024)+vec3(.003,.013,.025)*lum;
    vec3 earth=mix(vec3(.023,.042,.048),vec3(.20,.245,.18),pow(lum,1.1));
    earth=mix(earth,tex*vec3(.24,.35,.30),.48);
    vec3 base=mix(ocean,earth,land)*(.56+.62*light);
    vec3 view=normalize(uCamera-vP);float ndv=max(dot(view,n),0.);float rim=pow(1.-ndv,3.);
    float focus=exp(-max(1.-dot(n,uFocus),0.)*460.);
    base*=1.-uFocusAmt*.23*(1.-focus);
    vec3 night=texture2D(uLights,uv).rgb;float nl=pow(max(max(night.r,night.g),night.b),1.55);
    base+=vec3(1.,.52,.20)*nl*land*(.24+uUrban*.13+focus*uFocusAmt*.48);
    float spec=pow(max(dot(reflect(-uSun,normal),view),0.),48.)*(1.-land)*.035;
    float relief=clamp((dx+dy)*.12,-.004,.004)*land;
    vec3 color=base+spec+relief+vec3(.012,.040,.073)*rim;
    color=mix(color,vec3(.019,.041,.065),rim*.28);
    vec3 graded=pow(max(color,vec3(0.)),vec3(.454545));
    float dither=(mod(gl_FragCoord.x,2.)+mod(gl_FragCoord.y,2.)*2.-1.5)*.00065;
    gl_FragColor=vec4(graded+dither,1.);
   }`;
  this.surfaceMaterial.needsUpdate=true;
  this.atmosphere.scale.setScalar(1.009);this.atmosphere.material.fragmentShader=this.atmosphere.material.fragmentShader.replace('f*.19','f*.24');this.atmosphere.material.needsUpdate=true;
  const texture=await new THREE.TextureLoader().loadAsync('./assets/v2/cloud-haze.png');texture.wrapS=THREE.RepeatWrapping;
  this.cloud=new THREE.Mesh(new THREE.SphereGeometry(1.0085,128,64),new THREE.ShaderMaterial({
   uniforms:{uCloud:{value:texture},uOpacity:{value:.065},uCam:{value:new THREE.Vector3()}},
   vertexShader:`varying vec3 p;void main(){p=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
   fragmentShader:`varying vec3 p;uniform sampler2D uCloud;uniform float uOpacity;uniform vec3 uCam;
    void main(){vec3 n=normalize(p);vec2 uv=vec2(atan(-n.z,n.x)/6.2831853+.5,asin(n.y)/3.14159265+.5);float a=texture2D(uCloud,uv).r;float rim=pow(1.-max(dot(n,normalize(uCam-p)),0.),2.);gl_FragColor=vec4(.32,.43,.50,a*uOpacity*(.5+rim));}`,
   transparent:true,depthWrite:false,blending:THREE.NormalBlending
  }));this.groups.atmosphere.add(this.cloud);return this
 }
 focus_city(city,strength){this.surfaceMaterial.uniforms.uFocus.value.copy(geo(city.lon,city.lat));this.surfaceMaterial.uniforms.uFocusAmt.value=strength}
 update(camera,t=0){super.update(camera);let city=t<5.2?hubs.ICN:t<13.8?hubs.NRT:hubs.SIN;
  let strength=t<5.2?ease(t,.30,.62)*(1-ease(t,3.8,5.2)):t<13.8?windowed(t,5.2,6.2,9.8,11):ease(t,15.6,16.5);
  this.focus_city(city,strength);this.surfaceMaterial.uniforms.uUrban.value=.8*ease(t,.4,.85)+.2*ease(t,8.4,9.3);
  this.cloud.rotation.y=t*.0015;this.cloud.material.uniforms.uCam.value.copy(camera.position);
  this.cloud.material.uniforms.uOpacity.value=.065+.08*windowed(t,13.3,14.25,15.25,16.1);
 }
}

export class CountryHighlighter extends V1.CountryHighlighter{
 constructor(map){super(map);this.items[0].begin=15.6;this.items[1].begin=.55;this.items[2].begin=5.55}
 update(t){for(const item of this.items){const a=ease(t,item.begin,item.begin+.95);let focus=1-ease(t,item.begin+2.5,item.begin+4);
  item.fill.material.opacity=a*(.04+.075*focus);for(const b of item.borders)b.material.opacity=a*(.20+.38*focus)}
 }
}

export class RouteAnimator{
 constructor(map){this.routes=[
  {a:hubs.ICN,b:hubs.NRT,start:1.15,end:7.1,color:0xabe8ed,lift:.026},
  {a:hubs.NRT,b:hubs.SIN,start:10.15,end:17.2,color:0xe5d4af,lift:.062}
 ];this.group=map.groups.routes;
  for(const r of this.routes){r.curve=new GeodesicCurve(r.a,r.b,r.lift);r.meshes=[];
   for(const [radius,alpha] of [[.00055,.86],[.00145,.065],[.0032,.012]]){
    const material=new THREE.ShaderMaterial({uniforms:{uP:{value:0},uColor:{value:new THREE.Color(r.color)},uAlpha:{value:alpha},uOverview:{value:0}},
     vertexShader:`varying float prog;void main(){prog=uv.x;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
     fragmentShader:`varying float prog;uniform float uP,uAlpha,uOverview;uniform vec3 uColor;void main(){if(prog>uP)discard;float delta=uP-prog;float tail=.24+.76*exp(-delta*14.);tail=mix(tail,.85,uOverview);gl_FragColor=vec4(uColor,uAlpha*tail);}`,
     transparent:true,depthWrite:false,blending:THREE.AdditiveBlending});
    const mesh=new THREE.Mesh(new THREE.TubeGeometry(r.curve,420,radius,6,false),material);r.meshes.push(mesh);this.group.add(mesh)
   }
   r.head=new THREE.Mesh(new THREE.SphereGeometry(.0011,16,12),new THREE.MeshBasicMaterial({color:r.color}));this.group.add(r.head);
   r.particles=[];for(let i=0;i<10;i++){const m=new THREE.Mesh(new THREE.SphereGeometry(.00042,6,4),new THREE.MeshBasicMaterial({color:r.color,transparent:true,opacity:.15,depthWrite:false}));this.group.add(m);r.particles.push(m)}
  }
 }
 progress(t,r){return ease(t,r.start,r.end)}
 animate_route(t){for(const r of this.routes){const p=this.progress(t,r);for(const m of r.meshes){m.visible=t>r.start;m.material.uniforms.uP.value=p;m.material.uniforms.uOverview.value=ease(t,18.35,19.45)}
   r.head.position.copy(r.curve.getPoint(p));r.head.visible=t>r.start&&t<r.end+.15;
   r.particles.forEach((m,i)=>{const q=p-(i+1)*.0045;m.visible=q>0&&t<r.end;m.position.copy(r.curve.getPoint(clamp(q)));m.material.opacity=(1-i/10)*.19})
  }}
 update(t){this.animate_route(t)}
}

export class NetworkAnimator{
 constructor(map){const extra={SHA:{lon:121.47,lat:31.23},HKG:{lon:114.17,lat:22.32},BKK:{lon:100.5,lat:13.76}};
  this.items=[];for(const [a,b,delay] of [[hubs.ICN,extra.SHA,0],[hubs.NRT,extra.HKG,.25],[extra.HKG,extra.BKK,.55]]){
   const curve=new GeodesicCurve(a,b,.025),mat=new THREE.ShaderMaterial({uniforms:{p:{value:0},a:{value:0}},
    vertexShader:`varying float v;void main(){v=uv.x;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`varying float v;uniform float p,a;void main(){if(v>p)discard;gl_FragColor=vec4(.35,.61,.68,a*(.45+.55*exp(-(p-v)*8.)));}`,
    transparent:true,depthWrite:false,blending:THREE.AdditiveBlending});
   const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,200,.0010,4,false),mat);map.groups.routes.add(mesh);this.items.push({mesh,delay})
  }
  this.nodes=[];for(const city of Object.values(extra)){const m=new THREE.Mesh(new THREE.SphereGeometry(.0018,10,8),new THREE.MeshBasicMaterial({color:0xd6bc90,transparent:true,opacity:0,depthWrite:false}));m.position.copy(geo(city.lon,city.lat,1.005));map.groups.effects.add(m);this.nodes.push(m)}
 }
 activate_network(t){let alpha=windowed(t,8.4,9.15,10.3,11.5)*.29+ease(t,18.65,19.6)*.32;
  for(const r of this.items){r.mesh.material.uniforms.a.value=alpha;r.mesh.material.uniforms.p.value=Math.max(ease(t,8.4+r.delay,9.6+r.delay),ease(t,18.65+r.delay*.5,19.7));r.mesh.visible=alpha>.001}
  for(const n of this.nodes)n.material.opacity=alpha*1.5
 }
 update(t){this.activate_network(t)}
}

export class EntityAnimator extends V1.EntityAnimator{
 constructor(map,routes){super(map,routes);this.model.traverse(m=>{if(m.isMesh&&m.material.isMeshStandardMaterial){m.material.roughness=.38;m.material.metalness=.45}})}
 spawn_entity(t){return ease(t,1.75,2.2)*(1-ease(t,17.2,17.6))}
 update(t,camera){const r=this.routes.routes[t<10.15?0:1],p=this.routes.progress(t,r),pos=r.curve.getPoint(p);
  this.model.visible=t>=1.75&&t<17.6&&(t<7.7||t>=10.15);this.model.position.copy(pos);
  let f=r.curve.getPoint(clamp(p+.001)).sub(r.curve.getPoint(clamp(p-.001))).normalize(),up=pos.clone().normalize(),right=new THREE.Vector3().crossVectors(f,up).normalize();up.crossVectors(right,f).normalize();
  this.model.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(right,f,up));
  if(t>7.1&&t<10.15){const next=this.routes.routes[1],f2=next.curve.getPoint(.001).sub(next.curve.getPoint(0)).normalize(),up2=pos.clone().normalize(),right2=new THREE.Vector3().crossVectors(f2,up2).normalize();up2.crossVectors(right2,f2).normalize();const q=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(right2,f2,up2));this.model.quaternion.slerp(q,ease(t,7.3,10.15))}
  this.model.rotateY(Math.sin(p*Math.PI)*.15+Math.sin(t*1.7)*.012);
  const alpha=this.spawn_entity(t)*(1-windowed(t,7.2,7.7,10.15,10.65));
  this.model.userData.alpha=alpha;this.model.traverse(m=>{if(m.isMesh){m.material.transparent=true;m.material.opacity=alpha}});
  const dist=camera.position.distanceTo(pos),hero=windowed(t,13.35,14.3,15.8,16.6);
  this.model.scale.setScalar(dist*.030*(1+hero*.20));
 }
}

export class EffectsEngine{
 constructor(map){this.items=[];const cn=document.createElement('canvas');cn.width=256;cn.height=256;const c=cn.getContext('2d'),grad=c.createRadialGradient(128,128,0,128,128,128);grad.addColorStop(0,'rgba(255,225,169,.8)');grad.addColorStop(.15,'rgba(255,205,136,.28)');grad.addColorStop(.45,'rgba(247,188,123,.09)');grad.addColorStop(1,'rgba(225,167,96,0)');c.fillStyle=grad;c.fillRect(0,0,256,256);const texture=new THREE.CanvasTexture(cn);
  for(const [key,time,pulses] of [['ICN',.4,[.4,1.04]],['NRT',5.9,[5.9,7.1]],['SIN',16.3,[16.3,17.2]]]){
   const city=hubs[key],normal=geo(city.lon,city.lat),g=new THREE.Group();g.position.copy(normal.clone().multiplyScalar(1.005));g.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),normal);map.groups.effects.add(g);
   const halo=new THREE.Mesh(new THREE.PlaneGeometry(.070,.070),new THREE.MeshBasicMaterial({map:texture,transparent:true,opacity:0,depthWrite:false,blending:THREE.AdditiveBlending}));g.add(halo);
   const dot=new THREE.Mesh(new THREE.SphereGeometry(.0018,16,12),new THREE.MeshBasicMaterial({color:city.color,transparent:true,opacity:0}));g.add(dot);
   const rings=[];for(const start of pulses){const ring=new THREE.Mesh(new THREE.RingGeometry(.014,.01465,96),new THREE.MeshBasicMaterial({color:city.color,transparent:true,opacity:0,side:THREE.DoubleSide,depthWrite:false,blending:THREE.AdditiveBlending}));g.add(ring);rings.push({ring,start})}
   this.items.push({city,key,time,halo,dot,rings})
  }
  // A hint is deliberately weaker than the active origin; the name arrives later.
  this.hint=new THREE.Mesh(new THREE.SphereGeometry(.0017,12,8),new THREE.MeshBasicMaterial({color:0xe8d5b4,transparent:true,opacity:0}));this.hint.position.copy(geo(hubs.NRT.lon,hubs.NRT.lat,1.007));map.groups.effects.add(this.hint)
 }
 destination_pulse(t,item){for(const {ring,start} of item.rings){const p=clamp((t-start)/1.3);ring.scale.setScalar(.25+p*3.1);ring.material.opacity=t<start?0:.46*(1-p)**2}}
 update(t){for(const item of this.items){const on=ease(t,item.time,item.time+(item.key==='ICN'?.22:.55));let active=item.key==='ICN'?1-ease(t,3.6,5):item.key==='NRT'?1-ease(t,9.6,11.2):1;
   item.halo.material.opacity=on*(.07+.31*active);item.dot.material.opacity=on*.85;item.dot.scale.setScalar(1+.07*Math.sin(t*2.8));this.destination_pulse(t,item)}
  this.hint.material.opacity=windowed(t,2.75,3.25,5.3,5.95)*(.45+.10*Math.sin(t*3));
 }
}

export class Renderer extends V1.Renderer{
 constructor(){super();for(const g of Object.values(this.map.groups))this.scene.remove(g);this.map=new MapRenderer(this.scene);this.cam=new CameraController(this.camera);this.scenes=new SceneManager();this.textBounds=[];
  this.scene.add(new THREE.DirectionalLight(0x83c9df,.75));this.sun.position.copy(geo(125,45,5))
 }
 async init(){await this.map.init();this.highlight=new CountryHighlighter(this.map);this.routes=new RouteAnimator(this.map);this.cam.follow_entity(this.routes);this.entities=new EntityAnimator(this.map,this.routes);this.effects=new EffectsEngine(this.map);this.network=new NetworkAnimator(this.map);this.makeStars();await document.fonts.ready;return this}
 sceneAt(t){this.cam.update(t);this.map.update(this.camera,t);this.highlight.update(t);this.routes.update(t);this.entities.update(t,this.camera);this.effects.update(t);this.network.update(t);this.gl.render(this.scene,this.camera)}
 text(str,x,y,size,color='#e6edf0',weight=400,spacing=0){super.text(str,x,y,size,color,weight,spacing);const m=this.ctx.measureText(str);this.textBounds.push({text:str,x,y,width:m.width+Math.max(str.length-1,0)*spacing,top:y-(m.actualBoundingBoxAscent||size),bottom:y+(m.actualBoundingBoxDescent||0),alpha:this.ctx.globalAlpha})}
 overlay(t){const c=this.ctx,W=this.w,H=this.h;this.textBounds=[];c.save();
  let vignette=c.createRadialGradient(W*.48,H*.44,W*.30,W*.48,H*.44,H*.64);vignette.addColorStop(0,'rgba(0,0,0,0)');vignette.addColorStop(1,'rgba(0,3,9,.44)');c.fillStyle=vignette;c.fillRect(0,0,W,H);
  const bottom=c.createLinearGradient(0,2650,0,H);bottom.addColorStop(0,'rgba(2,8,15,0)');bottom.addColorStop(.57,'rgba(2,8,15,.83)');bottom.addColorStop(1,'rgba(2,8,15,.96)');c.fillStyle=bottom;c.fillRect(0,2650,W,H-2650);
  this.text('CIVILIAN AIR NETWORK',148,300,30,'#99b1bc',600,3);c.fillStyle='#73bcc8';c.fillRect(148,334,74,3);
  const {index,beat,next}=this.scenes.story(t),alpha=(index===0?1:ease(t,beat[0],beat[0]+.28))*(1-ease(t,next-.18,next));c.globalAlpha=alpha;
  const lift=(1-ease(t,beat[0],beat[0]+.5))*13;
  this.text(beat[1],148,2740+lift,31,t>=18.35?'#d9c7a5':'#9bcad2',600,2.8);
  this.text(beat[2],148,2850+lift,82,'#e5edf0',400);
  let meta;if(t<2.75)meta='SEOUL  /  INCHEON';else if(t<4.4)meta='EASTBOUND  ·  NEXT HUB';else if(t<7.5)meta=`ICN → NRT  ·  ${Math.round(firstDistance).toLocaleString('en-US')} KM`;else if(t<10.15)meta='3 LINKED CORRIDORS';else if(t<18.35)meta=`NRT → SIN  ·  ${Math.round(secondDistance*this.routes.progress(t,this.routes.routes[1])).toLocaleString('en-US')} / ${Math.round(secondDistance).toLocaleString('en-US')} KM`;else meta=`${Math.round(firstDistance+secondDistance).toLocaleString('en-US')} KM  ·  THREE AIR HUBS`;
  this.text(meta,148,2954+lift,56,'#9eb2bd',400,1.5);c.globalAlpha=1;
  const final=ease(t,18.7,19.45);if(final>.001){c.globalAlpha=final;this.text('CONNECTED',148,608,126,'#e6eff1',300,-2);this.text('ONE CONTINUOUS JOURNEY',154,683,30,'#a8bdc7',400,2);c.globalAlpha=1}
  const plane=this.project(this.entities.model.position),planeBounds=this.aircraft_bounds();
  for(const [key,city] of Object.entries(hubs)){let a=ease(t,city.reveal,city.reveal+.7);const past=key==='ICN'?.70*windowed(t,6.8,7.5,18.5,19.4):key==='NRT'?.70*windowed(t,10.5,11.4,18.5,19.4):0;a*=1-past;if(a<.01)continue;const p=this.project(geo(city.lon,city.lat,1.006));if(!p.visible||p.x<100||p.x>W-180||p.y<550||p.y>2630)continue;
   const right=key==='NRT',width=key==='SIN'?490:375;let x=right?p.x+52:p.x-width-54,y=p.y+(key==='ICN'?-90:200)+(1-a)*12;x=clamp(x,148,W-width-240);
   // Keep the 3D aircraft silhouette clear of the city label's painted area.
   if(key==='ICN'&&this.entities.model.visible&&plane.visible&&plane.x>x-30&&plane.x<x+width+35&&Math.abs(plane.y-y)<145)y+=190;
   if(key!=='ICN'&&this.entities.model.visible){const near=smooth((planeBounds.right-x+180)/140)*smooth((x+width+180-planeBounds.left)/140);y+=Math.max(0,planeBounds.bottom+125-y)*near*smooth((this.entities.model.userData.alpha||0)/.18)}
   y=clamp(y,610,2550);c.globalAlpha=a;c.strokeStyle=key==='SIN'?'#c8b58f':'#7cacb6';c.lineWidth=1.5;c.beginPath();c.moveTo(p.x,p.y);c.lineTo(right?x:x+width,y-25);c.stroke();
   const shade=c.createLinearGradient(x-18,0,x+width,0);shade.addColorStop(0,'rgba(3,12,20,.56)');shade.addColorStop(1,'rgba(3,12,20,0)');c.fillStyle=shade;c.fillRect(x-18,y-84,width+30,142);
   this.text(city.name,x,y-22,72,'#e4ebed',600,1.8);this.text(`${city.tag} · ${key==='ICN'?'서울':key==='NRT'?'도쿄':'싱가포르'}`,x,y+38,52,'#a7bac4',400);c.globalAlpha=1
  }
  this.text('FICTIONAL CIVIL LOGISTICS · 20 SECOND STUDY',148,3470,25,'#607e8d',400,1.2);c.restore()
 }
 frame(t,samples=2){return super.frame(t,samples)}
 aircraft_bounds(){let pts=[];for(const x of [-.61,.61])for(const y of [-.75,.75])for(const z of [-.13,.27])pts.push(this.project(new THREE.Vector3(x,y,z).applyMatrix4(this.entities.model.matrixWorld)));return {left:Math.min(...pts.map(p=>p.x)),right:Math.max(...pts.map(p=>p.x)),top:Math.min(...pts.map(p=>p.y)),bottom:Math.max(...pts.map(p=>p.y))}}
 audit(t){const r=this.routes.routes[t<10.15?0:1],p=this.routes.progress(t,r),plane=this.project(this.entities.model.position),texts=this.textBounds.filter(x=>x.alpha>.08);
  const bounds=this.aircraft_bounds();const overlaps=this.entities.model.visible&&(this.entities.model.userData.alpha||0)>.2?texts.filter(s=>s.alpha>.45&&Object.values(hubs).some(h=>s.text===h.name||s.text.startsWith(h.tag+' ·'))&&s.x<bounds.right&&s.x+s.width>bounds.left&&s.top<bounds.bottom&&s.bottom>bounds.top).map(s=>s.text):[];
  return {t,aircraftBounds:bounds,aircraftLabelOverlaps:overlaps,camera:this.camera.position.toArray(),cameraQuaternion:this.camera.quaternion.toArray(),cameraHeight:this.cam.values(t)[2],routeProgress:this.routes.routes.map(r=>this.routes.progress(t,r)),planePosition:this.entities.model.position.toArray(),planeVisible:this.entities.model.visible&&(this.entities.model.userData.alpha||0)>.12,planeScreen:plane,texts,textClipped:texts.filter(x=>x.x<0||x.x+x.width>this.w||x.top<0||x.bottom>this.h).map(x=>x.text),webglError:this.gl.getContext().getError()}
 }
}

const app=await new Renderer().init();window.app=app;window.renderFrame=(t,samples=2)=>{app.frame(t,samples);return true};window.ready=true;app.frame(0,1);
