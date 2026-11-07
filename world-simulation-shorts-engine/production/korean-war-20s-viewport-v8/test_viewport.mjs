/** Focused regression for the observed moving-camera component defect only. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
const [sourcePath,preparedPath,output]=process.argv.slice(2),source=await readFile(sourcePath,'utf8');
const code=source.slice(source.indexOf('export function presentationAreaViewport('),source.indexOf('\nexport function presentationNativeMapOptions'));
assert(code.startsWith('export function presentationAreaViewport'));
const contains=(p,b,pad=0)=>p[0]>=b[0]+pad&&p[0]<=b[2]-pad&&p[1]>=b[1]+pad&&p[1]<=b[3]-pad;
const viewport=new Function('ok','contains',code.replace('export ','')+';return presentationAreaViewport')((v,c)=>{if(!v)throw Error(c)},contains);
const rect=(x0,y0,x1,y1)=>[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]];
const test=(coords,options={})=>viewport({geometry:{type:'Polygon',coordinates:coords},project:p=>p,safeArea:[48,72,1032,1848],presentation:{mapStyle:{preset:'REFERENCE_FOCUS_V2'}},...options});
let checks=[];
assert.throws(()=>test([rect(1200,100,1300,200)]),/UP2_AREA_SOURCE_OUTSIDE_VIEWPORT/);checks.push('strict_default_still_rejects_offscreen');
assert.equal(test([rect(1200,100,1300,200)],{allowOffscreenComponents:true}).visible,false);checks.push('opt_in_identifies_offscreen_without_geometry_mutation');
test([rect(-100,100,1200,200)]);checks.push('crossing_edge_without_inside_vertices_is_visible');
test([rect(-100,-100,1200,2000)]);checks.push('enclosing_polygon_without_inside_vertices_is_visible');
assert.throws(()=>test([rect(-200,-200,1400,2200),rect(-100,-100,1200,2000)]),/UP2_AREA_SOURCE_OUTSIDE_VIEWPORT/);checks.push('viewport_inside_hole_is_not_filled_land');
assert.throws(()=>test([[[NaN,0],[0,0],[1,1]]],{allowOffscreenComponents:true}),/UP2_AREA_PROJECTED_POINT_REQUIRED/);checks.push('malformed_coordinates_still_rejected');
assert.throws(()=>test([rect(1200,100,1300,200)],{allowOffscreenComponents:true,presentation:{}}),/UP2_AREA_SOURCE_FOOTPRINT_OUTSIDE_SAFE/);checks.push('non_focus_profile_retains_strict_footprint');
const prepared=JSON.parse(await readFile(preparedPath,'utf8'));let culled=[],evaluated=0;
for(const segment of prepared.segments){
 for(let f=0;f<segment.presentationPlan.cpuFrameBounds.length;f++){
  const b=segment.presentationPlan.cpuFrameBounds[f],project=p=>[(p[0]-b[0])/(b[2]-b[0])*1080,(b[3]-p[1])/(b[3]-b[1])*1920];
  for(const stage of segment.scene.time_steps){
   const areas=segment.scene.areas.filter(a=>a.stage_id===stage.id);
   const rows=areas.map(a=>{
    const geometry=segment.scene.geometries.find(g=>g.id===a.geometry_ref);
    assert(geometry);
    const v=viewport({geometry:geometry.geometry,project,safeArea:[48,72,1032,1848],presentation:segment.presentation,allowOffscreenComponents:true});
    return{id:a.id,visible:v.visible!==false};
   });
   assert(rows.some(a=>a.visible),'WHOLE_STATE_OUTSIDE_'+segment.sceneId+'_'+f+'_'+stage.id);
   for(const r of rows)if(!r.visible)culled.push({globalFrame:segment.startFrame+f,state:stage.id,area:r.id});
  }
  evaluated++;
 }
}
assert(culled.some(r=>r.globalFrame===192));
const result={status:'PASS_NEW_VIEWPORT_REGRESSION_ONLY',checks,actualCameraFrames:evaluated,offscreenComponentObservations:culled.length,observedFailedFrame:192,allStatesRetainVisibleGeometry:true,sourceGeometryChanged:false,oldSuitesRerun:0,culled};
await writeFile(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({...result,culled:undefined}));
