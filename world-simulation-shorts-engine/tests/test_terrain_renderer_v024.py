"""Execute native inherited frame/overlay paths with recording Canvas, no GPU."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from copy import deepcopy
from engine.infographic_planner import generate_infographic_qa
from engine import infographic_contract as parent
from engine.bold_infographic import prepare_bold_infographic
from engine.terrain_infographic import prepare_terrain_infographic

ROOT = Path(__file__).resolve().parents[1]

# Reuse the frozen setup only. No protected renderer/test file is rewritten.
# The fixture executes actual parent camera, shader, frame and overlay methods;
# its recording Canvas does not claim captured pixels or physical GPU quality.
NATIVE_TEST = r"""
// Native browser Path2D clipping is recorded here; captured pixels are tested
// by the separate real Canvas harness, never inferred from this fixture.
globalThis.Path2D=class{rect(...bounds){this.bounds=bounds;}};
RecordingContext.prototype.clip=function(path){this.commands.push(['clip',path.bounds]);};
const bold=new Function('SceneInfographicRenderer','SceneProductionInfographicRenderer','createInfographicRenderer','validateInfographicGeometry','prepareInfographicGeometry','projectInfographicGeometry','digestBytes','trustedStaticURL',strip('web/bold_infographic_adapter.js')+';return {createBoldInfographicRenderer,validateBoldSelection,withoutLegacyCountryDraw};')(infographic.SceneInfographicRenderer,infographic.SceneProductionInfographicRenderer,infographic.createInfographicRenderer,infographic.validateInfographicGeometry,infographic.prepareInfographicGeometry,infographic.projectInfographicGeometry,quality.digestBytes,quality.trustedStaticURL);
const terrain=new Function('THREE','SceneInfographicRenderer','SceneProductionInfographicRenderer','prepareInfographicGeometry','projectInfographicGeometry','validateBoldSelection','withoutLegacyCountryDraw','createBoldInfographicRenderer','digestBytes','trustedStaticURL',strip('web/terrain_infographic_adapter.js')+';return {createTerrainInfographicRenderer,validateTerrainProfile,validateTerrainSelection,terrainRegionStyle,drawTerrainRegionLayer,prepareTerrainInfographicGeometry,withTerrainContrast,mergeTerrainFillPaths,traceTerrainFillPath};')(THREE,infographic.SceneInfographicRenderer,infographic.SceneProductionInfographicRenderer,infographic.prepareInfographicGeometry,infographic.projectInfographicGeometry,bold.validateBoldSelection,bold.withoutLegacyCountryDraw,bold.createBoldInfographicRenderer,quality.digestBytes,quality.trustedStaticURL);
buffers['/static/infographic/v023/bold_profile.json']=fs.readFileSync(path.join(root,'web/infographic/v023/bold_profile.json'));
buffers['/static/infographic/v024/terrain_profile.json']=fs.readFileSync(path.join(root,'web/infographic/v024/terrain_profile.json'));
try{
 const original=JSON.stringify(inputScene),baseline=structuredClone(inputScene);delete baseline.terrain_infographic;
 const legacy=bold.createBoldInfographicRenderer(baseline,plan);await legacy.init();const baselineRequests=requests.splice(0);
 const off=terrain.createTerrainInfographicRenderer(baseline,plan);await off.init();const offRequests=requests.splice(0);
 const on=terrain.createTerrainInfographicRenderer(inputScene,plan);await on.init();const onRequests=requests.splice(0);
 const selection=inputScene.bold_infographic,fps=String(selection.fps).includes('/')?Number(selection.fps.split('/')[0])/Number(selection.fps.split('/')[1]):Number(selection.fps),total=selection.total_frames;
 assert.equal(off.constructor,legacy.constructor);assertRequestInventory(offRequests,baselineRequests);
 const previousAssets=baselineRequests.filter(url=>url!=='/static/infographic/v023/bold_profile.json');
 assertRequestInventory(onRequests.filter(url=>url!=='/static/infographic/v024/terrain_profile.json'),previousAssets);
 assert.equal(onRequests.filter(url=>url==='/static/infographic/v024/terrain_profile.json').length,1);
 assert.equal(onRequests.filter(url=>url==='/static/infographic/v023/bold_profile.json').length,0);
 for(const prepared of on.terrainPrepared.values())if(prepared.fill_tessellation){assert.equal(prepared.fill_tessellation.method,'SHARED_INDEXED_SPHERICAL_EDGE_REFINEMENT');const old=infographic.prepareInfographicGeometry(prepared.record);assert.deepEqual(prepared.lines.map(line=>line.map(point=>point.toArray())),old.lines.map(line=>line.map(point=>point.toArray())));for(const[a,b,c]of prepared.triangles)assert(Math.max(a.angleTo(b),b.angleTo(c),c.angleTo(a))<=6*Math.PI/180+1e-10);}
 const materialValue=value=>value?.isTexture?{image:value.image,colorSpace:value.colorSpace,wrapS:value.wrapS,wrapT:value.wrapT,minFilter:value.minFilter,magFilter:value.magFilter,anisotropy:value.anisotropy,generateMipmaps:value.generateMipmaps}:value?.toArray?value.toArray():value;
 const coverage={},trajectory=[],regions=[];let primary=0,secondary=0,suppressed=0;
 for(let frame=0;frame<total;frame++){
  const t=frame/fps;for(const renderer of [legacy,off,on]){renderer.ctx.reset();renderer.actx.reset();renderer.frame(t);}
  assert.deepEqual(off.ctx.commands,legacy.ctx.commands);assert.deepEqual(off.actx.commands,legacy.actx.commands);
  for(const renderer of [off,on]){
   assert.deepEqual(renderer.camera.position.toArray(),legacy.camera.position.toArray());assert.deepEqual(renderer.camera.quaternion.toArray(),legacy.camera.quaternion.toArray());assert.equal(renderer.camera.fov,legacy.camera.fov);assert.deepEqual(renderer.cam.values(t),legacy.cam.values(t));assert.equal(renderer.shaderTime,legacy.shaderTime);
   assert.equal(renderer.map.surface.fragmentShader,legacy.map.surface.fragmentShader);assert.deepEqual(Object.keys(renderer.map.surface.uniforms),Object.keys(legacy.map.surface.uniforms));
   for(const [name,uniform]of Object.entries(renderer.map.surface.uniforms))assert.deepEqual(materialValue(uniform.value),materialValue(legacy.map.surface.uniforms[name].value));
  }
  assert.deepEqual(on.actx.commands,legacy.actx.commands);assert.equal(JSON.stringify(inputScene),original);assert.equal(on.ctx.stack.length,0);
  const before=legacy.audit(t),after=on.audit(t),receipt=after.infographic,child=after.terrain_infographic;
  assert.deepEqual(receipt.labels,before.infographic.labels);assert.deepEqual(receipt.markers,before.infographic.markers);assert.deepEqual(receipt.layout,before.infographic.layout);
  assert.deepEqual(on.ctx.commands.filter(command=>['fillText','strokeText'].includes(command[0])),legacy.ctx.commands.filter(command=>['fillText','strokeText'].includes(command[0])));
  assert.equal(receipt.primary_motion_effect_count,before.infographic.primary_motion_effect_count);
  assert.equal(child.version,'v024');assert.equal(child.frame,frame);assert.equal(child.added_texture_uploads,0);assert.equal(child.added_routes,0);assert.equal(child.added_entities,0);assert.equal(child.added_sfx,0);
  assert.equal(child.contrast.text_outline_px_1080,on.terrainProfile.contrast.text_outline_px);assert.equal(child.contrast.text_glyph_strokes,on.ctx.commands.filter(command=>command[0]==='strokeText').length);for(const edge of child.contrast.marker_edges){assert(edge.width_px_1080>3);assert(edge.width_px_1080<=5.5);assert(edge.width_px_1080*on.w/1080<=edge.radius*.4+1e-10);assert.equal(edge.inside_original_box,true);const native=receipt.markers.find(marker=>marker.visible&&Math.abs(marker.box.x-edge.clip_box.x)<1e-7);assert(native);for(const key of['x','y','width','height'])assert(Math.abs(native.box[key]-edge.clip_box[key])<1e-7);}
  assert(!after.bold_infographic);assert.equal(child.pixel_quality,'NOT_ASSESSED_BY_OVERLAY_AUDIT');
  for(const geometry of receipt.geometry){
   const old=before.infographic.geometry.find(value=>value.geometry_id===geometry.geometry_id);assert(old);
   for(const name of ['state','state_before','state_after','transition','event_id','visible','bounds','geometry_id','source_sha256'])assert.deepEqual(geometry[name],old[name]);
   if(geometry.visual_profile){assert.equal(geometry.visual_profile,'VISUAL_TARGET_MAP_V024');assert.equal(geometry.blend_mode,'color');assert.equal(geometry.fill_mode,'NATIVE_COLORIZED_TERRAIN');assert.equal(geometry.drawn_by,'COLORIZED_NATIVE_TERRAIN_LAYER');assert.equal(geometry.legacy_draw_suppressed,true);}
   else assert.deepEqual(geometry,old);
  }
  for(const region of child.regions){coverage[region.id]=(coverage[region.id]||0)+1;assert.equal(region.source_sha256,on.terrainPrepared.get(region.geometry_id).record.sha256);assert.equal(region.blend_mode,'color');assert.equal(region.luminance_scale,region.polygon_count?on.terrainProfile.geometry[region.role].luminance_scale:1);assert.equal(region.luminance_operation,region.polygon_count&&region.luminance_scale<1?'NATIVE_POLYGON_NEUTRAL_MULTIPLY':'NONE');if(region.polygon_count){assert.equal(region.fill_path.method,'PAIRED_PROJECTED_MESH_EDGE_UNION');assert.equal(region.fill_path.closed,true);assert.equal(region.fill_path.branched,false);assert.equal(region.fill_path.endpoint_key_precision_px,1e-7);assert(region.fill_path.maximum_endpoint_identification_delta_px<=1.5e-7);}if(region.polygon_count&&region.luminance_scale<1){assert(region.multiply_color);assert(region.multiply_gray_factor>=.79&&region.multiply_gray_factor<=1);}if(region.role==='SECONDARY'){assert.equal(region.glow_drawn,false);assert.equal(region.glow_alpha,0);}if(region.visible){if(region.role==='PRIMARY')primary++;else secondary++;}}
  assert(child.primary_regions<=1);suppressed+=child.legacy_country_draw_groups_suppressed;
  trajectory.push({frame,position:on.camera.position.toArray(),quaternion:on.camera.quaternion.toArray(),FOV:on.camera.fov,target:on.cam.values(t)});
  if(child.regions.length)regions.push(structuredClone(child));
 }
 assert.equal(trajectory.length,total);assert(primary>0);assert(secondary>0);assert(suppressed>0);for(const region of selection.regions)assert.equal(coverage[region.id],region.end_frame-region.start_frame);
 const profile=JSON.parse(buffers['/static/infographic/v024/terrain_profile.json']),inverted=structuredClone(profile);inverted.geometry.SECONDARY.fill_alpha=1;assert.throws(()=>terrain.validateTerrainProfile(inverted),/HIERARCHY/);
 const glow=structuredClone(profile);glow.geometry.SECONDARY.glow_alpha=.1;assert.throws(()=>terrain.validateTerrainProfile(glow),/BOUNDED_PRIMARY_GLOW/);
 const changed=structuredClone(inputScene);changed.terrain_infographic.parent_camera_sha256='0'.repeat(64);assert.throws(()=>terrain.validateTerrainSelection(changed),/SOURCE/);
 const invalidTone=structuredClone(profile);invalidTone.geometry.PRIMARY.luminance_scale=.79;assert.throws(()=>terrain.validateTerrainProfile(invalidTone),/STYLE_INVALID/);
 const badContrast=structuredClone(profile);badContrast.contrast.font_size=100;assert.throws(()=>terrain.validateTerrainProfile(badContrast),/CONTRAST_PROFILE_INVALID/);const escapedContrast=structuredClone(profile);escapedContrast.contrast.marker_edge_px=8;assert.throws(()=>terrain.validateTerrainProfile(escapedContrast),/CONTRAST_PROFILE_INVALID/);
 const points=values=>values.map(([x,y])=>({x,y})),donut=terrain.mergeTerrainFillPaths([points([[0,0],[10,0],[8,2],[2,2]]),points([[10,0],[10,10],[8,8],[8,2]]),points([[10,10],[0,10],[2,8],[8,8]]),points([[0,10],[0,0],[2,2],[2,8]])]);assert.equal(donut.paths.length,2);const area=path=>path.reduce((sum,p,i)=>sum+p.x*path[(i+1)%path.length].y-p.y*path[(i+1)%path.length].x,0)/2;assert.equal(donut.paths.reduce((sum,path)=>sum+area(path),0),64);assert(donut.paths.some(path=>area(path)<0));assert(donut.receipt.internal_edge_occurrences_cancelled>0);const touching=terrain.mergeTerrainFillPaths([points([[0,0],[2,0],[0,2]]),points([[0,0],[-2,0],[0,-2]])]);assert.equal(touching.paths.length,2);assert.equal(touching.receipt.connected_fill_components,2);assert.equal(touching.receipt.component_rule,'SHARED_FACE_EDGE_NOT_VERTEX');assert.throws(()=>terrain.mergeTerrainFillPaths([points([[0,0],[2,0],[0,2]]),points([[0,0],[2,0],[0,2]])]),/OVERLAP_INVALID/);
 assert.throws(()=>terrain.mergeTerrainFillPaths([points([[0,0],[2,0],[0,2]]),points([[0,2],[2,0],[0,0]])]),/UNRESOLVED/);const zero=terrain.mergeTerrainFillPaths([points([[0,0],[1,1],[2,2]])]);assert.equal(zero.paths.length,0);assert.equal(zero.receipt.zero_area_faces_omitted,1);assert.deepEqual(zero.receipt.zero_area_projected_coordinates,[points([[0,0],[1,1],[2,2]])]);
 const noOp=on.ctx.commands.length;assert.equal(terrain.terrainRegionStyle(profile,'NEUTRAL'),null);const noOpReceipt=terrain.drawTerrainRegionLayer(on.ctx,null,null);assert.equal(noOpReceipt.luminance_scale,1);assert.equal(on.ctx.commands.length,noOp);
 const failFrame=inputScene.infographic.events.find(event=>event.primary_role==='EVENT_TITLE')?.start_frame??inputScene.infographic.events[0].start_frame;
 on.frame(failFrame/fps);const context=on.ctx,spec=on.sceneSpec,oldStroke=on.ctx.stroke,styleStrokes=on.terrainInfographicReceipt.regions.reduce((count,region)=>count+(region.segment_count?2+(region.glow_drawn?1:0):0),0);let calls=0;
 on.ctx.stroke=function(){calls++;if(calls>styleStrokes)throw Error('INJECTED_INHERITED_STROKE_FAILURE');return oldStroke.apply(this,arguments);};
 try{assert.throws(()=>on.overlay(failFrame/fps),/INJECTED_INHERITED/);assert.equal(on.ctx,context);assert.equal(on.sceneSpec,spec);assert.equal(on.ctx.stack.length,0);}finally{on.ctx.stroke=oldStroke;on.ctx.reset();}
 const prepared=[...on.terrainPrepared.values()][0],projected=infographic.projectInfographicGeometry(prepared,on.camera,on.w,on.h),style=terrain.terrainRegionStyle(profile,'PRIMARY'),failureContext=new RecordingContext(),originalFill=failureContext.fill;
 failureContext.globalCompositeOperation='screen';failureContext.shadowBlur=2;failureContext.globalAlpha=.7;failureContext.fill=()=>{throw Error('INJECTED_COLOR_FILL_FAILURE');};
 assert.throws(()=>terrain.drawTerrainRegionLayer(failureContext,projected,style,{width:on.w,height:on.h}),/INJECTED_COLOR_FILL_FAILURE/);assert.equal(failureContext.stack.length,0);assert.equal(failureContext.globalCompositeOperation,'screen');assert.equal(failureContext.shadowBlur,2);assert.equal(failureContext.globalAlpha,.7);failureContext.fill=originalFill;
 const {frameEvidence}=await import(pathToFileURL(path.join(root,'tools/scene_diagnostic_journal.mjs')));on.frame(failFrame/fps);const audit=on.audit(failFrame/fps),captured=frameEvidence({sceneId:inputScene.scene_id,frameIndex:failFrame,t:failFrame/fps,audit,errors:[],renderer:{},failedInvariants:[],decoded:[1080,1920],decodeError:false});assert.deepEqual(captured.infographic.terrain_visual_profile,audit.terrain_infographic);
 const result={passed:true,checks:28,frames:total,camera_trajectory:'UNCHANGED',material:'UNCHANGED',marker:'UNCHANGED',marker_pixel_contrast:'DRAW_ONLY_V024',text_layout:'UNCHANGED',text_pixel_contrast:'DRAW_ONLY_V024',canal_event_state:'UNCHANGED',overlay_off:'EXACT_V023',source_scene_immutable:true,fill_tessellation:'SHARED_INDEXED_SPHERICAL_EDGE_REFINEMENT',fill_path:'PAIRED_PROJECTED_MESH_EDGE_UNION',primary_visible_frames:primary,secondary_visible_region_frames:secondary,legacy_country_draw_suppressed:suppressed,region_coverage:coverage,additional_texture_uploads:0,GPU:'NOT_RUN',pixel_quality:'NOT_RUN',scope:'Actual native inherited frame/camera/material/overlay with recording Canvas; no pixels or NVIDIA execution'};
 console.log(JSON.stringify(result));
}finally{globalThis.fetch=oldFetch;globalThis.document=oldDocument;}
"""


class TerrainNativeRendererTests(unittest.TestCase):
    def _run_native(self, plan, body):
        original = (ROOT / 'tools/test_infographic_v022.mjs').read_text()
        marker = '\ntry{\n const baselineScene=structuredClone(inputScene);'
        self.assertIn(marker, original)
        setup = original[:original.index(marker)]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'plan.json'
            source.write_text(json.dumps(plan, ensure_ascii=False))
            script = Path(directory) / 'native-terrain.mjs'
            script.write_text(setup + body)
            try:
                completed = subprocess.run(['node', str(script), str(source)],
                    cwd=ROOT, text=True, capture_output=True, timeout=180, check=True)
            except subprocess.CalledProcessError as error:
                self.fail((error.stderr or error.stdout or str(error))[-4000:])
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        return result

    def test_actual_registry_country_union_holes_multipart_touch_and_dateline(self):
        imports = NATIVE_TEST[:NATIVE_TEST.index('try{')]
        body = imports + r"""
