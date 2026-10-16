/** Conservative camera extension. Original V5, layout, projection and detail easing remain owners. */
import {detailSmootherstep} from '/modules/camera_detail_approach_adapter_v1.mjs';
const copy=value=>structuredClone(value),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),
 center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2],span=b=>[b[2]-b[0],b[3]-b[1]],
 valid=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]>=-180&&b[2]<=180&&b[1]>=-90&&b[3]<=90&&b[0]<b[2]&&b[1]<b[3];
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite);
function vertices(geometry){
 if(!geometry||!['Point','LineString','Polygon','MultiLineString','MultiPolygon'].includes(geometry.type))throw Error('PRODUCTION_FOCUS_SOURCE_GEOMETRY_REQUIRED');
 const result=[];function walk(value){if(point(value))result.push([...value]);else if(Array.isArray(value))value.forEach(walk);else throw Error('PRODUCTION_FOCUS_COORDINATES_REQUIRED');}
 walk(geometry.coordinates);return result;
}
export function interpolateProductionBounds(a,b,t){
 if(!valid(a)||!valid(b)||!Number.isFinite(t)||t<0||t>1)throw Error('PRODUCTION_FOCUS_BOUNDS_REQUIRED');
 if(t===0||same(a,b))return [...a];if(t===1)return [...b];
 const u=detailSmootherstep(t),ac=center(a),bc=center(b),as=span(a),bs=span(b),
  c=ac.map((v,i)=>v+(bc[i]-v)*u),s=as.map((v,i)=>Math.exp(Math.log(v)+(Math.log(bs[i])-Math.log(v))*u));
 return[c[0]-s[0]/2,c[1]-s[1]/2,c[0]+s[0]/2,c[1]+s[1]/2];
}
export function geometryScreenSafety({geometries,bounds,safeArea,output=[1080,1920],paddingPixels=16}){
 if(!valid(bounds)||!Array.isArray(safeArea)||safeArea.length!==4)throw Error('PRODUCTION_FOCUS_SAFE_AREA_REQUIRED');
 const projected=geometries.flatMap(vertices).map(p=>[(p[0]-bounds[0])/(bounds[2]-bounds[0])*output[0],
  (bounds[3]-p[1])/(bounds[3]-bounds[1])*output[1]]);
 if(!projected.length)throw Error('PRODUCTION_FOCUS_NONEMPTY_GEOMETRY_REQUIRED');
 const extent=[Math.min(...projected.map(p=>p[0])),Math.min(...projected.map(p=>p[1])),
  Math.max(...projected.map(p=>p[0])),Math.max(...projected.map(p=>p[1]))],
  inside=projected.every(p=>p[0]>=safeArea[0]+paddingPixels&&p[0]<=safeArea[2]-paddingPixels
   &&p[1]>=safeArea[1]+paddingPixels&&p[1]<=safeArea[3]-paddingPixels);
 return{wholeSuppliedGeometrySafe:inside,projectedBounds:extent,paddingPixels};
}
export function deriveConservativeFocusBounds({geometries,anchor,approvedBounds,safeArea,output=[1080,1920],paddingPixels=16}){
 if(!valid(approvedBounds)||!point(anchor))throw Error('PRODUCTION_FOCUS_APPROVED_BASE_REQUIRED');
 const points=[...geometries.flatMap(vertices),anchor],required=[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),
  Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))],floor=span(approvedBounds),
  safe=[safeArea[0]+paddingPixels,safeArea[1]+paddingPixels,safeArea[2]-paddingPixels,safeArea[3]-paddingPixels],
  factor=Math.max(1,(required[2]-required[0])/(safe[2]-safe[0])*output[0]/floor[0],
   (required[3]-required[1])/(safe[3]-safe[1])*output[1]/floor[1]),s=floor.map(v=>v*factor),r=center(required),
  safeCenter=[(safe[0]+safe[2])/2/output[0],1-(safe[1]+safe[3])/2/output[1]],
  c=[r[0]+(.5-safeCenter[0])*s[0],r[1]+(.5-safeCenter[1])*s[1]],candidate=[c[0]-s[0]/2,c[1]-s[1]/2,c[0]+s[0]/2,c[1]+s[1]/2];
 if(!valid(candidate))return{decision:'USE_CURRENT_VIEW',bounds:[...approvedBounds],reason:'GEOGRAPHIC_DOMAIN_LIMIT'};
 return{decision:same(candidate,approvedBounds)?'USE_CURRENT_VIEW':'CONSERVATIVE_EVENT_FOCUS_REQUIRED',bounds:candidate,
  reason:'FULL_SUPPLIED_GEOMETRY_SAFE_PAN_OR_WIDEN_ONLY',closerThanParentApprovedFloor:false,localAdmissionGranted:false};
}
/** Every candidate includes old+new snapshot geometry; rejected motion keeps the preceding view. */
export function compileProductionFocusPlan({chapters,totalFrames,approvedBounds,safeArea,anchor,geometriesForChapter,
 approachFrames=48,validateBounds=()=>({valid:true}),output=[1080,1920],preserveInitialView=false}){
 if(!Array.isArray(chapters)||!chapters.length||!Number.isSafeInteger(totalFrames)||!valid(approvedBounds)
  ||typeof geometriesForChapter!=='function'||!Number.isSafeInteger(approachFrames)||approachFrames<2)
  throw Error('PRODUCTION_FOCUS_PLAN_INPUT_REQUIRED');
 let previous=[...approvedBounds];const entries=[];
 for(const [index,chapter]of chapters.entries()){
  const geometry=geometriesForChapter(chapter),prior=index?geometriesForChapter(chapters[index-1]):geometry,
   required=[...prior,...geometry],target=deriveConservativeFocusBounds({geometries:required,anchor,approvedBounds,safeArea,output}),
   duration=Math.min(approachFrames,chapter.endFrame-chapter.startFrame),candidate=index===0&&preserveInitialView?previous:target.bounds;
  if(index===0&&preserveInitialView){target.decision='USE_CURRENT_VIEW';target.reason='INITIAL_PARENT_DETAIL_LOCK_AND_LINE_REVEAL_PRESERVED';}
  let rejection=null,actualTarget=null;const attempts=[];
  // Backtracking searches safe focus strength; it neither shrinks the admitted
  // floor nor moves an existing graphic to force a camera candidate through.
  for(const strength of [1,.65,.4,.2,.1]){
   const proposed=interpolateProductionBounds(previous,candidate,strength);let failure=null;
   for(let offset=0;offset<duration;offset++){
    const actual=interpolateProductionBounds(previous,proposed,offset/Math.max(1,duration-1)),
     safety=geometryScreenSafety({geometries:required,bounds:actual,safeArea,output}),
     native=validateBounds(actual,chapter.startFrame+offset);
    if(!safety.wholeSuppliedGeometrySafe||native?.valid!==true){failure=!safety.wholeSuppliedGeometrySafe?'FULL_GEOMETRY_NOT_SAFE_DURING_APPROACH':'PROTECTED_NATIVE_GRAPHICS_NOT_SAFE';break;}
   }
   attempts.push({strength,accepted:!failure,reason:failure});
   if(!failure){actualTarget=proposed;rejection=null;break;}rejection=failure;
  }
  const accepted=actualTarget!==null;
  if(!accepted){
   const fallbackSafety=geometryScreenSafety({geometries:required,bounds:previous,safeArea,output}),
    fallbackNative=validateBounds(previous,chapter.startFrame);
   if(!fallbackSafety.wholeSuppliedGeometrySafe||fallbackNative?.valid!==true)
    throw Error('PRODUCTION_FOCUS_NO_SAFE_CURRENT_VIEW_'+(chapter.chapterId??chapter.id));
   actualTarget=previous;
  }
  entries.push({chapterId:chapter.chapterId??chapter.id,startFrame:chapter.startFrame,endFrame:chapter.endFrame,
   approachFrames:duration,startBounds:[...previous],targetBounds:[...actualTarget],
   decision:rejection?'USE_CURRENT_VIEW':target.decision,reason:rejection??target.reason,
   closerThanParentApprovedFloor:false,surveyAdmissionModified:false,localAdmissionGranted:false,
   candidateAccepted:accepted,focusAdmissionAttempts:attempts});previous=[...actualTarget];
 }
 return{version:'UNIVERSAL_PRODUCTION_CAMERA_V3',totalFrames,approvedBounds:copy(approvedBounds),safeArea:copy(safeArea),entries,
  ownership:{v5:'UNCHANGED_PARENT_V5',extension:'CONSERVATIVE_GEOMETRY_FOCUS_PAN_OR_WIDEN',easing:'UNCHANGED_DETAIL_SMOOTHERSTEP',
   newClosestDetailCertified:false,protectedGraphicsReprojected:true}};
}
export function evaluateProductionFocusFrame(plan,frame){
 if(plan?.version!=='UNIVERSAL_PRODUCTION_CAMERA_V3'||!Number.isSafeInteger(frame)||frame<0||frame>=plan.totalFrames)
  throw Error('PRODUCTION_FOCUS_GLOBAL_FRAME_REQUIRED');
 const row=plan.entries.find(entry=>frame>=entry.startFrame&&frame<entry.endFrame);if(!row)throw Error('PRODUCTION_FOCUS_FRAME_GAP');
 const local=frame-row.startFrame,t=Math.min(1,local/Math.max(1,row.approachFrames-1)),flatBounds=interpolateProductionBounds(row.startBounds,row.targetBounds,t),
  moving=t<1&&!same(row.startBounds,row.targetBounds);
 return{...copy(row),frame,flatBounds,cameraLocked:!moving,settle:{locked:!moving,phase:moving?'CONSERVATIVE_EVENT_FOCUS_APPROACH':'EVENT_FOCUS_HOLD'},
  state:moving?'EVENT_FOCUS_APPROACH':'EVENT_FOCUS_HOLD',surveyAdmissionModified:false,localAdmissionGranted:false};
}
