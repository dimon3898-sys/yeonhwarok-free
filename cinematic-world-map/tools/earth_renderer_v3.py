"""Blender Earth renderer; preserves the Three.js GIS/camera authoring layer.
Run with blender -b -t 4 --python tools/earth_renderer_v3.py -- [options].
"""
import bpy, json, math, sys, argparse, time
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
C=Matrix(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))
def mat4(a): return Matrix(tuple(tuple(a[c*4+r] for c in range(4)) for r in range(4)))
def geo(lon,lat,r=1):
    a,b=math.radians(lon),math.radians(lat)
    return Vector((r*math.cos(b)*math.cos(a),r*math.cos(b)*math.sin(a),r*math.sin(b)))
def node(nt,kind):return nt.nodes.new(kind)
def image_node(nt,path,noncolor=False):
    n=node(nt,'ShaderNodeTexImage');n.image=bpy.data.images.load(str(path),check_existing=True)
    if noncolor:n.image.colorspace_settings.name='Non-Color'
    n.interpolation='Linear';return n
def math_node(nt,op,a=None,b=None):
    n=node(nt,'ShaderNodeMath');n.operation=op
    for i,v in enumerate((a,b)):
        if v is None:continue
        if isinstance(v,(int,float)):n.inputs[i].default_value=v
        else:nt.links.new(v,n.inputs[i])
    return n.outputs[0]
def sphere(name,radius,mat,segments=512,rings=256):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,radius=radius)
    obj=bpy.context.object;obj.name=name;obj.data.materials.append(mat)
    uv=obj.data.uv_layers.active
    for face in obj.data.polygons:
        vals=[]
        for li in face.loop_indices:
            v=obj.data.vertices[obj.data.loops[li].vertex_index].co.normalized()
            vals.append((li,math.atan2(v.y,v.x)/(2*math.pi)+.5,math.asin(max(-1,min(1,v.z)))/math.pi+.5))
        seam=max(v[1] for v in vals)-min(v[1] for v in vals)>.5
        for li,u,v in vals:uv.data[li].uv=(u+(1 if seam and u<.5 else 0),v)
        face.use_smooth=True
    return obj
