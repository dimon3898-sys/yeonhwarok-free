import * as THREE from 'three';

// All scene state is a pure function of seconds; no browser clock or random drift.
const TAU=Math.PI*2, DEG=Math.PI/180;
export const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
export const smooth=(v)=>{v=clamp(v);return v*v*(3-2*v)};
const ease=(t,a,b)=>smooth((t-a)/(b-a));
export function geo(lon,lat,r=1){return new THREE.Vector3(Math.cos(lat*DEG)*Math.cos(lon*DEG),Math.sin(lat*DEG),-Math.cos(lat*DEG)*Math.sin(lon*DEG)).multiplyScalar(r)}
const places={SIN:{lon:103.9915,lat:1.3644,name:'SINGAPORE',ko:'싱가포르',tag:'SIN',time:1.4},ICN:{lon:126.4407,lat:37.4602,name:'SEOUL',ko:'서울 · 인천',tag:'ICN',time:7.8},NRT:{lon:140.3929,lat:35.7719,name:'TOKYO',ko:'도쿄 · 나리타',tag:'NRT',time:15.8}};

export class SceneManager{
 constructor(){this.inserts=[];this.events=[0,1.5,2.8,3.7,5.3,7.6,9.1,10.4,12.3,13.5,15.8,17.2,18.6]}
 insert_cinematic_clip({start,end,source}){if(!(end>start))throw Error('Invalid insert interval');this.inserts.push({start,end,source})}
 active(t){return this.inserts.find(x=>t>=x.start&&t<x.end)||null}
 chapter(t){return t<3.7?0:t<9.6?1:t<15.8?2:3}
}

export class CameraController{
 constructor(camera){this.camera=camera;this.keys=[
 [0,115,18,3.05,.10,-.09,-.045],
 [1.5,108,10,1.65,.10,-.02,-.02],
 [3.5,107,9,1.10,.08,.015,.012],
 [4.8,109,10.5,1.04,.09,.02,.015],
 [5.8,114,18.0,.93,.11,.02,.018],
 [7.6,121,32,1.27,.15,-.06,.012],
 [9.6,126,37,1.03,.16,-.09,-.014],
 [11.9,132,36,.81,.23,-.04,-.025],
 [14.3,137,36,.87,.68,.10,-.035],
 [16.2,137,35,1.28,.32,.05,-.014],
 [18,126,26,2.00,.13,-.02,.012],
 [20,123,24,3.1,.07,-.06,.025]]}
 values(t){let i=0;while(i<this.keys.length-2&&t>this.keys[i+1][0])i++;let a=this.keys[i],b=this.keys[i+1],dt=b[0]-a[0],u=clamp((t-a[0])/dt);let vals=[];for(let j=1;j<7;j++){let prev=this.keys[Math.max(0,i-1)],next=this.keys[Math.min(this.keys.length-1,i+2)];let m0=(b[j]-prev[j])/(b[0]-prev[0]),m1=i===this.keys.length-2?0:(next[j]-a[j])/(next[0]-a[0]);vals.push((2*u**3-3*u*u+1)*a[j]+(u**3-2*u*u+u)*dt*m0+(-2*u**3+3*u*u)*b[j]+(u**3-u*u)*dt*m1)}return vals}
 update(t){const [lon,lat,h,tilt,yaw,roll]=this.values(t);let n=geo(lon,lat),east=geo(lon+90,0),north=new THREE.Vector3().crossVectors(n,east).normalize();let target=n.clone().multiplyScalar(.93);this.camera.position.copy(n.clone().multiplyScalar(1+h).addScaledVector(north,-tilt*h).addScaledVector(east,yaw*h));let up=north.clone().applyAxisAngle(n,roll);this.camera.up.copy(up);this.camera.lookAt(target);this.camera.updateMatrixWorld();return {lon,lat,h}}
}

