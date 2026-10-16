/** Presentation-only policy over supplied Area V3 geometry; no inferred ownership. */
export const PRODUCTION_VISUAL_VERSION='UNIVERSAL_PRODUCTION_VISUAL_V3';
const copy=value=>structuredClone(value),bounded=(v,min,max,label)=>{
 if(!Number.isFinite(v)||v<min||v>max)throw Error('PRODUCTION_VISUAL_'+label+'_RANGE');return v;};
const color=(value,label)=>{if(!Array.isArray(value)||value.length!==3||value.some(v=>!Number.isFinite(v)||v<0||v>1))
 throw Error('PRODUCTION_VISUAL_'+label+'_RGB_REQUIRED');return [...value];};
export function normalizeProductionVisualProfile(input={}){
 const profile={version:PRODUCTION_VISUAL_VERSION,
  territoryOpacity:bounded(input.territoryOpacity??.62,.24,.8,'TERRITORY_OPACITY'),
  frontCoreWidthPixels:bounded(input.frontCoreWidthPixels??4.8,2.5,7,'FRONT_WIDTH'),
  frontCoreColor:color(input.frontCoreColor??[1,.98,.91],'FRONT_CORE'),
  frontGlowColor:color(input.frontGlowColor??[1,.66,.16],'FRONT_GLOW'),
  frontGlowRadiusPixels:bounded(input.frontGlowRadiusPixels??10,3,16,'FRONT_RADIUS'),
  frontGlowGain:bounded(input.frontGlowGain??.42,.1,.65,'FRONT_GAIN'),
  cameraApproachFrames:input.cameraApproachFrames??48,
  existingNativeMarkerPolicy:'ORIGINAL_ART_ANCHOR_AND_SCALE_TOKENS',
  ownershipPolicy:'ONLY_EXPLICIT_SUPPLIED_AREA_BINDINGS_NO_COMPLEMENT',
  frontPolicy:'ORIGINAL_AREA_V3_CONTOUR_ON_EXACT_SUPPLIED_FRONT_LINE',
  scalarV2ClassifierReused:false};
 if(!Number.isSafeInteger(profile.cameraApproachFrames)||profile.cameraApproachFrames<12||profile.cameraApproachFrames>120)
  throw Error('PRODUCTION_VISUAL_APPROACH_FRAMES_RANGE');
 return Object.freeze(profile);
}
export function validateAreaColorBindings(bindings,legacyScene,palette={}){
 if(!Array.isArray(bindings)||bindings.length>64)throw Error('PRODUCTION_AREA_BINDINGS_REQUIRED');
 const known=new Set(legacyScene.areas.map(row=>row.id)),seen=new Set();
 return Object.freeze(bindings.map(row=>{
  const area=legacyScene.areas.find(item=>item.id===row?.areaId),step=legacyScene.time_steps.find(item=>item.id===row?.sourceStateId);
  if(!known.has(row?.areaId)||seen.has(row.areaId)||typeof row.factionId!=='string'||!row.factionId
   ||area?.geometry_ref!==row.sourceGeometryRef||!step?.area_ids.includes(row.areaId)
   ||row.enemyComplementAdmitted!==false||row.measuredMilitaryControl!==false
   ||!/^[a-f0-9]{64}$/.test(row.sourceProof?.factsSHA256??'')||!row.sourceProof?.fields?.length
   ||!legacyScene.source_notes.some(source=>source.id===area.source_id))throw Error('PRODUCTION_EXPLICIT_QUALIFIED_AREA_OWNER_REQUIRED');
  seen.add(row.areaId);return Object.freeze({...copy(row),sourceId:area.source_id,color:color(row.color??palette[row.colorRole],'TERRITORY')});
 }));
}
export function productionAreaStyle(profile,territoryColor=[.36,.47,.56]){
 if(profile?.version!==PRODUCTION_VISUAL_VERSION)throw Error('PRODUCTION_VISUAL_PROFILE_REQUIRED');
 const rgb=color(territoryColor,'TERRITORY'),transparent={fillColor:[0,0,0,0],coreColor:[0,0,0,0],width:0,
  glowColor:[0,0,0,0],glowRadius:0,glowGain:0};
 return {AREA:{...copy(transparent),fillColor:[...rgb,profile.territoryOpacity]},
  FRONT:{...copy(transparent),coreColor:[...profile.frontCoreColor,1],width:profile.frontCoreWidthPixels,
   glowColor:[...profile.frontGlowColor,1],glowRadius:profile.frontGlowRadiusPixels,glowGain:profile.frontGlowGain},
  IMPACT:copy(transparent),PROPAGATION:copy(transparent)};
}
/** The actual measured glyph must identify the supplied event, not only its date. */
export function productionEventAnnotationLabels({chapters,source,anchor}){
 if(!Array.isArray(chapters)||!chapters.length)throw Error('PRODUCTION_EVENT_CHAPTER_LABELS_REQUIRED');
 return chapters.map(chapter=>{
  if(typeof chapter.chapterId!=='string'||!chapter.chapterId||typeof chapter.displayLabel!=='string'||!chapter.displayLabel.trim()
   ||typeof chapter.title!=='string'||!chapter.title.trim())throw Error('PRODUCTION_EVENT_DATE_AND_TITLE_REQUIRED');
  return{id:chapter.chapterId,display_value:chapter.displayLabel,unit:chapter.title,source:copy(source),anchor:copy(anchor),
   expectedText:`${chapter.displayLabel} ${chapter.title}`};
 });
}
/** Derive free text bands from actual measured atlases. The original layout
 * owner still performs the final safe-area/collision decision for every anchor. */
