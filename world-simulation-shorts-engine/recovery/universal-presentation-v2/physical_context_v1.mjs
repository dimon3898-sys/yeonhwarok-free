/** Source-derived, approximate physical context. Never political/historical borders. */
import {validateLabelText} from './presentation_labels.mjs';
import {geographicCameraFrame} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
export const PHYSICAL_CONTEXT_SHA256='bc71dc38a4b394558e33818cccf212578cbbd51726a1fc4edc79c7fcedc6b8f5';
export async function loadPhysicalContext(presentation,totalFrames){
 if(presentation.mapStyle?.physicalContext!=='NATURAL_EARTH_V1')return null;
 const response=await fetch(new URL('./sources/physical-context/context.json',import.meta.url));
 if(!response.ok)throw Error('PHYSICAL_CONTEXT_SOURCE_UNAVAILABLE');
 const bytes=await response.arrayBuffer(),sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
 if(sha!==PHYSICAL_CONTEXT_SHA256)throw Error('PHYSICAL_CONTEXT_HASH_CHANGED');
 const data=JSON.parse(new TextDecoder().decode(bytes));
 const views=[presentation.camera.frames[0],presentation.camera.frames.at(-1)].map(geographicCameraFrame);
 const candidates=data.physicalLabels.filter(row=>{
  try{validateLabelText(row.text);}catch{return false;}
  return views.every(view=>{const [x,y]=view.project(row.anchor);return x>140&&x<940&&y>300&&y<1300;});
 }).sort((a,b)=>a.rank-b.rank||a.id.localeCompare(b.id));
 const chosen=[];
 for(const row of candidates){if(chosen.length>=2)break;const q=views[0].project(row.anchor);if(chosen.every(x=>{const a=views[0].project(x.anchor);return Math.hypot(q[0]-a[0],q[1]-a[1])>250;}))chosen.push(row);}
 return{source:data.sourceURL,sourceSHA256:data.sourceSHA256,derivedSHA256:sha,precision:data.precision,
  labels:chosen.map(row=>({id:row.id,locationId:row.id,role:'PHYSICAL',text:row.text,anchor:row.anchor,startFrame:0,endFrame:totalFrames,revealFrames:1,exitFrames:1,priority:10})),
  locations:chosen.map(row=>({id:row.id,label:row.text,anchor:row.anchor})),
  lines:data.continentSeams.map(row=>({...row,alpha:.65,semantics:'APPROXIMATE_PHYSICAL_DIVIDE_NOT_POLITICAL_BORDER'}))};
}