try{
 const registry=JSON.parse(buffers['/static/infographic/v022/registry.json']),countries=registry.geometries.filter(record=>['Polygon','MultiPolygon'].includes(record.geometry_type));let poses=0;const details=[];
 const cameraAt=(point,distance,fov)=>{const lon=point[0]*Math.PI/180,lat=point[1]*Math.PI/180,n=new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon)),camera=new THREE.PerspectiveCamera(fov,1080/1920,.02,30);camera.position.copy(n).multiplyScalar(distance);camera.lookAt(n);camera.updateMatrixWorld();return camera;};
 const check=(record,prepared,center,distance,fov)=>{const projected=infographic.projectInfographicGeometry(prepared,cameraAt(center,distance,fov),1080,1920);let union;try{union=terrain.mergeTerrainFillPaths(projected.polygons);}catch(error){throw Error(record.id+' '+JSON.stringify(center)+' '+distance+': '+error.message);}assert.equal(union.receipt.closed,true);assert.equal(union.receipt.branched,false);assert.equal(union.receipt.component_rule,'SHARED_FACE_EDGE_NOT_VERTEX');assert(union.receipt.maximum_endpoint_identification_delta_px<=1.5e-7);poses++;return union;};
 const probes=[['COUNTRY_NLD',[4.226172,51.386475]],['COUNTRY_CAN',[-74.708887,45.003857]],['COUNTRY_BRN',[115.026758,4.899707]],['COUNTRY_FJI',[180,-17]],['COUNTRY_RUS',[180,65]]];
 for(const record of countries){const prepared=terrain.prepareTerrainInfographicGeometry(record),parts=record.geometry_type==='Polygon'?[record.coordinates]:record.coordinates,largest=parts.reduce((a,b)=>a[0].length>b[0].length?a:b),n=new THREE.Vector3();for(const[longitude,latitude]of largest[0]){const lon=longitude*Math.PI/180,lat=latitude*Math.PI/180;n.add(new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon)));}n.normalize();const center=[Math.atan2(-n.z,n.x)*180/Math.PI,Math.asin(n.y)*180/Math.PI];check(record,prepared,center,1.6,40);check(record,prepared,center,4.2,60);const probe=probes.find(([id])=>id===record.id);if(probe){const union=check(record,prepared,probe[1],1.6,40);assert(union.paths.length>0);details.push({id:record.id,source_sha256:record.sha256,paths:union.paths.length,components:union.receipt.connected_fill_components});}}
 assert(countries.length>=242);assert.equal(details.length,5);console.log(JSON.stringify({passed:true,countries:countries.length,poses,actual_touching_country_probes:details,source_geometry:'UNCHANGED',GPU:'NOT_RUN'}));
}finally{globalThis.fetch=oldFetch;globalThis.document=oldDocument;}
"""
        result = self._run_native(generate_infographic_qa(), body)
        self.assertTrue(result['passed'])
        self.assertGreaterEqual(result['countries'], 242)
        self.assertGreaterEqual(result['poses'], 489)
        self.assertEqual(len(result['actual_touching_country_probes']), 5)
        self.assertEqual(result['GPU'], 'NOT_RUN')

    def test_all_720_native_camera_material_marker_text_state_and_v023_off(self):
        plan = prepare_terrain_infographic(
            prepare_bold_infographic(generate_infographic_qa()))
        result = self._run_native(plan, NATIVE_TEST)
        self.assertTrue(result['passed'])
        self.assertEqual(result['frames'], 720)
        for field in ('camera_trajectory', 'material', 'marker', 'text_layout',
                      'canal_event_state'):
            self.assertEqual(result[field], 'UNCHANGED')
        self.assertEqual(result['overlay_off'], 'EXACT_V023')
        self.assertEqual(result['additional_texture_uploads'], 0)
        self.assertEqual(result['GPU'], 'NOT_RUN')

    def test_admitted_multi_country_context_has_no_legacy_solid_redraw(self):
        plan = generate_infographic_qa()
        registry = parent.load_registry()
        authored = deepcopy(plan['metadata']['infographic']['authored_events'])
        event = next(e for e in authored if 'COUNTRY_EGY' in e['target_geometry_refs'])
        event['target_geometry_refs'].append('COUNTRY_ISR')
        plan['metadata']['infographic']['authored_events'] = authored
        metadata = plan['metadata']
        for scene in plan['scenes']:
            own = [e for e in authored if e['scene_id'] == scene['scene_id']]
            scene['infographic'] = parent.compile_scene_selection(scene, own,
                registry, metadata['infographic']['semantic_segments'],
                metadata['frame_grid']['fps'],
                {claim['id']: claim for claim in plan['story']['claims']},
                metadata['infographic']['parent_renderer_family'])
        self.assertTrue(parent.validate_infographic(plan)['passed'])
        plan = prepare_terrain_infographic(prepare_bold_infographic(plan))
        self.assertTrue(any(row['geometry_ref'] == 'COUNTRY_ISR' and
            row['role'] == 'SECONDARY' for row in plan['scenes'][0]['bold_infographic']['regions']))
        imports = NATIVE_TEST[:NATIVE_TEST.index('try{')]
        body = imports + r"""
