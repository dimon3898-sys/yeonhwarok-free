// Server-owned source registry. Never read a request-supplied path or trust flag.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const raw=fs.readFileSync(new URL('./evidence/REVIEWED_CONTEXT.json',import.meta.url));
export const reviewedContextRegistrySHA256='015f951a4dddccbfce10a7e72eb4b33e02d894305c238566806dff7273ae19e8';
if(createHash('sha256').update(raw).digest('hex')!==reviewedContextRegistrySHA256)throw Error('EVIDENCE_SOURCE_MISMATCH');
const records=JSON.parse(raw).records;
export function reviewedContextRecords(){return structuredClone(records);}
