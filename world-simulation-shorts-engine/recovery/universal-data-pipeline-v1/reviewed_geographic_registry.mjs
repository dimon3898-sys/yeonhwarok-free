// Server-owned exact dataset binding. Modern geometry only; no historical control.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const raw=fs.readFileSync(new URL('./evidence/REVIEWED_GEOGRAPHIC_CONTEXT.json',import.meta.url));
if(createHash('sha256').update(raw).digest('hex')!=='957e3de8fc284dfcef65180d18471ac9151dacaff64df5f87b15d663782b7f84')throw Error('EVIDENCE_GEOGRAPHIC_REGISTRY_MISMATCH');
export function reviewedGeographicRecords(){return structuredClone(JSON.parse(raw).records);}