try{
 const on=terrain.createTerrainInfographicRenderer(inputScene,plan);await on.init();
 const contextRegion=inputScene.bold_infographic.regions.find(region=>region.geometry_ref==='COUNTRY_ISR'&&region.role==='SECONDARY');assert(contextRegion);
 const t=(contextRegion.start_frame+15)/30;on.ctx.reset();on.actx.reset();on.frame(t);
 const receipt=on.audit(t).infographic,child=on.terrainInfographicReceipt;
 const originalTarget=receipt.geometry.find(geometry=>geometry.geometry_id==='COUNTRY_ISR');assert(originalTarget);
 assert.equal(originalTarget.visual_role,'SECONDARY');assert.equal(originalTarget.blend_mode,'color');assert.equal(originalTarget.fill_alpha,on.terrainProfile.geometry.SECONDARY.fill_alpha);assert.equal(originalTarget.legacy_draw_suppressed,true);assert.equal(originalTarget.drawn_by,'COLORIZED_NATIVE_TERRAIN_LAYER');
 const activeTargets=new Set(inputScene.infographic.geometry_layers.filter(layer=>t*30>=layer.start_frame&&t*30<layer.end_frame).map(layer=>layer.geometry_ref));
 const activeCountries=new Set(child.regions.map(region=>region.geometry_id));
 assert.equal(child.legacy_country_draw_groups_suppressed,[...activeTargets].filter(id=>activeCountries.has(id)).length);assert(child.legacy_country_draw_groups_suppressed>=2);
 assert.equal(on.ctx.commands.filter(command=>command[0]==='set'&&command[1]==='globalCompositeOperation'&&command[2]==='color').length,child.regions.filter(region=>region.polygon_count>0).length);
 assert.equal(on.ctx.stack.length,0);
 console.log(JSON.stringify({passed:true,secondary_country:'COUNTRY_ISR',legacy_country_groups_suppressed:child.legacy_country_draw_groups_suppressed,secondary_receipt:'NATIVE_COLOR_ONLY',GPU:'NOT_RUN'}));
}finally{globalThis.fetch=oldFetch;globalThis.document=oldDocument;}
"""
        result = self._run_native(plan, body)
        self.assertTrue(result['passed'])
        self.assertEqual(result['secondary_receipt'], 'NATIVE_COLOR_ONLY')
        self.assertEqual(result['GPU'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