export function productionAnnotationAnchors({atlasEnvelope,safeArea,preferredAnchor,protectedGraphics=[],boundarySegments=[],markerSize=40,gap=18}){
 const [width,height]=atlasEnvelope??[],safe=safeArea;
 if(![width,height].every(v=>Number.isSafeInteger(v)&&v>0)||!Array.isArray(safe)||safe.length!==4
  ||!safe.every(Number.isFinite)||!Array.isArray(preferredAnchor)||preferredAnchor.length!==2||!preferredAnchor.every(Number.isFinite))
  throw Error('PRODUCTION_MEASURED_ANNOTATION_INPUT_REQUIRED');
 if(width>safe[2]-safe[0]||height>safe[3]-safe[1])throw Error('PRODUCTION_ANNOTATION_ATLAS_EXCEEDS_SAFE_AREA');
 const boxes=[...protectedGraphics.map(row=>row.box),...boundarySegments.map(row=>[
  Math.min(row.a[0],row.b[0])-row.radiusPx,Math.min(row.a[1],row.b[1])-row.radiusPx,
  Math.max(row.a[0],row.b[0])+row.radiusPx,Math.max(row.a[1],row.b[1])+row.radiusPx])],
  overlaps=(a,b)=>a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1],
  left=safe[0]+2,right=safe[2]-width-2,top=safe[1]+2,bottom=safe[3]-height-2,
  xs=[left,Math.max(left,Math.min(right,preferredAnchor[0]-width/2)),right],ys=new Set([top,bottom]),edgeYs=new Set();
 // A half-line grid covers free horizontal bands; obstacle-edge positions also
 // retain thin valid bands without requiring a smaller or truncated glyph.
 const rowCount=Math.min(96,Math.max(1,Math.ceil((bottom-top)/Math.max(1,height/2))));
 for(let row=0;row<=rowCount;row++)ys.add(top+(bottom-top)*row/Math.max(1,rowCount));
 for(const box of boxes){for(const y of [box[1]-height-2,box[3]+2])if(y>=top&&y<=bottom)edgeYs.add(y);}
 for(const y of [...edgeYs].sort((a,b)=>Math.abs(a+height/2-preferredAnchor[1])-Math.abs(b+height/2-preferredAnchor[1])).slice(0,128))ys.add(y);
 const candidates=[];
 for(const y of ys)for(const x of xs){
  const box=[x,y,x+width,y+height];if(boxes.some(old=>overlaps(box,old)))continue;
  const distance=markerSize/2+gap,
   anchor=y+height+distance<=safe[3]?[x+width/2,y+height+distance]:[x+width/2,y-distance];
  if(anchor[1]<safe[1]||anchor[1]>safe[3])continue;
  candidates.push({anchor,score:Math.hypot(x+width/2-preferredAnchor[0],y+height/2-preferredAnchor[1])});
 }
 const seen=new Set();return candidates.sort((a,b)=>a.score-b.score).flatMap(row=>{
  const key=JSON.stringify(row.anchor);if(seen.has(key))return[];seen.add(key);return[row.anchor];}).slice(0,24);
}
/** Scene output clock remains independent of the explicitly sourced geometry clock. */
export function evaluateProductionGeometryClock(plan,globalFrame){
 const schedule=plan?.productionV3?.geometrySchedule;
 if(!Array.isArray(schedule)||!Number.isSafeInteger(globalFrame)||globalFrame<0||globalFrame>=plan.totalFrames)
  throw Error('PRODUCTION_GEOMETRY_SCHEDULE_REQUIRED');
 const row=schedule.find(item=>globalFrame>=item.startFrame&&globalFrame<item.endFrame);
 if(!row||!['ARRIVAL_NO_EVENT','REVEAL_SUPPLIED_SNAPSHOT','HOLD_SUPPLIED_SNAPSHOT','TRANSITION_SUPPLIED_SNAPSHOTS'].includes(row.mode))throw Error('PRODUCTION_BOUND_SOURCE_CLOCK_REQUIRED');
 if(row.mode==='ARRIVAL_NO_EVENT')return{...copy(row),globalFrame,sourceGeometryFrame:null,eventEnabled:false,
  clockPolicy:'ORIGINAL_ARRIVAL_WITHOUT_EVENT_GEOMETRY',coordinatesInterpolated:false,eventDateFrontPrecisionClaimed:false};
 if(![row.sourceStartFrame,row.sourceEndFrame].every(Number.isSafeInteger))throw Error('PRODUCTION_BOUND_SOURCE_CLOCK_REQUIRED');
 const progress=(globalFrame-row.startFrame)/Math.max(1,row.endFrame-row.startFrame-1),
  sourceGeometryFrame=row.endFrame-row.startFrame===1?row.sourceEndFrame:Math.round(row.sourceStartFrame+(row.sourceEndFrame-row.sourceStartFrame)*progress),
  legacy=plan.legacyScenePlan;
 if(sourceGeometryFrame<legacy.timing.event_start_frame||sourceGeometryFrame>=legacy.timing.total_frames
  ||row.mode==='HOLD_SUPPLIED_SNAPSHOT'&&row.sourceStartFrame!==row.sourceEndFrame)
  throw Error('PRODUCTION_GEOMETRY_CLOCK_OUTSIDE_SUPPLIED_SOURCE');
 return {...copy(row),globalFrame,sourceGeometryFrame,eventEnabled:true,clockPolicy:'EXPLICIT_SUPPLIED_SNAPSHOT_CLOCK_NOT_EVENT_DATE_BOUNDARY',
  coordinatesInterpolated:false,eventDateFrontPrecisionClaimed:false,snapshotDateMatchesEventDate:row.eventDateMatchesSnapshot===true,
  sourceClockQuantization:'EXPLICIT_NEAREST_VALIDATED_INTEGER_SOURCE_FRAME',continuous600SecondSourceAlphaClaimed:false};
}
