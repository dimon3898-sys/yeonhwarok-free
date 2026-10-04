// V3 camera/geodesy authoring. The V1/V2 renderer and all its files are preserved.
import * as THREE from 'three';
import {createAircraftV3} from './aircraft_v3.js';
import {geo,clamp,smooth,CameraController as CameraBase,GeodesicCurve as CurveBase,EntityAnimator as EntityBase,SceneManager as SceneBase} from './core_v1_preserved.js';
export const CITIES={SEOUL:{lon:126.978,lat:37.5665,airport:{lon:126.4407,lat:37.4602}},TOKYO:{lon:139.6917,lat:35.6895,airport:{lon:140.3929,lat:35.7719}},SINGAPORE:{lon:103.8198,lat:1.3521,airport:{lon:103.9915,lat:1.3644}}};
export const SHOTS=[{start:0,name:'ORBITAL_ESTABLISHING'},{start:.3,name:'ATMOSPHERIC_DIVE'},{start:1.5,name:'CITY_APPROACH'},{start:2.2,name:'ROUTE_CHASE'},{start:4.3,name:'AIRCRAFT_FOLLOW'},{start:7.7,name:'EARTH_ORBIT'},{start:10.2,name:'ROUTE_CHASE'},{start:14,name:'HORIZON_REVEAL'},{start:16.4,name:'CITY_APPROACH'},{start:18.1,name:'GLOBAL_PULLBACK'}];
export class SceneManager extends SceneBase{
 constructor(){super();this.events=[0,.3,.6,.9,1.2,1.5,2.2,3.8,5.6,7.1,8.3,9.65,10.2,12.1,14,15.5,16.5,17.25,18.1,19.2]}
 shot(t){return SHOTS.filter(x=>x.start<=t).at(-1)}
}
export class GreatCircleArc extends CurveBase{
 constructor(a,b){super(a,b,0);this.baseRadius=1+11/6371;this.lift=4/6371}
 getPoint(t,out=new THREE.Vector3()){let q=this.angle;out.copy(this.a).multiplyScalar(Math.sin((1-t)*q)/Math.sin(q)).addScaledVector(this.b,Math.sin(t*q)/Math.sin(q));return out.normalize().multiplyScalar(this.baseRadius+Math.sin(Math.PI*t)*this.lift)}
}
export class RouteAnimator{
 constructor(){this.routes=[{a:CITIES.SEOUL.airport,b:CITIES.TOKYO.airport,start:1.2,end:7.1},{a:CITIES.TOKYO.airport,b:CITIES.SINGAPORE.airport,start:10.2,end:17.25}];for(const r of this.routes)r.curve=new GreatCircleArc(r.a,r.b)}
 progress(t,r){return smooth((t-r.start)/(r.end-r.start))}
 active(t){return this.routes[t<9.65?0:1]}
}
export class CameraController extends CameraBase{
 constructor(camera,routes){super(camera);this.routes=routes;this.keys=[
 [0,119,24,2.35,.55,-.45,-.065],
 [.8,124,34,1.45,.72,-.40,-.06],
 [2.2,130,38,.42,1.40,-.20,-.035],
 [4.5,135,37,.28,1.35,-.15,.015],
 [6.5,139,36,.34,.95,-.12,.035],
 [7.5,140,36,.40,.90,-.10,.025],
 [9,138,31,1.00,.62,-.15,-.015],
 [10.3,132,24,1.22,.45,-.20,-.035],
 [12.2,125,14,.50,1.25,-.35,-.04],
 [14.4,121,18,.16,.90,1.00,-.045],
 [15.6,115,13,.17,.95,1.05,-.025],
 [17.2,104,2,.37,1.05,.60,.02],
 [18.1,107,7,.58,.75,.40,.025],
 [19.2,120,23,2.40,.30,.20,.015],
 [20,123,22,2.70,.26,.10,0]]}
 update(t){let [lon,lat,h,tilt,yaw,roll]=this.values(t);let n=geo(lon,lat);const window=(a,b,c,d)=>smooth((t-a)/(b-a))*(1-smooth((t-c)/(d-c)));const r=this.routes.active(t),p=this.routes.progress(t,r);n.lerp(r.curve.getPoint(p).normalize(),(.58+.26*window(12.8,14,15.6,16.7))*(window(1.5,2.5,6.8,7.6)+window(10.2,11.4,16.5,17.5))).normalize();let east=new THREE.Vector3(-n.z,0,n.x).negate().normalize(),north=new THREE.Vector3().crossVectors(n,east).normalize();this.camera.position.copy(n.clone().multiplyScalar(1+h).addScaledVector(north,-tilt*h).addScaledVector(east,yaw*h));let hero=window(12.8,14,15.6,16.7);let target=n.clone().multiplyScalar(.94+.065*hero);if(hero>0){const at=r.curve.getPoint(p),forward=r.curve.getPoint(clamp(p+.0001)).sub(r.curve.getPoint(clamp(p-.0001))).normalize(),radial=at.clone().normalize(),right=forward.clone().cross(radial).normalize();const chase=at.clone().addScaledVector(radial,.145).addScaledVector(right,-.130).addScaledVector(forward,.095);const aim=at.clone().addScaledVector(forward,.008).addScaledVector(radial,.014);this.camera.position.lerp(chase,hero);target.lerp(aim,hero);n.lerp(radial,hero).normalize();}this.camera.up.copy(n.clone().applyAxisAngle(target.clone().sub(this.camera.position).normalize(),roll));this.camera.lookAt(target);this.camera.near=.02;this.camera.fov=44-2*hero;this.camera.updateProjectionMatrix();this.camera.updateMatrixWorld();return {lon,lat,h,tilt,yaw,roll}}
}
export class EntityAnimator{
 constructor(routes){this.routes=routes;this.model=createAircraftV3();this.model.name='CIVILIAN_AIRCRAFT_V3';this.model.traverse(m=>{if(m.isMesh)m.material.transparent=true})}
 update(t,camera){let r=this.routes.active(t),p=this.routes.progress(t,r),pos=r.curve.getPoint(p),f=r.curve.getPoint(clamp(p+.0001)).sub(r.curve.getPoint(clamp(p-.0001))).normalize(),up=pos.clone().normalize(),right=f.clone().cross(up).normalize();up.crossVectors(right,f).normalize();this.model.position.copy(pos);this.model.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(right,f,up));this.model.rotateY(.13*Math.sin(p*Math.PI)*Math.sin(t*.55));this.model.scale.setScalar(.0075+.0090*smooth((t-12.5)/1.5)*(1-smooth((t-16)/1.5)));let alpha=smooth((t-1.5)/.3)*(1-smooth((t-7.1)/.4))+smooth((t-10.2)/.3)*(1-smooth((t-17.25)/.3));this.model.userData.alpha=alpha;this.model.visible=alpha>.005;this.model.traverse(m=>{if(m.isMesh)m.material.opacity=alpha});this.model.updateMatrixWorld(true);return {progress:p,position:pos.toArray(),visible:this.model.visible}}
}
