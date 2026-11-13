import fs from 'node:fs';import path from 'node:path';import {execFileSync} from 'node:child_process';import{fileURLToPath}from'node:url';
export function loadNative(){
 const p=path.dirname(fileURLToPath(import.meta.url)),e=path.resolve(p,'../../..'),repo=path.dirname(e),read=f=>JSON.parse(fs.readFileSync(f)),cat=read(path.join(e,'recovery/universal-presentation-v2/REGION_SOURCE_CATALOG.json'));
 const seed=JSON.parse(execFileSync('python',['-c','import zipfile,sys;sys.stdout.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]).decode())',path.join(repo,cat.seed.file),cat.seed.member],{maxBuffer:32*1024**2}));
 for(const g of read(path.join(p,'../sources/NATIVE_COUNTRY_OVERRIDES.json')).records){const i=seed.nativePlan.geometries.findIndex(r=>r.id===g.id);if(i<0)throw Error('MISSING_EXISTING_OVERRIDE');seed.nativePlan.geometries[i]=g;}
 return seed.nativePlan.geometries;
}