export class MapRenderer{
 constructor(scene){this.scene=scene;this.groups={};for(const key of ['ocean','land','terrain','borders','coastlines','cities','atmosphere','nightLights','selectedCountries','routes','entities','effects']){const g=new THREE.Group();g.name=key;scene.add(g);this.groups[key]=g}}
 async init(){let loader=new THREE.TextureLoader();const [surface,topo,lights,data]=await Promise.all([loader.loadAsync('./assets/gis/earth-blue-marble.jpg'),loader.loadAsync('./assets/gis/earth-topology.png'),loader.loadAsync('./assets/gis/earth-lights.png'),fetch('./assets/gis/countries_50m.geojson').then(r=>r.json())]);
 for(const t of [surface,topo,lights]){t.anisotropy=8;t.wrapS=THREE.RepeatWrapping}
 const mat=new THREE.ShaderMaterial({uniforms:{uMap:{value:surface},uTopo:{value:topo},uLights:{value:lights},uSun:{value:geo(110,25)},uCamera:{value:new THREE.Vector3()}},vertexShader:`varying vec3 vP;void main(){vP=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,fragmentShader:`precision highp float;varying vec3 vP;uniform sampler2D uMap,uTopo,uLights;uniform vec3 uSun,uCamera;
 void main(){vec3 n=normalize(vP);vec2 uv=vec2(atan(-n.z,n.x)/6.2831853+.5,asin(n.y)/3.14159265+.5);vec3 tex=texture2D(uMap,uv).rgb;float elev=texture2D(uTopo,uv).r;float east=texture2D(uTopo,uv+vec2(.0005,0.)).r-elev;float north=texture2D(uTopo,uv+vec2(0.,.001)).r-elev;vec3 norm=normalize(n+vec3(east,north,-east)*.45);float light=max(dot(norm,uSun),0.);float lum=dot(tex,vec3(.23,.65,.12));float land=smoothstep(-.04,.08,max(tex.r,tex.g)-tex.b);vec3 ocean=vec3(.004,.016,.033)+vec3(.006,.012,.020)*lum;vec3 earth=mix(vec3(.045,.078,.083),vec3(.32,.36,.29),pow(lum,1.05));earth=mix(earth,tex*vec3(.48,.58,.52),.43);vec3 base=mix(ocean,earth,land);base*=.56+.65*light;vec3 view=normalize(uCamera-vP);float spec=pow(max(dot(reflect(-uSun,n),view),0.),40.)*(1.-land)*.05;float rim=pow(1.-max(dot(view,n),0.),3.2);vec3 night=texture2D(uLights,uv).rgb;float nl=pow(max(max(night.r,night.g),night.b),2.);base+=vec3(1.,.60,.28)*nl*.14*land;float relief=clamp((east+north)*.09,-.003,.003)*land;base+=relief;vec3 outc=base+spec+vec3(.015,.08,.13)*rim;gl_FragColor=vec4(pow(max(outc,vec3(0.)),vec3(.454545)),1.);}`});
 this.earth=new THREE.Mesh(new THREE.SphereGeometry(1,256,128),mat);this.groups.land.add(this.earth);this.surfaceMaterial=mat;
 const atmosphere=new THREE.Mesh(new THREE.SphereGeometry(1.017,128,96),new THREE.ShaderMaterial({uniforms:{cameraPos:{value:new THREE.Vector3()}},vertexShader:`varying vec3 vP;void main(){vP=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,fragmentShader:`varying vec3 vP;uniform vec3 cameraPos;void main(){vec3 n=normalize(vP);vec3 v=normalize(cameraPos-vP);float f=pow(1.-abs(dot(n,v)),5.);gl_FragColor=vec4(.13,.53,.76,f*.19);}`,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.BackSide}));this.atmosphere=atmosphere;this.groups.atmosphere.add(atmosphere);
 // Separate, real vector administrative borders; all rings use their GIS positions.
 const borderPoints=[];for(const f of data.features){const polys=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates;for(const poly of polys){for(const ring of poly){for(let i=1;i<ring.length;i++){if(Math.abs(ring[i][0]-ring[i-1][0])>180)continue;let a=geo(...ring[i-1],1.00065),b=geo(...ring[i],1.00065);borderPoints.push(a.x,a.y,a.z,b.x,b.y,b.z)}}}}
 const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.Float32BufferAttribute(borderPoints,3));this.groups.borders.add(new THREE.LineSegments(geom,new THREE.LineBasicMaterial({color:0x5c8292,transparent:true,opacity:.23,depthWrite:false})));
 this.features=data.features;
 // Coastline is independently selectable; shared border segments remain in borders.
 this.coastlines=this.groups.coastlines;
 const coastData=await fetch('./assets/gis/coastlines_50m.geojson').then(r=>r.json());let cp=[];for(const f of coastData.features){let lines=f.geometry.type==='LineString'?[f.geometry.coordinates]:f.geometry.coordinates;for(const line of lines){for(let i=1;i<line.length;i++){let a=geo(...line[i-1],1.0008),b=geo(...line[i],1.0008);cp.push(...a.toArray(),...b.toArray())}}}let cg=new THREE.BufferGeometry();cg.setAttribute('position',new THREE.Float32BufferAttribute(cp,3));this.coastlines.add(new THREE.LineSegments(cg,new THREE.LineBasicMaterial({color:0x9eaeb0,transparent:true,opacity:.17,depthWrite:false})));
 // Sparse, geographically located cities, not random lights painted over oceans.
 const cityCoords=[[103.82,1.35],[100.50,13.76],[101.69,3.14],[106.85,-6.21],[106.63,10.82],[121.47,31.23],[116.40,39.90],[114.17,22.32],[126.98,37.57],[139.69,35.68],[135.50,34.69],[121.56,25.03],[120.98,14.60],[113.26,23.13],[108.94,34.34]];
 const pos=[];for(const c of cityCoords){const v=geo(...c,1.001);pos.push(...v.toArray())}
 let pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));this.groups.cities.add(new THREE.Points(pg,new THREE.PointsMaterial({color:0xffcf8c,size:.0022,transparent:true,opacity:.6,depthWrite:false})));
 }
 update(camera){this.surfaceMaterial.uniforms.uCamera.value.copy(camera.position);this.atmosphere.material.uniforms.cameraPos.value.copy(camera.position)}
}

