// Server-owned exact dataset binding. Modern geometry only; no historical control.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const raw=fs.readFileSync(new URL('./evidence/REVIEWED_GEOGRAPHIC_CONTEXT.json',import.meta.url));
if(createHash('sha256').update(raw).digest('hex')!=='2ee6c011d6c971e0f1d0e91768d4beb6a60fa97f01eb03540af8d46f2b5d4cde')throw Error('EVIDENCE_GEOGRAPHIC_REGISTRY_MISMATCH');
export function reviewedGeographicRecords(){return structuredClone(JSON.parse(raw).records);}
