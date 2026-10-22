from pathlib import Path
import hashlib,json,difflib
ns=Path(__file__).resolve().parents[1];root=ns.parents[2]
original=(ns/'backups/renderer.5cc9b98.original.mjs').read_text()
current=(root/'world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs').read_text()
assert hashlib.sha256(original.encode()).hexdigest()=='e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38'
assert hashlib.sha256(current.encode()).hexdigest()=='c5aaf6b902d5f5374d93230e8979919dee398e47c41cf65a12e3bf2a35b55f9d'
start='const terrainFragment = '
end='const ribbonVertex = '
a=original.index(start);b=original.index(end,a)
ca=current.index(start);cb=current.index(end,ca)
fragment=original[a:b]
edits=[
 ('uniform vec4 bounds, tileBounds;', '''uniform vec4 bounds, tileBounds;
// Opt-in inverse geographic sampling. GIS targets stay in current-view UVs.
uniform int similarityEnabled;
uniform vec2 similarityCenterQ, similarityAngle;
uniform float similarityScale;
uniform vec3 similarityOrigin;
uniform vec2 similarityTileSpanQ, similarityTileCenterUV;'''),
 (' vec2 geo=mix(bounds.xy,bounds.zw,vUv);',' vec2 geo=mix(bounds.xy,bounds.zw,vUv);\n vec2 activeSimilarityDeltaQ=vec2(0.);'),
 (' vec2 guv=vec2((geo.x+180.)/360.,(geo.y+90.)/180.);', ''' if(globeProjection==0&&similarityEnabled==1){
  vec2 d=vec2((vUv.x-.5)*1080.,(.5-vUv.y)*1920.)/similarityScale;
  vec2 deltaQ=vec2(similarityAngle.x*d.x+similarityAngle.y*d.y,-similarityAngle.y*d.x+similarityAngle.x*d.y);
  vec2 q=similarityCenterQ+deltaQ;
  activeSimilarityDeltaQ=deltaQ;
  geo=vec2(similarityOrigin.x+q.x/similarityOrigin.z,similarityOrigin.y-q.y);
 }
 vec2 guv=vec2((geo.x+180.)/360.,(geo.y+90.)/180.);'''),
 (' vec2 tuv=(geo-tileBounds.xy)/(tileBounds.zw-tileBounds.xy);', ''' vec2 tuv=(geo-tileBounds.xy)/(tileBounds.zw-tileBounds.xy);
 // Relative source UV is evaluated before the unchanged material/lighting path.
 if(globeProjection==0&&similarityEnabled==1)tuv=similarityTileCenterUV+vec2(activeSimilarityDeltaQ.x/similarityTileSpanQ.x,-activeSimilarityDeltaQ.y/similarityTileSpanQ.y);'''),
]
helper='''// Preserve the original default/globe shader bytes and compile its exact program.
// Only the explicit opt-in builds this bounded source variant, before material creation.
function referenceSimilarityTerrainFragment(){
 let source=terrainFragment;
 const edits='''+json.dumps(edits,ensure_ascii=False,indent=2)+''';
 for(const [from,to] of edits){
  const at=source.indexOf(from);
  if(at<0||source.indexOf(from,at+from.length)!==-1)throw Error('SIMILARITY_SHADER_SOURCE_ANCHOR_CHANGED');
  source=source.slice(0,at)+to+source.slice(at+from.length);
 }
 return source;
}
'''
candidate=current[:ca]+fragment+helper+current[cb:]
old=" const terrainMaterial=mat(fullscreenVertex,terrainFragment,uniforms),terrainScene=fullScene(terrainMaterial);"
new=" const terrainMaterial=mat(fullscreenVertex,similarityOptIn?referenceSimilarityTerrainFragment():terrainFragment,uniforms),terrainScene=fullScene(terrainMaterial);"
assert candidate.count(old)==1;candidate=candidate.replace(old,new)
assert candidate[candidate.index(start):candidate.index('// Preserve the original default/globe shader bytes')]==fragment
path=ns/'candidates/renderer.similarity.candidate05.mjs'
with path.open('x')as f:f.write(candidate)
for name,before in [('original',original),('candidate04',current)]:
 patch=''.join(difflib.unified_diff(before.splitlines(True),candidate.splitlines(True),fromfile='renderer.mjs@'+name,tofile='renderer.mjs@candidate05'))
 with(ns/f'candidates/renderer.similarity.proposed05-vs-{name}.patch').open('x')as f:f.write(patch)
summary={'schema':'WORLD_ENGINE_REFERENCE_RENDERER_CONFIRMED_REGRESSION_FIX_PROPOSAL_V1','confirmedFailure':'Default globe shader changed12 actualpixels(maxRGBdelta5) with candidate04; flat12frames bit-exact','originalSHA256':hashlib.sha256(original.encode()).hexdigest(),'current04SHA256':hashlib.sha256(current.encode()).hexdigest(),'candidate05SHA256':hashlib.sha256(candidate.encode()).hexdigest(),'originalTerrainFragmentDeclarationSHA256':hashlib.sha256(fragment.encode()).hexdigest(),'candidateDefaultTerrainFragmentDeclarationByteIdentical':True,'candidateBytes':len(candidate.encode()),'applied':False,'protectedRendererStill04':True,'fixScope':'Opt-in shader source compiled only for explicitly enabled factory; original default/globe GLSL bytes restored; no threshold relaxation or framebuffer blit'}
with(ns/'candidates/PROPOSAL_SUMMARY05.json').open('x')as f:json.dump(summary,f,indent=2);f.write('\n')
print(json.dumps(summary))
