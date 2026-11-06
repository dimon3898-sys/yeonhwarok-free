// Server-owned source registry. Never read a request-supplied path or trust flag.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const raw=fs.readFileSync(new URL('./evidence/REVIEWED_CONTEXT.json',import.meta.url));
export const reviewedContextRegistrySHA256='965c76d58095d6d40be848616753608d25ebf1cfb369a2618275fbe3f541696a';
if(createHash('sha256').update(raw).digest('hex')!==reviewedContextRegistrySHA256)throw Error('EVIDENCE_SOURCE_MISMATCH');
const records=JSON.parse(raw).records;
export function reviewedContextRecords(){return structuredClone(records);}