export class CountryHighlighter{
 constructor(map){this.items=[];for(const [name,begin,color] of [['Singapore',1.6,0x71dbdf],['South Korea',7.7,0x78dbe4],['Japan',14.8,0xe3c28a]]){let f=map.features.find(f=>f.properties.ADMIN===name);let polys=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates;
 const positions=[],edges=[];for(const poly of polys){let outer=poly[0];if(outer.length<4)continue;let contour=outer.slice(0,-1).map(c=>new THREE.Vector2(c[0],c[1]));let holes=poly.slice(1).map(r=>r.slice(0,-1).map(c=>new THREE.Vector2(c[0],c[1])));let coords=[...contour,...holes.flat()];let triangles=THREE.ShapeUtils.triangulateShape(contour,holes);for(const tri of triangles){let vv=tri.map(i=>geo(coords[i].x,coords[i].y,1.001));let normal=new THREE.Vector3().crossVectors(vv[1].clone().sub(vv[0]),vv[2].clone().sub(vv[0]));if(normal.dot(vv[0])<0)vv.reverse();vv.forEach(v=>positions.push(...v.toArray()))}for(const ring of poly){let points=ring.map(c=>geo(...c,1.0017));if(points.length>2)edges.push(new THREE.CatmullRomCurve3(points,false,'centripetal',.1))}}
 let geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.computeVertexNormals();let fill=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color,transparent:true,opacity:0,depthWrite:false,side:THREE.DoubleSide}));map.groups.selectedCountries.add(fill);
 let borders=[];for(const curve of edges){let pts=curve.points;const bg=new THREE.BufferGeometry().setFromPoints(pts);let line=new THREE.Line(bg,new THREE.LineBasicMaterial({color,transparent:true,opacity:0,depthWrite:false}));map.groups.selectedCountries.add(line);borders.push(line)}
 this.items.push({fill,borders,begin})}}
 update(t){for(const item of this.items){let fade=ease(t,item.begin,item.begin+1.2);item.fill.material.opacity=.19*fade;item.borders.forEach(x=>x.material.opacity=.67*fade)}}
}

