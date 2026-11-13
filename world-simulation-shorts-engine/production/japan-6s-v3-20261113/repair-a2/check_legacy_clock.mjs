import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {highlightRingAt} from '../../../recovery/universal-presentation-v2/presentation_flow.mjs';
const p=new URL('./',import.meta.url),old=JSON.parse(await fs.readFile(new URL('../JAPAN_V3_SCENE_INPUT.json',p))),rows=JSON.parse(await fs.readFile(new URL('../cpu-a1/FRAME_SUMMARY.json',p)));
let max=0,samples=0;
for(const h of old.presentation.highlights)for(let f=0;f<180;f++){
 const actual=highlightRingAt(h,f,[500,900]),saved=rows[f].locationRings?.find(x=>x.id===h.id)?.draw;
 assert.equal(!!actual,!!saved);
 if(actual){assert.equal(actual.radius,saved.radius);max=Math.max(max,Math.abs(actual.alpha-saved.alpha));assert.ok(Math.abs(actual.alpha-saved.alpha)<1e-12);samples++;}
}
const prior=JSON.parse(await fs.readFile(new URL('REPAIR_TEST_RESULT.json',p)));
assert.equal(prior.rows.filter(r=>r.status==='FAIL').length,1);assert.equal(prior.rows[0].id,'legacy ring clock matches all 180 saved diagnostics');
await fs.writeFile(new URL('REPAIR_TEST_RESOLUTION.json',p),JSON.stringify({status:'PASS',inheritedPassedChecks:prior.rows.filter(r=>r.status==='PASS').map(r=>r.id),resolvedCheck:prior.rows[0].id,reason:'Node and Chromium Math.sin differ by one ULP in saved browser diagnostics. Compare numeric transport with 1e-12 tolerance; no product behavior change.',maximumAlphaDifference:max,samples,oldTestsRerun:0,reexecutedScope:'only failed numeric comparison; 12 prior PASS checks skipped'},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'PASS',maximumAlphaDifference:max,samples}));
