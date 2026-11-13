/** Task data admission, not an animation generator. Reuses retained source bytes. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {canonicalJSON} from '../../recovery/universal-presentation-v2/region_source.mjs';
const base=new URL('./',import.meta.url),old=new URL('../mongol-empire-6s-20261113/',base);
const hash=x=>createHash('sha256').update(typeof x==='string'?x:canonicalJSON(x)).digest('hex');
const read=(root,name)=>JSON.parse(fs.readFileSync(new URL(name,root)));
const input=read(old,'MONGOL_EMPIRE_INPUT_CANDIDATE.json'),features=read(old,'source/CLIOPATRIA_MONGOL_1206_1259.geojson').features;
const facts=input.data.scenes[0].facts,src=facts.source_notes[0];
assert.equal(features.length,8);
Object.assign(src,{historical_validity:{start:'1206',end:'1259'},
 uncertainty:'Published reconstructed polity extents; spatial and temporal uncertainty; not surveyed borders, daily conquest events or campaign routes.',
 attribution:'Bennett et al. (2025), Cliopatria / Seshat Global History Databank, v0.2.1, CC BY 4.0; https://doi.org/10.1038/s41597-025-04516-9',
 note:'Faithful source reconstruction only. Original version and coordinates retained. Geometry validity is an inclusive source year interval; cross-fades are visual transitions, not inferred intermediate ownership. Display center is derived, not a historical settlement.'});
for(let i=0;i<features.length;i++){
 const f=features[i],g=facts.geometries[i];assert.deepEqual(g.geometry,f.geometry);
 g.validity={start:String(f.properties.FromYear),end:String(f.properties.ToYear)};
 facts.stages[i].date=structuredClone(g.validity);facts.stages[i].label=g.validity.start+'-'+g.validity.end;
}
const record={id:'HISTORICAL_RECONSTRUCTION_CLIOPATRIA_V021',sourceId:src.id,
 claimId:'PUBLISHED_RECONSTRUCTED_POLITY_EXTENTS_AND_YEAR_INTERVALS',reviewStatus:'VERIFIED',scope:'RECONSTRUCTED_TERRITORY',
 sourceReference:src.source_reference,sourceSHA256:src.original_sha256,canonicalFactsSHA256:hash(facts),
 applicableDates:src.historical_validity,uncertainty:src.uncertainty,license:src.license,
 reviewBasis:'Retained peer-reviewed dataset and prior source audit; exact eight geometry equality and source year intervals checked. Not independent certification of every historical border.',
 geometrySHA256ById:Object.fromEntries(facts.geometries.map(g=>[g.id,hash(g.geometry)])),
 geometryValidityById:Object.fromEntries(facts.geometries.map(g=>[g.id,g.validity]))};
input.data.scenes[0].historicalEvidence=[{recordId:record.id,sourceId:record.sourceId,claimId:record.claimId,geometryIds:facts.geometries.map(g=>g.id),stageIds:facts.stages.map(s=>s.id)}];
delete input.region;input.presentation={automatic:'HISTORICAL_STATES_V1'};
fs.writeFileSync(new URL('MONGOL_EMPIRE_SCENE_INPUT.json',base),JSON.stringify(input,null,2)+'\n');
fs.writeFileSync(new URL('HISTORICAL_EVIDENCE_REGISTRY.json',base),JSON.stringify({schema:'REVIEWED_HISTORICAL_RECONSTRUCTIONS_V1',records:[record]},null,2)+'\n');
console.log(JSON.stringify({sourceRows:8,sourceGeometryMutations:0,sourceRecollected:false,factsSHA256:record.canonicalFactsSHA256}));
