// Authoring step for the exact, source-reviewed illustrative sample. Not a
// runtime approval endpoint. Changing inputs requires another source review.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const here=path.dirname(fileURLToPath(import.meta.url));
const runtime=path.resolve(here,'../../recovery/universal-data-pipeline-v1');
const canonical=x=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}':JSON.stringify(x);
const sha=x=>createHash('sha256').update(typeof x==='string'||Buffer.isBuffer(x)?x:canonical(x)).digest('hex');
const write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n');
const packet={schema:'WORLD_ENGINE_REVIEWED_GEOGRAPHIC_EVENT_CONTEXT_V1',reviewedAt:'2026-11-07',reviewer:'Codex source review under user-directed production preparation',reviewType:'Source comparison and exact dataset binding; not professional historical front reconstruction',
  sourceChecks:[
    {url:'https://unarchives.mpva.go.kr/contents/map',publisher:'Ministry of Patriots and Veterans Affairs, Republic of Korea',accessed:'2026-11-06',claims:['Naktong defense preceded Incheon landing','Incheon landing began 1950-09-15','Landing forces advanced toward Seoul','Seoul recapture 1950-09-28'],rawWebsiteBytesArchived:false},
    {url:'https://theme.archives.go.kr/next/chronology/yearRecord.do?archiveEvntId=0049286404&year=1950',publisher:'National Archives of Korea',claims:['1950-09-15 Incheon landing','1950-09-28 Seoul recapture'],rawWebsiteBytesArchived:false},
    {repository:'dimon3898-sys/yeonhwarok-free',commit:'bbd2ff9b783d00da208a6296e91183b32905373c',source:'Natural Earth geographic context',countryRepository:'nvkelso/natural-earth-vector',countryCommit:'ca96624a56bd078437bca8184e78163e5039ad19',countryBlob:'5ebc66e25fc1af01edaebe9375c546655e04cf1e',cityBlob:'4da9c6b27b5cd41d7c930ea9cd0c1f84548b65fb',method:'Selected original named city coordinates; country shared-edge cancellation only',historicalCoastlineAccuracyClaimed:false}
  ],
  verifiedCities:JSON.parse(fs.readFileSync(path.join(here,'sources/CITY_CONTEXT.json'))).features.map(f=>({name:f.properties.name,ne_id:f.properties.ne_id,coordinates:f.geometry.coordinates})),
  scope:{geography:'Static modern generalized peninsula context; not 1950 coastline or occupied territory',dates:'Event dates and authored display intervals only; no dated military geometry',line:'Straight city-to-city direction diagram labeled as approximate; not troop track or road',naktong:'Daegu regional context pin; not a surveyed defensive-line point',unavailable:['September front polygon','Daily control areas','Georeferenced landing sea approach','Exact troop track'],historicalOwnershipAllowed:false},
  geographicDerivation:JSON.parse(fs.readFileSync(path.join(here,'sources/GEOGRAPHIC_DERIVATION.json'))),
  provenance:'The SHA binds this review packet, not the unarchived official HTML. Geographic original identities are listed separately.'};
write(path.join(here,'sources/SOURCE_REVIEW.json'),packet);
const packetSha=sha(fs.readFileSync(path.join(here,'sources/SOURCE_REVIEW.json')));
const records=[];
for(let clip=1;clip<=2;clip++){
  const p=path.join(here,`KOREAN_WAR_20S_PART_${String(clip).padStart(2,'0')}.json`),input=JSON.parse(fs.readFileSync(p));
  for(const row of input.data.scenes){
    for(const src of row.facts.source_notes){src.sha256=packetSha;if(!src.note.includes('SHA256 identifies'))src.note+=' SHA256 identifies the authored SOURCE_REVIEW.json packet, not original website HTML. Original geographic blobs are separately identified.';}
    const factSha=sha(row.facts);row.historicalEvidence=[];
    for(const src of row.facts.source_notes){
      const geo=src.id==='PINNED_GEOGRAPHIC_CONTEXT',id='KW20_CONTEXT_DETAIL_V2_'+row.sceneId.toUpperCase()+'_'+(geo?'GEO':'EVENT');
      const geometries=row.facts.geometries.filter(g=>g.source_id===src.id);
      const claimId=geo?'UNCHANGED_GEOGRAPHIC_CONTEXT':'REVIEWED_EVENT_CHRONOLOGY_AND_DIRECTION_DIAGRAM';
      records.push({id,sourceId:src.id,claimId,sourceSHA256:src.sha256,sourceReference:src.source_reference,canonicalFactsSHA256:factSha,geometrySHA256ById:Object.fromEntries(geometries.map(g=>[g.id,sha(g.geometry)])),applicableDates:row.facts.time_range,scope:geo?'GEOGRAPHIC_CONTEXT':'EVENT_DIRECTION_DIAGRAM',reviewStatus:'VERIFIED',historicalOwnershipAllowed:false,geometryMeaning:geo?'UNCHANGED_MODERN_LAND_CONTEXT':'LABELED_DIRECTION_NOT_ACTUAL_TROOP_ROUTE',reviewPacketSHA256:packetSha,stageDateMeaning:'Authored geographic emphasis interval; not observed ownership or troop position'});
      // Existing gate uses start/end names for the reviewed interval.
      row.historicalEvidence.push({recordId:id,sourceId:src.id,claimId,geometryIds:geometries.map(g=>g.id),stageIds:geo?[]:row.facts.stages.map(s=>s.id)});
    }
  }
  write(p,input);
}
fs.mkdirSync(path.join(runtime,'evidence'),{recursive:true});
const registry=path.join(runtime,'evidence/REVIEWED_CONTEXT.json');
const prior=JSON.parse(fs.readFileSync(registry));
const retained=prior.records.filter(r=>!r.id.startsWith('KW20_CONTEXT_DETAIL_V2_'));
write(registry,{...prior,records:[...retained,...records]});
const registrySha=sha(fs.readFileSync(registry));
fs.writeFileSync(path.join(runtime,'reviewed_context_registry.mjs'),`// Server-owned source registry. Never read a request-supplied path or trust flag.\nimport fs from 'node:fs';\nimport {createHash} from 'node:crypto';\nconst raw=fs.readFileSync(new URL('./evidence/REVIEWED_CONTEXT.json',import.meta.url));\nexport const reviewedContextRegistrySHA256='${registrySha}';\nif(createHash('sha256').update(raw).digest('hex')!==reviewedContextRegistrySHA256)throw Error('EVIDENCE_SOURCE_MISMATCH');\nconst records=JSON.parse(raw).records;\nexport function reviewedContextRecords(){return structuredClone(records);}\n`);
write(path.join(here,'sources/REGISTRY_RECEIPT.json'),{reviewPacketSHA256:packetSha,serverRegistrySHA256:registrySha,recordCount:records.length,callerControlled:false,fullTerritoryApproved:false,gpuApproved:false});
console.log(JSON.stringify({recordCount:records.length,registrySha,packetSha}));