def surface(day,night,terrain,sun):
    m=bpy.data.materials.new('EARTH / PBR sunlight, terrain, real urban radiance');m.use_nodes=True
    nt=m.node_tree;nt.nodes.clear();out=node(nt,'ShaderNodeOutputMaterial');p=node(nt,'ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'],out.inputs['Surface'])
    d=image_node(nt,day);n=image_node(nt,night);b=image_node(nt,terrain,True)
    nt.links.new(d.outputs['Color'],p.inputs['Base Color']);p.inputs['Roughness'].default_value=.52
    bump=node(nt,'ShaderNodeBump');bump.inputs['Strength'].default_value=.12;bump.inputs['Distance'].default_value=.00018
    nt.links.new(b.outputs['Color'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    geom=node(nt,'ShaderNodeNewGeometry');dot=node(nt,'ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=sun
    nt.links.new(geom.outputs['Normal'],dot.inputs[0])
    gate=math_node(nt,'MULTIPLY',dot.outputs['Value'],-8)
    gate=math_node(nt,'ADD',gate,.25);cl=node(nt,'ShaderNodeClamp');nt.links.new(gate,cl.inputs[0])
    nt.links.new(n.outputs['Color'],p.inputs['Emission Color']);nt.links.new(math_node(nt,'MULTIPLY',cl.outputs[0],4),p.inputs['Emission Strength'])
    return m
def clouds(path):
    m=bpy.data.materials.new('CLOUD / independent altitude and cast shadow');m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
    out=node(nt,'ShaderNodeOutputMaterial');p=node(nt,'ShaderNodeBsdfPrincipled');p.inputs['Base Color'].default_value=(.8,.86,.91,1);p.inputs['Roughness'].default_value=.88
    tex=image_node(nt,path,True);rgb=node(nt,'ShaderNodeRGBToBW');nt.links.new(tex.outputs['Color'],rgb.inputs[0]);opacity=math_node(nt,'MULTIPLY',rgb.outputs[0],.52)
    bump=node(nt,'ShaderNodeBump');bump.inputs['Strength'].default_value=.32;bump.inputs['Distance'].default_value=.0003;nt.links.new(rgb.outputs[0],bump.inputs['Height']);nt.links.new(bump.outputs[0],p.inputs['Normal'])
    transparent=node(nt,'ShaderNodeBsdfTransparent');mix=node(nt,'ShaderNodeMixShader');nt.links.new(opacity,mix.inputs[0]);nt.links.new(transparent.outputs[0],mix.inputs[1]);nt.links.new(p.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs['Surface']);return m
def atmosphere():
    m=bpy.data.materials.new('ATMOSPHERE / exponential Rayleigh volume');m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();out=node(nt,'ShaderNodeOutputMaterial');v=node(nt,'ShaderNodeVolumeScatter');v.inputs['Color'].default_value=(.10,.29,.75,1);v.inputs['Anisotropy'].default_value=.12
    g=node(nt,'ShaderNodeNewGeometry');length=node(nt,'ShaderNodeVectorMath');length.operation='LENGTH';nt.links.new(g.outputs['Position'],length.inputs[0]);height=math_node(nt,'SUBTRACT',length.outputs['Value'],1)
    exp=math_node(nt,'EXPONENT',math_node(nt,'MULTIPLY',height,-600));nt.links.new(math_node(nt,'MULTIPLY',exp,28),v.inputs['Density']);nt.links.new(v.outputs[0],out.inputs['Volume']);return m
def emission(name,color,strength):
    m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();out=node(nt,'ShaderNodeOutputMaterial');e=node(nt,'ShaderNodeEmission');e.inputs['Color'].default_value=(*color,1);e.inputs['Strength'].default_value=strength;nt.links.new(e.outputs[0],out.inputs['Surface']);return m
def curve_object(name,points,radius,mat):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=1;c.bevel_depth=radius;c.bevel_resolution=3
    s=c.splines.new('POLY');s.points.add(len(points)-1)
    for v,p in zip(s.points,points):v.co=(*p,1)
    o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);c.materials.append(mat);return o
def make_aircraft(data,pose):
    root=bpy.data.objects.new('AIRCRAFT_RIG',None);bpy.context.collection.objects.link(root);root.matrix_world=C@mat4(pose['entity']['matrix']);root.hide_render=not pose['entity']['visible']
    for i,item in enumerate(data['model']):
        verts=[item['position'][j:j+3] for j in range(0,len(item['position']),3)];indices=item['index'] or list(range(len(verts)));faces=[indices[j:j+3] for j in range(0,len(indices),3)]
        mesh=bpy.data.meshes.new(item['name']);mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new(item['name'],mesh);bpy.context.collection.objects.link(o);o.parent=root;o.matrix_local=mat4(item['matrix']);o.hide_render=root.hide_render
        for p in mesh.polygons:p.use_smooth=True
        m=bpy.data.materials.new('AIRCRAFT_PBR_'+str(i));m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*item['material']['color'],1);p.inputs['Roughness'].default_value=item['material']['roughness'];p.inputs['Metallic'].default_value=item['material']['metalness'];p.inputs['Coat Weight'].default_value=.18;mesh.materials.append(m)
    return root
def build(args):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.render.engine=args.engine;scene.render.resolution_x=args.width;scene.render.resolution_y=round(args.width*16/9);scene.render.resolution_percentage=100;scene.render.fps=30
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='16';scene.render.threads_mode='FIXED';scene.render.threads=4
    if args.engine=='CYCLES':
        scene.cycles.device='CPU';scene.cycles.samples=args.samples;scene.cycles.use_denoising=False;scene.cycles.adaptive_threshold=.025;scene.cycles.max_bounces=8;scene.cycles.volume_bounces=2;scene.cycles.transparent_max_bounces=8;scene.cycles.volume_step_rate=.75
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.7
    scene.world=bpy.data.worlds.new('SPACE');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.007,.013,.026,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.18
    sun=geo(18,-12);light=bpy.data.lights.new('SUN / common scene direction','SUN');light.energy=4;light.angle=math.radians(.53);o=bpy.data.objects.new('SUN',light);bpy.context.collection.objects.link(o);o.rotation_euler=(-sun).to_track_quat('-Z','Y').to_euler()
    asset=ROOT/'assets/v3/earth';day=asset/'earth-day-8k.jpg';night=asset/'earth-night-8k.jpg';cloud=asset/'earth-clouds-8k.jpg';terrain=asset/'earth-topology.png'
    if not day.exists():day=ROOT/'assets/gis/earth-blue-marble.jpg'
    if not night.exists():night=ROOT/'assets/gis/earth-lights.png'
    if not terrain.exists():terrain=ROOT/'assets/gis/earth-topology.png'
    if not cloud.exists():cloud=ROOT/'assets/v2/cloud-haze.png'
    sphere('EARTH / accurate equirectangular surface',1,surface(day,night,terrain,sun))
    sphere('CLOUD / 6 km separate shell',1+6/6371,clouds(cloud),384,192)
    sphere('ATMOSPHERE / 100 km exponential shell',1+100/6371,atmosphere(),256,128)
    data=json.loads((ROOT/'outputs/v3_scene.json').read_text());pose=data['frames'][round(args.time*60)]
    camdata=bpy.data.cameras.new('CINEMATIC_CAMERA');cam=bpy.data.objects.new('CINEMATIC_CAMERA',camdata);bpy.context.collection.objects.link(cam);cam.matrix_world=C@mat4(pose['camera']['matrix']);camdata.sensor_fit='VERTICAL';camdata.sensor_height=36;camdata.lens=36/(2*math.tan(math.radians(pose['camera']['fov'])/2));camdata.clip_start=.00001;camdata.clip_end=30;scene.camera=cam
    for i,r in enumerate(data['routes']):
        p=pose['progress'][i]
        if p>0:
            points=r['points'][:max(2,round(p*(len(r['points'])-1))+1)];curve_object('GREAT_CIRCLE_ARC_'+str(i),points,.0004,emission('ROUTE_CORE_'+str(i),(.36,.77,1),3.5))
    make_aircraft(data,pose)
    scene.use_nodes=True;nt=scene.node_tree;nt.nodes.clear();rl=nt.nodes.new('CompositorNodeRLayers');gl=nt.nodes.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=2;gl.size=7;gl.mix=-.93;out=nt.nodes.new('CompositorNodeComposite');nt.links.new(rl.outputs['Image'],gl.inputs['Image']);nt.links.new(gl.outputs['Image'],out.inputs['Image'])
    scene.render.filepath=str(ROOT/'outputs'/args.output)
    return scene
def main():
    p=argparse.ArgumentParser();p.add_argument('--time',type=float,default=.5);p.add_argument('--width',type=int,default=540);p.add_argument('--samples',type=int,default=24);p.add_argument('--engine',default='CYCLES');p.add_argument('--output',default='v3_probe.png');args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    start=time.monotonic();scene=build(args);built=time.monotonic();bpy.ops.render.render(write_still=True);end=time.monotonic();record={'engine':args.engine,'width':args.width,'height':scene.render.resolution_y,'samples':args.samples,'time':args.time,'build_seconds':built-start,'render_seconds':end-built,'output':scene.render.filepath};(ROOT/'outputs'/(Path(args.output).stem+'_benchmark.json')).write_text(json.dumps(record,indent=2));print('V3_BENCHMARK',json.dumps(record))
if __name__=='__main__':main()
