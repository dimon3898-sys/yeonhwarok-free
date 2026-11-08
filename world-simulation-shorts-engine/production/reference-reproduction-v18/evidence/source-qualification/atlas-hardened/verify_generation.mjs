import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {parsePaths} from './cli_paths.mjs';
const options=parsePaths();
if(options.checkPaths){console.log(JSON.stringify(options));process.exit(0);}
const {verifyCandidateFiles}=await import(pathToFileURL(options.validator).href);
const root=options.outputRoot+path.sep;
const hash=b=>createHash('sha256').update(b).digest('hex');
const requireTrue=(v,m)=>{if(!v)throw new Error(m);};
const read=async name=>JSON.parse(await readFile(root+name,'utf8'));
const index=await read('GENERATION_INDEX.json');
for(const [name,r] of Object.entries(index.files)){
 requireTrue(!name.includes('/')&&!name.includes('..'),'Unsafe generation path');
 const b=await readFile(root+name);requireTrue(b.length===r.bytes&&hash(b)===r.sha256,'Generation artifact hash mismatch: '+name);
}
const evidence=await read('SOURCE_ARRAY_EVIDENCE.json');
requireTrue(index.sourceEvidenceSha256===hash(await readFile(root+'SOURCE_ARRAY_EVIDENCE.json')),'Evidence index not bound');
const declared=new Map(evidence.sources.map(s=>[s.source.id,s.source]));
const results=[];
for(let i=1;i<=4;i++){
 const m=await read(`segment${i}_manifest.json`),receiptNames=new Map(m.receipts.map(r=>[r.sha256,r.file]));
 for(const p of m.products){
  const r=await read(receiptNames.get(p.provenance.acquisitionReceiptSha256));
  requireTrue(r.sourceEvidenceSha256===index.sourceEvidenceSha256&&receiptNames.get(r.sourceEvidenceSha256)==='SOURCE_ARRAY_EVIDENCE.json','Unbound transitive source evidence');
  const u=await read(receiptNames.get(p.provenance.upstreamManifestSha256));
  for(const source of u.sources){
   if(source.id==='baseline_pinned_png'){
    requireTrue(source.sourceWholeFileSha256===evidence.baselineMaterialization.sourceOriginalSha256&&evidence.baselineMaterialization.derivedPngSha256===evidence.baselineCatalog.sha256,'Baseline derivation unbound');
   }else requireTrue(JSON.stringify(source)===JSON.stringify(declared.get(source.id)),'Upstream source differs from evidence index');
  }
 }
 results.push({segment:i,...await verifyCandidateFiles(m,{root})});
}
// Verification report stays outside the immutable generation.
await writeFile(options.report,JSON.stringify({status:'QUALIFICATION_REQUIRED',productionAdmitted:false,transitiveBindingsChecked:true,acquisitionAuthenticity:'PENDING',results},null,2)+'\n');
console.log('4 candidate manifests and generation/evidence bindings verified; production remains blocked.');
