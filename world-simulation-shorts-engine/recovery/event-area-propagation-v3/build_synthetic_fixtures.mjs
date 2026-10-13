import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {compileAreaIntent,compileAreaPlan} from '../../web/map_infographic_v1/area_core_v3.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..');
const scene=JSON.parse(await readFile(path.join(engine,'recovery/event-feature-bundle-v2-polish/fixtures/scene.json'),'utf8'));
const camera=JSON.parse(await readFile(path.join(engine,'recovery/v5/inputs/camera-plan.json'),'utf8'));
const origin=scene.event_anchor.coordinates??scene.event_anchor;
const point=(x,y)=>[origin[0]+x,origin[1]+y];
const polygon=offsets=>({type:'Polygon',coordinates:[offsets.map(p=>point(...p))]});
const square=(x,y,size)=>polygon([[x-size,y-size],[x+size,y-size],[x+size,y+size],[x-size,y+size],[x-size,y-size]]);
const source={source_type:'SYNTHETIC_TEST',source_reference:'Authored deterministic topology/motion regression fixture',verification_status:'SYNTHETIC_TEST'};
const area=(id,geometry)=>({id,geometry,role:'EVENT_AREA',style_role:'PRIMARY'});
const nativeFiles={regionalPlan:'recovery/event-feature-bundle-v2-polish/fixtures/REGIONAL-plan.json',
 continentPlan:'recovery/event-feature-bundle-v2-polish/fixtures/CONTINENT-plan.json',scene:'recovery/event-feature-bundle-v2-polish/fixtures/scene.json',
 cameraPlan:'recovery/v5/inputs/camera-plan.json',inputManifest:'recovery/v4/V4-state-records/input-manifest.json'};
const cases=[
 {key:'a',intent:{data_mode:'SYNTHETIC_TEST',source,origin,areas:[area('round',polygon(Array.from({length:33},(_,i)=>{const t=(i%32)/32*Math.PI*2;return [Math.cos(t)*1.3,Math.sin(t)*1.3];})))],
  propagations:[{id:'wave',origin,radius_start_degrees:.1,radius_end_degrees:2}]},
 operations:[{type:'AREA_REVEAL',target_id:'round',start_frame:0,duration_frames:10},{type:'AREA_GROW',target_id:'round',start_frame:0,duration_frames:35},
 {type:'PROPAGATION_RING',target_id:'wave',start_frame:6,duration_frames:65},{type:'AREA_CONTRACT',target_id:'round',start_frame:35,duration_frames:36},
 {type:'AREA_HOLD',start_frame:71,duration_frames:19}]},
 {key:'b',intent:{data_mode:'SYNTHETIC_TEST',source,origin,states:[
  {state_id:'A',time_label:'단계 1',areas:[area('zone',polygon([[-2,-1],[0,-1.2],[1,0],[0,1],[-2,.5],[-2,-1]]))]},
  {state_id:'B',time_label:'단계 2',areas:[area('zone',square(0,0,1.5))]},
  {state_id:'C',time_label:'단계 3',areas:[area('zone',polygon([[-1,-2],[1,-1],[2,1],[0,2],[-1,-2]]))]}]},
 operations:[{type:'AREA_REVEAL',target_id:'zone',start_frame:0,duration_frames:10},
 {type:'STATE_TRANSITION',state_ids:['A','B','C'],start_frame:10,duration_frames:60},{type:'AREA_HOLD',start_frame:70,duration_frames:20}]},
 {key:'c',intent:{data_mode:'SYNTHETIC_TEST',source,origin,areas:[area('mobile',square(-2,1.5,.25))],
 trajectories:[{id:'move',geometry:{type:'LineString',coordinates:[point(-2,1.5),point(-1,2),point(1,1.5)]}}],
 states:[{state_id:'INITIAL',time_label:'DAY 1',areas:[area('control',square(-1,0,1))],fronts:[{id:'front',geometry:{type:'LineString',coordinates:[point(0,-1),point(0,1)]}}]},
 {state_id:'ADVANCE',time_label:'DAY 2',areas:[area('control',polygon([[-2,-1],[1,-1],[1,1],[-2,1],[-2,-1]]))],fronts:[{id:'front',geometry:{type:'LineString',coordinates:[point(1,-1),point(1,1)]}}]},
 {state_id:'HOLD',time_label:'DAY 3',areas:[area('control',square(-.5,0,1.5))],fronts:[{id:'front',geometry:{type:'LineString',coordinates:[point(1,-1.5),point(1,1.5)]}}]}],
 impacts:[area('impact',square(1,0,.5))]},
 operations:[{type:'AREA_REVEAL',target_id:'control',start_frame:0,duration_frames:10},
 {type:'AREA_REVEAL',target_id:'mobile',start_frame:0,duration_frames:10},{type:'FRONT_LINE',target_id:'front',start_frame:5,duration_frames:20},
 {type:'AREA_MOVE',target_id:'mobile',trajectory_id:'move',start_frame:10,duration_frames:45},
 {type:'STATE_TRANSITION',state_ids:['INITIAL','ADVANCE'],start_frame:10,duration_frames:40},
 {type:'TIME_STEP',state_ids:['ADVANCE','HOLD'],start_frame:50,duration_frames:20},
 {type:'IMPACT_ZONE',target_id:'impact',start_frame:55,duration_frames:15},{type:'AREA_HOLD',start_frame:70,duration_frames:20}]}
];
await mkdir(path.join(root,'fixtures'),{recursive:true});
for(const fixture of cases){
 const intent=compileAreaIntent(fixture.intent),areaPlan=compileAreaPlan(intent,{operations:fixture.operations});
 const output={schema:1,key:fixture.key,nativeFiles,areaPlan,presentation:{totalFrames:areaPlan.totalFrames,eventStartFrame:0,
  cameraStartFrame:camera.totalFrames-1,annotations:fixture.key==='c'?intent.states.map(state=>({id:state.state_id,
   display_value:state.time_label,unit:'상태',source,anchor:origin})):[],checkpoints:[]},productionEligible:false};
 await writeFile(path.join(root,'fixtures/synthetic-'+fixture.key+'.json'),JSON.stringify(output,null,2)+'\n');
 console.log(JSON.stringify({key:fixture.key,frames:areaPlan.totalFrames,features:areaPlan.operations.map(op=>op.type)}));
}
