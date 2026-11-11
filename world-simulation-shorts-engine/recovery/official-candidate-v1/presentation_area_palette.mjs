/** Optional per-area presentation colors. Ownership still requires source data. */
const copy=value=>structuredClone(value),own=(value,key)=>value!==null&&typeof value==='object'&&Object.hasOwn(value,key);
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const rgba=value=>Array.isArray(value)&&value.length===4&&value.every(x=>Number.isFinite(x)&&x>=0&&x<=1)&&value[3]>=.08&&value[3]<=.6;
const fail=code=>{throw Error(code);};

export function validatePresentationAreaColors(colors,scene){
 if(scene?.control_timeline_ref!==undefined){
  const owners=scene.control_timeline_ref.ownerIds;
  if(!object(colors)||!Array.isArray(owners)||Object.keys(colors).length!==owners.length
   ||!owners.every(owner=>own(colors,owner)&&rgba(colors[owner])))fail('PRESENTATION_CONTROL_OWNER_COLORS_REQUIRED');
  return;
 }
 if(colors===undefined)return;
 if(!object(colors)||Object.keys(colors).length>64)fail('PRESENTATION_AREA_PALETTE_INVALID');
 const areas=new Set((scene?.areas??[]).map(area=>area.id));
 for(const [id,color]of Object.entries(colors))if(!areas.has(id)||!rgba(color))fail('PRESENTATION_AREA_COLOR_BINDING_INVALID');
}

/** Per-area explicit color wins; absent entries preserve the original state palette. */
export function resolvePresentationAreaColor(presentation,area,defaultColor){
 const color=own(presentation?.areaColors,area.id)?presentation.areaColors[area.id]
  :own(presentation?.territoryColors,area.state_id)?presentation.territoryColors[area.state_id]:defaultColor;
 return color===undefined?undefined:copy(color);
}

/** Keep paint order: non-adjacent same-color polygons are never reordered. */
export function groupPresentationAreasByColor(areas,presentation,defaultColor){
 // Omitted optional palette keeps the exact legacy first-seen state grouping.
 if(presentation?.areaColors===undefined){
  const byState=new Map();
  for(const area of areas){const stateId=area.state_id??'__DEFAULT__';
   if(!byState.has(stateId))byState.set(stateId,{key:stateId,stateId,color:resolvePresentationAreaColor(presentation,area,defaultColor),areas:[]});
   byState.get(stateId).areas.push(area);
  }
  return byState.size?[...byState.values()]:[{key:'__DEFAULT__',stateId:'__DEFAULT__',color:copy(defaultColor),areas:[]}];
 }
 const groups=[];
 for(const area of areas){
  const stateId=area.state_id??'__DEFAULT__',color=resolvePresentationAreaColor(presentation,area,defaultColor),
   key=JSON.stringify([stateId,color]),last=groups.at(-1);
  if(last?.key===key)last.areas.push(area);
  else groups.push({key,stateId,color,areas:[area]});
 }
 return groups.length?groups:[{key:JSON.stringify(['__DEFAULT__',defaultColor]),stateId:'__DEFAULT__',color:copy(defaultColor),areas:[]}];
}

/** Match source-ordered areas across a cut, even when local area/state IDs differ. */
export function bindPresentationBoundaryAreaColors(records,areaRows,stateId,presentation){
 if(records.length!==areaRows.length)fail('PRESENTATION_BOUNDARY_GEOMETRY_REQUIRED');
 return records.map((record,index)=>{
  const color=resolvePresentationAreaColor(presentation,{id:areaRows[index].id,state_id:stateId});
  if(color===undefined)fail('PRESENTATION_CONTINUITY_EXPLICIT_STATE_COLOR_REQUIRED');
  return{...copy(record),color};
 });
}
