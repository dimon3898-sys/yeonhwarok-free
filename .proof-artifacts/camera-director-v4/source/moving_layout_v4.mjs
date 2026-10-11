/** Consume frozen measured Universal Layout candidates; never alter camera or style. */
export const MOVING_LAYOUT_V4_VERSION='GEOGRAPHIC_LAYOUT_CONSUMER_V4';
const copy=v=>structuredClone(v);
const freeze=v=>{if(v&&typeof v==='object'&&!Object.isFrozen(v)){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const finiteBox=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[2]>0&&b[3]>0;
const expand=(b,p)=>[b[0]-p,b[1]-p,b[2]+p*2,b[3]+p*2];
const overlap=(a,b)=>a[0]<b[0]+b[2]&&a[0]+a[2]>b[0]&&a[1]<b[1]+b[3]&&a[1]+a[3]>b[1];
const safeBox=(b,s)=>b[0]>=s[0]&&b[1]>=s[1]&&b[0]+b[2]<=s[2]&&b[1]+b[3]<=s[3];
const corners=b=>[[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]];
const protectedBox=i=>i.kind==='TEXT'?expand(i.inkBox,(i.outlineRadius??i.metrics?.outlineRadius??0)+2):i.box;
const roleKey={COUNTRY:'country',MARKER:'marker',LOCATION_LABEL:'location',EVENT_TITLE:'title',TITLE_CONTRAST_PANEL:'title',SCENARIO_DISCLOSURE:'disclosure'};
function polygons(record){
 const g=record.geometry??record,type=record.geometry_type??g.type,c=g.coordinates??record.coordinates;
 return type==='Polygon'?[c]:type==='MultiPolygon'?c:[];
}
function inRing(point,ring){
 let inside=false;
 for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[i],b=ring[j];
  if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }
 return inside;
}
function inPolygon(point,poly){return inRing(point,poly[0])&&!poly.slice(1).some(r=>inRing(point,r));}
function segmentHitsBox(a,b,box){
 const [left,top,width,height]=box,right=left+width,bottom=top+height,d=[b[0]-a[0],b[1]-a[1]];
 let enter=0,exit=1;
 for(const [p,q]of[[-d[0],a[0]-left],[d[0],right-a[0]],[-d[1],a[1]-top],[d[1],bottom-a[1]]]){
  if(p===0){if(q<0)return false;continue;}
  const t=q/p;if(p<0)enter=Math.max(enter,t);else exit=Math.min(exit,t);if(enter>exit)return false;
 }
 return true;
}
function ringHitsBox(ring,box){
 for(let i=1;i<ring.length;i++)if(segmentHitsBox(ring[i-1],ring[i],box))return true;
 return ring.length>2&&segmentHitsBox(ring.at(-1),ring[0],box);
}
const inverse=(p,b,[w,h])=>[b[0]+p[0]/w*(b[2]-b[0]),b[3]-p[1]/h*(b[3]-b[1])];
const screen=(p,b,[w,h])=>[(p[0]-b[0])/(b[2]-b[0])*w,(b[3]-p[1])/(b[3]-b[1])*h];
function geographicBox(box,bounds,output){
 const a=inverse([box[0],box[1]+box[3]],bounds,output),c=inverse([box[0]+box[2],box[1]],bounds,output);
 return[a[0],a[1],c[0]-a[0],c[1]-a[1]];
}

/** Glyph dimensions/candidates come from the unchanged Universal Layout once. */
export function compileMovingLayoutContract({regionalPlan,measuredLayout}={}){
 const items=Array.isArray(measuredLayout)?measuredLayout:measuredLayout?.items??measuredLayout?.layout;
 if(!Array.isArray(items)||!items.length)throw Error('MOVING_LAYOUT_ACTUAL_MEASURED_ITEMS_REQUIRED');
 const finalBounds=regionalPlan?.framing?.bounds,output=regionalPlan?.layout?.canonical??[1080,1920],safe=regionalPlan?.layout?.safe??[48,72,1032,1848];
 if(!Array.isArray(finalBounds)||finalBounds.length!==4||!finalBounds.every(Number.isFinite))throw Error('MOVING_LAYOUT_APPROVED_FRAMING_REQUIRED');
 if(items.some(i=>!finiteBox(i.box)||i.kind==='TEXT'&&!finiteBox(i.inkBox)))throw Error('MOVING_LAYOUT_ACTUAL_GLYPH_BOUNDS_REQUIRED');
 const original=copy(items),marker=original.find(i=>i.role==='MARKER');
 if(!marker)throw Error('MOVING_LAYOUT_GEOGRAPHIC_MARKER_REQUIRED');
 const anchor=copy(marker.geographicAnchor??regionalPlan.anchor?.coordinates);
 if(!Array.isArray(anchor)||anchor.length!==2||!anchor.every(Number.isFinite))throw Error('MOVING_LAYOUT_EVENT_ANCHOR_REQUIRED');
 const markerCenter=[marker.box[0]+marker.box[2]/2,marker.box[1]+marker.box[3]/2];
 const bindings=original.map((item,index)=>{
  if(item.role==='COUNTRY'){
   const center=[item.inkBox[0]+item.inkBox[2]/2,item.inkBox[1]+item.inkBox[3]/2];
   return{index,role:item.role,geographicAnchor:inverse(center,finalBounds,output),candidate:item.placement?.candidate??'MEASURED_PRIMARY_INTERIOR'};
  }
  if(item.role==='LOCATION_LABEL'){
   const candidate=item.placement?.candidate;
   if(!['LEFT','RIGHT','ABOVE','BELOW'].includes(candidate))throw Error('MOVING_LAYOUT_MEASURED_LOCATION_CANDIDATE_REQUIRED');
   return{index,role:item.role,candidate,offset:[item.box[0]-markerCenter[0],item.box[1]-markerCenter[1]]};
  }
  return{index,role:item.role,candidate:item.placement?.candidate??'GEOGRAPHIC_ANCHOR'};
 });
 const records=(regionalPlan.geometries??[]).filter(r=>r.id===regionalPlan.primary||(regionalPlan.secondary??[]).includes(r.id)).map(r=>({id:r.id,role:r.id===regionalPlan.primary?'PRIMARY':'SECONDARY',polygons:copy(polygons(r))}));
 if(!records.some(r=>r.role==='PRIMARY'&&r.polygons.length))throw Error('MOVING_LAYOUT_REAL_PRIMARY_POLYGON_REQUIRED');
 return freeze({version:MOVING_LAYOUT_V4_VERSION,finalBounds:copy(finalBounds),canonicalOutput:copy(output),safeArea:copy(safe),
  primaryRegionId:regionalPlan.primary,eventAnchor:anchor,markerSize:marker.box[2],items:original,bindings,records,
  boundaryTheme:copy(regionalPlan.theme),candidatePolicy:'Unchanged measured Universal Layout candidates latched for the geographic beat',
  finalPreservation:'Original measured boxes returned exactly at the approved endpoint'});
}

/** Random-access layout: only geographic projection and approved scale size vary. */
export function evaluateMovingLayout(contract,cameraState,{markerSize=contract.markerSize,boundaryTokens={}}={}){
 if(contract?.version!==MOVING_LAYOUT_V4_VERSION)throw Error('MOVING_LAYOUT_COMPILED_CONTRACT_REQUIRED');
 const bounds=cameraState?.camera?.flatBounds??cameraState?.extent;
 if(!Array.isArray(bounds)||bounds.length!==4||!bounds.every(Number.isFinite)||bounds[2]<=bounds[0]||bounds[3]<=bounds[1])throw Error('MOVING_LAYOUT_CAMERA_EXTENT_REQUIRED');
 if(!Number.isFinite(markerSize)||markerSize<=0)throw Error('MOVING_LAYOUT_MARKER_SIZE_REQUIRED');
 const final=equal(bounds,contract.finalBounds),output=contract.canonicalOutput,anchor=screen(contract.eventAnchor,bounds,output),delta=(markerSize-contract.markerSize)/2;
 const items=copy(contract.items);
 if(!final)for(const binding of contract.bindings){
  const item=items[binding.index],original=contract.items[binding.index];let origin;
  if(item.role==='MARKER'){
   item.box=[anchor[0]-markerSize/2,anchor[1]-markerSize/2,markerSize,markerSize];item.anchor=[...anchor];continue;
  }
  if(item.role==='COUNTRY'){
   const center=screen(binding.geographicAnchor,bounds,output),alpha=original.alphaBounds??original.metrics?.alphaBounds;
   if(!alpha)throw Error('MOVING_LAYOUT_ACTUAL_ALPHA_BOUNDS_REQUIRED');
   origin=[center[0]-original.inkBox[2]/2-alpha[0],center[1]-original.inkBox[3]/2-alpha[1]];
   if(item.placement)item.placement.anchor=[...center];
  }else if(item.role==='LOCATION_LABEL'){
   origin=[anchor[0]+binding.offset[0],anchor[1]+binding.offset[1]];
   if(binding.candidate==='LEFT')origin[0]-=delta;if(binding.candidate==='RIGHT')origin[0]+=delta;
   if(binding.candidate==='ABOVE')origin[1]-=delta;if(binding.candidate==='BELOW')origin[1]+=delta;
   if(item.placement)item.placement.anchor=[...anchor];
  }
  if(origin){const dx=origin[0]-original.box[0],dy=origin[1]-original.box[1];item.box=[...origin,original.box[2],original.box[3]];
   item.inkBox=[original.inkBox[0]+dx,original.inkBox[1]+dy,original.inkBox[2],original.inkBox[3]];}
 }
 // Exact final marker size is part of the approved Scale endpoint contract.
 if(final&&Math.abs(markerSize-contract.markerSize)>1e-9)throw Error('MOVING_LAYOUT_FINAL_MARKER_SIZE_MISMATCH');
 const theme={...contract.boundaryTheme,...boundaryTokens},failures={country:[],marker:[],location:[],title:[],disclosure:[]};
 const boxes=items.map((item,index)=>({item,index,key:roleKey[item.role],box:protectedBox(item)}));
 const primary=contract.records.filter(r=>r.role==='PRIMARY');
 for(const record of boxes){
  const {item,key,box}=record;if(!key)continue;
  if(!safeBox(item.box,contract.safeArea)||!safeBox(box,contract.safeArea))failures[key].push({code:'SAFE_AREA',role:item.role});
  if(item.kind==='TEXT'){
   const geo=geographicBox(box,bounds,output);
   if(item.role==='COUNTRY'){
    const points=[...corners(geo),[geo[0]+geo[2]/2,geo[1]+geo[3]/2]];
    if(!points.every(p=>primary.some(r=>r.polygons.some(poly=>inPolygon(p,poly))))||primary.some(r=>r.polygons.some(poly=>poly.some(ring=>ringHitsBox(ring,geo)))))failures[key].push({code:'PRIMARY_INTERIOR',role:item.role});
   }
   // The frozen Universal Layout protects disclosure with safe-area/collision
   // checks only. It does not exclude background boundary crossings.
   for(const region of item.role==='SCENARIO_DISCLOSURE'?[]:contract.records){
    const edge=region.role==='PRIMARY'?theme.primaryEdgeWidth??theme.primaryWidth+2:theme.secondaryEdgeWidth??theme.secondaryWidth+2;
    const clearance=item.role==='COUNTRY'?edge/2+1:region.role==='PRIMARY'?Math.max(8,edge/2+(theme.glowRadius??0)*2):Math.max(6,edge/2+3);
    const guard=geographicBox(expand(box,clearance),bounds,output);
    if(region.polygons.some(poly=>poly.some(ring=>ringHitsBox(ring,guard))))failures[key].push({code:'BOUNDARY_CLEARANCE',role:item.role,regionId:region.id});
   }
  }
 }
 const collisions=[];
 for(let a=0;a<boxes.length;a++)for(let b=a+1;b<boxes.length;b++){
  const aa=boxes[a],bb=boxes[b],ownTitle=aa.key==='title'&&bb.key==='title';
  if(ownTitle||!overlap(aa.box,bb.box))continue;
  collisions.push({first:aa.item.role,second:bb.item.role,firstBox:aa.box,secondBox:bb.box});
  // A hidden screen-fixed title cannot block early geographic information.
  // Its own gate checks all geographic roles at the locked endpoint instead.
  if(aa.key)failures[aa.key].push({code:'COLLISION',role:aa.item.role,other:bb.item.role,otherKey:bb.key});
  if(bb.key)failures[bb.key].push({code:'COLLISION',role:bb.item.role,other:aa.item.role,otherKey:aa.key});
 }
 const readiness=Object.fromEntries(Object.keys(failures).map(key=>[key,boxes.some(b=>b.key===key)&&!failures[key].some(f=>f.code!=='COLLISION'||key==='title'||f.otherKey!=='title')]));
 return{version:MOVING_LAYOUT_V4_VERSION,frame:cameraState.frame,items,readiness,
  choice:Object.fromEntries(contract.bindings.map(b=>[`${b.role}:${b.index}`,b.candidate])),
  eventAnchor:[...anchor],geographicAnchor:copy(contract.eventAnchor),projectedRegion:copy(cameraState.projectedRegion??null),
  validation:{safeArea:copy(contract.safeArea),failuresByRole:failures,collisions,valid:Object.values(failures).every(v=>!v.length),
   candidateChanges:0,finalBoxesExact:final&&equal(items.map(i=>i.box),contract.items.map(i=>i.box))},
  cameraChanged:false,styleChanged:false};
}

/** Validate visible roles only, without letting hidden title panels mask motion. */
export function validateVisibleMovingLayout(layout,reveal){
 const visible=key=>(reveal?.[key]??0)>0;
 const failures=[];
 for(const [key,list]of Object.entries(layout.validation.failuresByRole))if(visible(key))for(const failure of list){
  if(failure.code==='COLLISION'&&!visible(failure.otherKey))continue;
  failures.push({...failure,key});
 }
 return{valid:!failures.length,failures,candidateChanges:0,finalBoxesExact:layout.validation.finalBoxesExact};
}
