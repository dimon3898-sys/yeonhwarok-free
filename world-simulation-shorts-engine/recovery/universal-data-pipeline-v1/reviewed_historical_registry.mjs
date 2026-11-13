// Server-owned reviewed reconstructions. Dataset-specific material belongs only in data.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const raw=fs.readFileSync(new URL('./evidence/REVIEWED_HISTORICAL.json',import.meta.url));
export const reviewedHistoricalRegistrySHA256='3474d66d3b5ebd5e32206b523523e9002c587b9de3664e9b12235c72ade1e87e';
if(createHash('sha256').update(raw).digest('hex')!==reviewedHistoricalRegistrySHA256)throw Error('EVIDENCE_HISTORICAL_REGISTRY_MISMATCH');
const data=JSON.parse(raw);
if(data.schema!=='REVIEWED_HISTORICAL_RECONSTRUCTIONS_V1'||!Array.isArray(data.records))throw Error('EVIDENCE_HISTORICAL_REGISTRY_SCHEMA');
export function reviewedHistoricalRecords(){return structuredClone(data.records);}
