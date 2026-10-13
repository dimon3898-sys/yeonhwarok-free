/** Focused native-GPU smoke. It inherits the saved parent runtime without editing
 * any Final source. Its explicit synthetic screen projection is a shader test;
 * the integrated Synthetic/proof suite separately binds native GIS projection.
 */
import {writeFile,mkdir,readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {openPolishRuntime} from '../event-feature-bundle-v2-polish/polish_runtime.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
const runtime=await openPolishRuntime();
let results;
try{
 results=await runtime.page.evaluate(async()=>{
  const {createAreaOverlayPass}=await import('/modules/area_overlay_pass_v3.mjs');
  const {compileAreaLinePrimitive,geographicPropagationContour}=await import('/modules/area_core_v3.mjs');
  const {captureFlowNativeGlState}=await import('/modules/flow_graphic_pass_v2.mjs');
  const canvas=document.querySelector('canvas'),gl=canvas.getContext('webgl2'),width=1080,height=1920;
  const read=()=>{const pixels=new Uint8Array(width*height*4);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);return pixels;};
  const project=([x,y])=>[500+x*10,1000-y*10];
  const source={source_type:'SYNTHETIC_TEST',source_reference:'AREA_V3_NATIVE_GPU_SMOKE',verification_status:'SYNTHETIC_TEST'};
  const square={type:'Polygon',coordinates:[[[-5,-5],[5,-5],[5,5],[-5,5],[-5,-5]]]};
  const multipart={type:'MultiPolygon',coordinates:[
   [[[-5,-5],[5,-5],[5,5],[-5,5],[-5,-5]],[[-3.5,-3.5],[-3.5,3.5],[3.5,3.5],[3.5,-3.5],[-3.5,-3.5]]],
   [[[7,-1],[9,-1],[9,1],[7,1],[7,-1]]]]};
  const polygon=(id,geometry,coverage=1)=>({id,geometry,alpha:1,coverage,coverageOrigin:[0,0]});
  const frontGeometry={type:'LineString',coordinates:[[-5,-4],[0,-2],[5,4]]};
  const propagationGeometry=geographicPropagationContour({origin:[0,0],angular_range_degrees:[0,360]},4);
  const line=(id,geometry,revealFraction=1)=>({id,geometry,alpha:1,revealFraction,
   linePrimitive:compileAreaLinePrimitive({geometry,source,data_mode:'SYNTHETIC_TEST'},{project})});
  const cases=[
   {name:'STATIC_POLYGON',controls:{areas:[polygon('static',square)]}},
   {name:'PARTS_AND_HOLE',controls:{areas:[polygon('parts',multipart)]},holeBox:[470,976,530,1025]},
   {name:'RADIAL_GROW',controls:{areas:[polygon('grow',square,.65)]},coverageRadius:Math.hypot(50,50)*.65},
   {name:'RADIAL_CONTRACT',controls:{areas:[polygon('contract',square,.25)]},coverageRadius:Math.hypot(50,50)*.25},
   {name:'V1_FRONT_RING_IMPACT',controls:{fronts:[line('front',frontGeometry,.72)],propagations:[line('ring',propagationGeometry)],
    impacts:[polygon('impact',{type:'Polygon',coordinates:[[[3,-4],[5,-4],[5,4],[3,4],[3,-4]]]})]}}
  ];
  const stateDiff=(before,after,path='')=>{
   if(before===after)return[];
   if(ArrayBuffer.isView(before)&&ArrayBuffer.isView(after))return before.length===after.length&&Array.from(before).every((value,index)=>value===after[index])?[]:[path];
   if(Array.isArray(before)&&Array.isArray(after))return before.length===after.length?before.flatMap((value,index)=>stateDiff(value,after[index],path+'['+index+']')):[path];
   if(before&&after&&typeof before==='object'&&typeof after==='object'&&Object.getPrototypeOf(before)===Object.prototype&&Object.getPrototypeOf(after)===Object.prototype)
    return [...new Set([...Object.keys(before),...Object.keys(after)])].flatMap(key=>stateDiff(before[key],after[key],path+'.'+key));
   return[path];
  };
  await window.flowProof.capture(120,{flowEnabled:false,png:false});
  const constructionBefore=captureFlowNativeGlState(gl),pass=createAreaOverlayPass({canvas}),constructionStateDiff=stateDiff(constructionBefore,captureFlowNativeGlState(gl));
  const records=[];
  try{
   for(const test of cases){
    await window.flowProof.capture(120,{flowEnabled:false,png:false});
    const before=read(),state=captureFlowNativeGlState(gl),controls={areas:[],fronts:[],propagations:[],impacts:[],...test.controls};
    const draw=pass.draw({controls,project,safeArea:[108,180,972,1700],
     protectedGraphics:[{kind:'PROTECTED_TEXT',box:[460,960,475,975]}],primaryMaterialColor:[.85,.65,.17],
     boundarySegments:[{a:[500,945],b:[500,1055],radiusPx:10}]});
    const after=read(),nativeStateDiff=stateDiff(state,captureFlowNativeGlState(gl));
    let changed=0,protectedChanged=0,boundaryChanged=0,outsideRoiChanged=0,holeChanged=0,outsideCoverageChanged=0;
    const holeProbePixelsOutsideNativeBoundary=test.holeBox?Array.from({length:test.holeBox[2]-test.holeBox[0]+1},(_,i)=>test.holeBox[0]+i)
     .filter(x=>x<489||x>511).length*(test.holeBox[3]-test.holeBox[1]+1):0;
    for(let y=0;y<height;y++)for(let x=0;x<width;x++){
     const offset=((height-1-y)*width+x)*4;if([0,1,2,3].every(channel=>before[offset+channel]===after[offset+channel]))continue;
     changed++;
     if(x>=460&&x<=475&&y>=960&&y<=975)protectedChanged++;
     if(x>=490&&x<=510&&y>=945&&y<=1055)boundaryChanged++;
     if(!draw.rois.some(box=>x+.5>=box[0]&&x+.5<=box[2]&&y+.5>=box[1]&&y+.5<=box[3]))outsideRoiChanged++;
     if(test.holeBox&&x>=test.holeBox[0]&&x<=test.holeBox[2]&&y>=test.holeBox[1]&&y<=test.holeBox[3])holeChanged++;
     if(test.coverageRadius!==undefined&&Math.hypot(x+.5-500,y+.5-1000)>test.coverageRadius+.5)outsideCoverageChanged++;
    }
    records.push({name:test.name,changed,protectedChanged,boundaryChanged,outsideRoiChanged,holeChanged,outsideCoverageChanged,holeProbePixelsOutsideNativeBoundary,
     nativeStateDiff,glError:gl.getError(),parts:draw.areas[0]?.parts??null,holes:draw.areas[0]?.holes??null,
     V1LineEvaluators:[...draw.fronts,...draw.propagations].map(item=>item.evaluator),
     rois:draw.rois,selectedAccent:draw.style.selection.selectedName,impactAccent:draw.style.selection.impactName});
   }
  }finally{const before=captureFlowNativeGlState(gl);pass.dispose();const diff=stateDiff(before,captureFlowNativeGlState(gl));if(diff.length)throw Error('AREA_SMOKE_DISPOSAL_GL_STATE_'+JSON.stringify(diff));}
  return {constructionStateDiff,cases:records,backend:gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL)};
 });
}finally{await runtime.close();}
const bad=results.constructionStateDiff.length||results.cases.some(test=>test.changed===0||test.protectedChanged||test.boundaryChanged||test.outsideRoiChanged||test.holeChanged||test.outsideCoverageChanged||test.nativeStateDiff.length||test.glError);
if(results.cases[1].parts!==2||results.cases[1].holes!==1||results.cases[1].holeProbePixelsOutsideNativeBoundary<500||results.cases[3].changed>=results.cases[2].changed)throw Error('AREA_SMOKE_TOPOLOGY_OR_CONTRACTION_FAIL');
const files=['overlay_smoke.mjs','../../web/map_infographic_v1/area_overlay_pass_v3.mjs','../../web/map_infographic_v1/area_style_v3.mjs','../../web/map_infographic_v1/area_core_v3.mjs'];
const sourceBindings={};for(const file of files)sourceBindings[file]=createHash('sha256').update(await readFile(path.resolve(root,file))).digest('hex');
const report={version:'AREA_OVERLAY_NATIVE_GPU_SMOKE_V3',status:bad?'FAIL':'PASS',
 purpose:'FOCUSED_NATIVE_GPU_SHADER_AND_PROTECTION_TEST_NOT_REAL_FIXTURE_ADMISSION',
 projection:'EXPLICIT_SYNTHETIC_SCREEN_MODEL_ON_UNCHANGED_PARENT_NATIVE_CANVAS',sourceBindings,
 permanentGateExecuted:false,finishedFrameBlit:false,...results};
await mkdir(path.join(root,'evidence'),{recursive:true});await writeFile(path.join(root,'evidence/OVERLAY_SMOKE.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:report.status,cases:results.cases.map(test=>({name:test.name,changed:test.changed,protectedChanged:test.protectedChanged,boundaryChanged:test.boundaryChanged,nativeStateDiff:test.nativeStateDiff}))}));
if(bad)throw Error('AREA_OVERLAY_NATIVE_GPU_SMOKE_FAIL');