export class GeodesicCurve extends THREE.Curve{
 constructor(a,b,lift){super();this.a=geo(a.lon,a.lat);this.b=geo(b.lon,b.lat);this.angle=Math.acos(clamp(this.a.dot(this.b),-1,1));this.lift=lift}
 getPoint(t,target=new THREE.Vector3()){let q=this.angle;target.copy(this.a).multiplyScalar(Math.sin((1-t)*q)/Math.sin(q)).addScaledVector(this.b,Math.sin(t*q)/Math.sin(q));return target.normalize().multiplyScalar(1.004+Math.sin(Math.PI*t)*this.lift)}
}
export class RouteAnimator{
 constructor(map){this.routes=[{a:places.SIN,b:places.ICN,start:3.7,end:9.15,color:0x81e7e9,lift:.055},{a:places.ICN,b:places.NRT,start:10.4,end:16.05,color:0xf3d9a3,lift:.038}];this.group=map.groups.routes;
 for(const r of this.routes){r.curve=new GeodesicCurve(r.a,r.b,r.lift);r.meshes=[];for(const [radius,alpha] of [[.00065,.83],[.0018,.12],[.004,.025]]){let geometry=new THREE.TubeGeometry(r.curve,360,radius,5,false);const uv=geometry.getAttribute('uv');let material=new THREE.ShaderMaterial({uniforms:{uP:{value:0},uColor:{value:new THREE.Color(r.color)},uAlpha:{value:alpha},uTail:{value:0}},vertexShader:`varying float prog;void main(){prog=uv.x;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,fragmentShader:`varying float prog;uniform float uP,uAlpha,uTail;uniform vec3 uColor;void main(){if(prog>uP)discard;float delta=uP-prog;float base=mix(.21,.70,uTail);float tail=mix(base,1.,exp(-delta*10.));float a=uAlpha*tail;gl_FragColor=vec4(uColor,a);}`,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending});let m=new THREE.Mesh(geometry,material);this.group.add(m);r.meshes.push(m)}
 const bead=new THREE.Mesh(new THREE.SphereGeometry(.0024,16,12),new THREE.MeshBasicMaterial({color:r.color}));this.group.add(bead);r.head=bead;
 r.particles=[];for(let i=0;i<12;i++){let m=new THREE.Mesh(new THREE.SphereGeometry(.00055,6,4),new THREE.MeshBasicMaterial({color:r.color,transparent:true,opacity:.3,depthWrite:false}));this.group.add(m);r.particles.push(m)}
 }}
 progress(t,r){return ease(t,r.start,r.end)}
 update(t){for(const r of this.routes){let p=this.progress(t,r);for(const m of r.meshes){m.visible=t>r.start;m.material.uniforms.uP.value=p;m.material.uniforms.uTail.value=ease(t,17,19)}r.head.visible=t>r.start&&t<r.end+.3;r.head.position.copy(r.curve.getPoint(p));r.particles.forEach((m,i)=>{let v=p-(i+1)*.006;m.visible=v>0&&t<r.end;m.position.copy(r.curve.getPoint(Math.max(v,0)));m.material.opacity=(1-i/12)*.4})}}
}

export class EntityAnimator{
 constructor(map,routes){this.routes=routes;this.model=this.aircraft();map.groups.entities.add(this.model)}
 aircraft(){const g=new THREE.Group();const white=new THREE.MeshStandardMaterial({color:0xd8e5e5,roughness:.3,metalness:.55});const dark=new THREE.MeshStandardMaterial({color:0x203d4c,roughness:.27,metalness:.7});const trim=new THREE.MeshStandardMaterial({color:0x68c5d1,roughness:.3,metalness:.6,emissive:0x12424a,emissiveIntensity:.35});
 const bodyPts=[new THREE.Vector2(.004,-.72),new THREE.Vector2(.05,-.59),new THREE.Vector2(.069,-.3),new THREE.Vector2(.074,.27),new THREE.Vector2(.064,.52),new THREE.Vector2(.035,.66),new THREE.Vector2(.002,.73)];let body=new THREE.Mesh(new THREE.LatheGeometry(bodyPts,24),white);g.add(body);
 const makeWing=(points,mat,z=0)=>{let shape=new THREE.Shape();points.forEach(([x,y],i)=>i?shape.lineTo(x,y):shape.moveTo(x,y));shape.closePath();let mesh=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:.012,bevelEnabled:true,bevelSegments:1,steps:1,bevelSize:.004,bevelThickness:.003}),mat);mesh.position.z=z;g.add(mesh);return mesh};
 makeWing([[-.075,.13],[-.57,-.27],[-.58,-.37],[-.42,-.39],[-.07,-.23],[.07,-.23],[.42,-.39],[.58,-.37],[.57,-.27],[.075,.13]],white,-.012);
 makeWing([[-.025,-.43],[-.24,-.63],[-.25,-.7],[-.06,-.66],[.06,-.66],[.25,-.7],[.24,-.63],[.025,-.43]],white,.02);
 let fin=makeWing([[0,-.37],[.19,-.65],[.17,-.72],[0,-.66]],trim);fin.rotation.y=-Math.PI/2;fin.position.z=.055;
 for(const x of [-.27,.27]){let eng=new THREE.Mesh(new THREE.CylinderGeometry(.046,.041,.20,16),dark);eng.position.set(x,-.13,-.055);g.add(eng);let front=new THREE.Mesh(new THREE.TorusGeometry(.037,.007,6,16),white);front.rotation.x=Math.PI/2;front.position.set(x,-.025,-.055);g.add(front)}
 const cockpit=new THREE.Mesh(new THREE.SphereGeometry(.051,16,8),dark);cockpit.scale.set(1,.9,.28);cockpit.position.set(0,.50,.044);g.add(cockpit);
 for(let i=0;i<11;i++){for(const x of [-.067,.067]){let w=new THREE.Mesh(new THREE.BoxGeometry(.012,.022,.011),dark);w.position.set(x,.34-i*.06,.03);g.add(w)}}
 for(const [x,color] of [[-.57,0xff6860],[.57,0x91e1c1]]){let light=new THREE.Mesh(new THREE.SphereGeometry(.008,8,6),new THREE.MeshBasicMaterial({color}));light.position.set(x,-.30,.013);g.add(light)}
 return g}
 update(t,camera){let r=t<10.4?this.routes.routes[0]:this.routes.routes[1];this.model.visible=t>2.9&&t<16.55;let p=this.routes.progress(t,r);let pos=r.curve.getPoint(p);this.model.position.copy(pos);let forward=r.curve.getPoint(clamp(p+.001)).sub(r.curve.getPoint(clamp(p-.001))).normalize();if(forward.length()<.1)forward=r.b?geo(r.b.lon,r.b.lat).sub(pos).normalize():new THREE.Vector3(0,1,0);let up=pos.clone().normalize();let right=new THREE.Vector3().crossVectors(forward,up).normalize();up.crossVectors(right,forward).normalize();let rot=new THREE.Matrix4().makeBasis(right,forward,up);this.model.quaternion.setFromRotationMatrix(rot);if(t>9.15&&t<10.4){let nr=this.routes.routes[1],f=nr.curve.getPoint(.002).sub(nr.curve.getPoint(0)).normalize(),nu=pos.clone().normalize(),ri=new THREE.Vector3().crossVectors(f,nu).normalize();nu.crossVectors(ri,f).normalize();let q=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(ri,f,nu));this.model.quaternion.slerp(q,ease(t,9.15,10.4))}const bank=Math.sin(p*Math.PI)*.10;const alpha=ease(t,2.9,3.6)*(1-ease(t,16.05,16.55));this.model.traverse(m=>{if(m.isMesh){m.material.transparent=true;m.material.opacity=alpha}});this.model.rotateY(bank);let dist=camera.position.distanceTo(pos);this.model.scale.setScalar(dist*.040*(1+.24*ease(t,12.5,14.2)*(1-ease(t,15.4,16.1))));}
}

export class EffectsEngine{
 constructor(map){this.rings=[];for(const [key,time,col] of [['SIN',2.8,0x84e5e7],['ICN',9.15,0x84e5e7],['NRT',16.05,0xf1d7a8]]){let city=places[key],n=geo(city.lon,city.lat);const container=new THREE.Group();container.position.copy(n.clone().multiplyScalar(1.003));container.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),n);map.groups.effects.add(container);const ring=new THREE.Mesh(new THREE.RingGeometry(.018,.0191,96),new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:0,side:THREE.DoubleSide,depthWrite:false,blending:THREE.AdditiveBlending}));container.add(ring);this.rings.push({ring,time});let dot=new THREE.Mesh(new THREE.SphereGeometry(.0032,16,12),new THREE.MeshBasicMaterial({color:col}));map.groups.effects.add(dot);dot.position.copy(n.clone().multiplyScalar(1.003));dot.userData.time=city.time;this.rings.push({dot,time:city.time})}}
 update(t){for(const r of this.rings){if(r.dot){r.dot.visible=t>r.time;r.dot.scale.setScalar(.8+.14*Math.sin((t-r.time)*3));continue}let q=clamp((t-r.time)/1.6);r.ring.material.opacity=t<r.time?0:.55*(1-q)**2;r.ring.scale.setScalar(.15+q*3.2)}}
}

export class Renderer{
 constructor(){this.w=2160;this.h=3840;this.scene=new THREE.Scene();this.scene.background=new THREE.Color(0x030910);this.camera=new THREE.PerspectiveCamera(42,9/16,.01,30);this.gl=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});this.gl.setSize(this.w,this.h);this.gl.setPixelRatio(1);this.gl.outputColorSpace=THREE.SRGBColorSpace;this.gl.toneMapping=THREE.NoToneMapping;this.canvas=document.createElement('canvas');this.canvas.width=this.w;this.canvas.height=this.h;document.body.append(this.canvas);this.ctx=this.canvas.getContext('2d',{alpha:false});this.accum=document.createElement('canvas');this.accum.width=this.w;this.accum.height=this.h;this.actx=this.accum.getContext('2d',{alpha:false});this.map=new MapRenderer(this.scene);this.cam=new CameraController(this.camera);this.scenes=new SceneManager();this.scene.add(new THREE.HemisphereLight(0xc1e8f6,0x172b36,2.0));this.sun=new THREE.DirectionalLight(0xffe9d1,3.2);this.sun.position.copy(geo(110,35,5));this.scene.add(this.sun)}
 async init(){await this.map.init();this.highlight=new CountryHighlighter(this.map);this.routes=new RouteAnimator(this.map);this.entities=new EntityAnimator(this.map,this.routes);this.effects=new EffectsEngine(this.map);this.makeStars();await document.fonts.ready;return this}
 makeStars(){const pts=[];for(let i=0;i<420;i++){let a=Math.sin(i*12.9898)*43758.5453;let b=Math.sin(i*4.381)*3117.17;let u=a-Math.floor(a),v=b-Math.floor(b);let vec=geo(u*360-180,(v-.5)*140,12);pts.push(...vec.toArray())}let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pts,3));this.scene.add(new THREE.Points(g,new THREE.PointsMaterial({color:0x87a9bb,size:.009,transparent:true,opacity:.30,depthWrite:false})))}
 sceneAt(t){this.cam.update(t);this.map.update(this.camera);this.highlight.update(t);this.routes.update(t);this.entities.update(t,this.camera);this.effects.update(t);this.gl.render(this.scene,this.camera)}
 text(str,x,y,size,color='#e6edf0',weight=400,spacing=0){let c=this.ctx;c.fillStyle=color;c.font=`${weight} ${size}px 'Open Sans', 'Noto Sans CJK KR', sans-serif`;if(!spacing){c.fillText(str,x,y);return}for(const ch of str){c.fillText(ch,x,y);x+=c.measureText(ch).width+spacing}}
 project(p){let v=p.clone().project(this.camera);let pos=p.clone(),n=pos.clone().normalize(),visible=n.dot(this.camera.position.clone().sub(pos))>0;return {x:(v.x*.5+.5)*this.w,y:(.5-v.y*.5)*this.h,visible:visible&&v.z<1}}
 overlay(t){const c=this.ctx,W=this.w,H=this.h;c.save();
 // Filmic vignette, not a rectangular presentation slide.
 let vignette=c.createRadialGradient(W*.48,H*.46,W*.24,W*.48,H*.46,H*.62);vignette.addColorStop(0,'rgba(0,0,0,0)');vignette.addColorStop(1,'rgba(0,3,9,.59)');c.fillStyle=vignette;c.fillRect(0,0,W,H);
 let top=c.createLinearGradient(0,0,0,820);top.addColorStop(0,'rgba(2,8,15,.7)');top.addColorStop(1,'rgba(2,8,15,0)');c.fillStyle=top;c.fillRect(0,0,W,820);
 let bottom=c.createLinearGradient(0,H-900,0,H);bottom.addColorStop(0,'rgba(2,8,15,0)');bottom.addColorStop(.65,'rgba(2,8,15,.83)');bottom.addColorStop(1,'rgba(2,8,15,.96)');c.fillStyle=bottom;c.fillRect(0,H-900,W,900);
 this.text('C I N E M A T I C   A T L A S',148,210,30,'#a3b8c3',600);
 c.fillStyle='#80d2d8';c.fillRect(148,248,80,4);this.text('01  /  CIVILIAN LOGISTICS',256,258,24,'#7795a4',400,2);
 const titleA=1-ease(t,2.5,4);c.globalAlpha=titleA;this.text('THE INVISIBLE',140,450,117,'#e8f0f2',300,-3);this.text('CORRIDOR',140,590,136,'#e8f0f2',600,-3);this.text('보이지 않는 연결, 세계를 움직이다',149,682,37,'#a2b7c2',400);c.globalAlpha=1;
 const finale=ease(t,17.5,19);c.globalAlpha=finale;this.text('ONE CONNECTED',140,450,112,'#e8f0f2',300,-2);this.text('WORLD',140,590,136,'#e8f0f2',600,-3);this.text('5,883 KM  ·  THREE AIR HUBS',149,682,33,'#a2b7c2',400,2);c.globalAlpha=1;
 const chapter=this.scenes.chapter(t);const titles=[['01','THE DEPARTURE','싱가포르에서 시작되는 하나의 연결.'],['02','ACROSS LATITUDES','대륙을 따라, 다음 허브를 향해.'],['03','THE NEXT HORIZON','서울에서 도쿄로. 연결은 계속된다.'],['04','ONE CONNECTED WORLD','세 도시. 하나의 물류 네트워크.']];let active=titles[chapter];let start=[0,3.7,9.6,15.8][chapter];let alpha=ease(t,start,start+.65);c.globalAlpha=alpha;
 this.text(active[0],148,H-950,28,'#7ad6df',600,2);this.text(active[1],230,H-950,30,'#bcd1db',600,3);
 this.text(active[2],148,H-839,86,'#e4eef1',400);
 let meta=t<3.7?'CHANGI  ·  01.36° N / 103.99° E':t<9.6?'SIN → ICN  ·  4,625 KM':t<15.8?'ICN → NRT  ·  1,258 KM':'SIN   /   ICN   /   NRT';this.text(meta,148,H-743,31,'#8ba4b3',400,2);c.globalAlpha=1;
 // Airfield anchors and offset leader labels stay attached to globe coordinates.
 for(const [key,city] of Object.entries(places)){let a=ease(t,city.time,city.time+.75);if(a<.01)continue;let pr=this.project(geo(city.lon,city.lat,1.006));if(!pr.visible||pr.x<100||pr.x>W-140||pr.y<850||pr.y>H-1010)continue;let dir=key==='NRT'?1:-1;let x=pr.x+dir*45,y=pr.y+(key==='ICN'?-80:90);let infoWidth=420;if(dir<0)x-=infoWidth;x=clamp(x,145,W-infoWidth-145);c.globalAlpha=a;c.strokeStyle=key==='NRT'?'#e7c995':'#84d5df';c.lineWidth=2;c.beginPath();c.moveTo(pr.x,pr.y);c.lineTo(pr.x+dir*27,y+10);c.lineTo(dir>0?x+180:x+infoWidth,y+10);c.stroke();let grad=c.createLinearGradient(x-15,0,x+infoWidth,0);grad.addColorStop(0,'rgba(3,12,20,.7)');grad.addColorStop(1,'rgba(3,12,20,0)');c.fillStyle=grad;c.fillRect(x-16,y-60,infoWidth+25,105);this.text(city.name,x,y-18,60,'#e2e8e8',600,2);this.text(`${city.tag}  /  ${city.ko}`,x,y+27,25,'#9bb5c2',400);c.globalAlpha=1}
 // One understated timeline; no game-style panels or invented live telemetry.
 c.fillStyle='#1e3441';c.fillRect(148,H-355,W-296,2);c.fillStyle='#72d1d8';c.fillRect(148,H-355,(W-296)*clamp(t/20),3);this.text('NEUTRAL MOVEMENT SIMULATION',148,H-285,23,'#678593',400,2);this.text('20 SEC  /  MASTER STUDY',W-674,H-285,23,'#678593',400,1);
 c.restore()}
 // A future decoder can provide frame_at(localSeconds) as source; the map
 // camera continues underneath, so returning from the clip resumes its flight.
 drawInsert(t){const slot=this.scenes.active(t);if(!slot)return false;const source=typeof slot.source==='function'?slot.source(t-slot.start):slot.source;const sw=source?.videoWidth||source?.naturalWidth||source?.width,sh=source?.videoHeight||source?.naturalHeight||source?.height;if(!sw||!sh)throw Error('Cinematic insert requires a prepared frame or frame_at callback');const scale=Math.max(this.w/sw,this.h/sh);this.ctx.drawImage(source,(this.w-sw*scale)/2,(this.h-sh*scale)/2,sw*scale,sh*scale);return true}
 frame(t,samples=2){this.actx.globalAlpha=1;for(let s=0;s<samples;s++){const delta=(s/(Math.max(samples-1,1))-.5)/60;this.sceneAt(clamp(t+delta,0,20));this.actx.globalAlpha=1/(s+1);this.actx.drawImage(this.gl.domElement,0,0)}this.ctx.globalAlpha=1;this.ctx.drawImage(this.accum,0,0);this.cam.update(t);if(!this.drawInsert(t))this.overlay(t);return this.canvas}
}

const app=await new Renderer().init();window.app=app;window.renderFrame=(t,samples=2)=>{app.frame(t,samples);return true};window.ready=true;app.frame(0,1);
