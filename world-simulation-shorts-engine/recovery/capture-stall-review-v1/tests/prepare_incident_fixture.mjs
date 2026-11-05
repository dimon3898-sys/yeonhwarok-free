import fs from 'node:fs/promises';
import path from 'node:path';
import {prepareRuntimeRequest} from '../../codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs';
const [fixture,output]=process.argv.slice(2),root='/workspace/incident-private';
await fs.mkdir(root,{mode:0o700});
const request=JSON.parse(await fs.readFile(fixture,'utf8'));
if(request.sourceInputSHA256!=='ead4c4f8beb8b541aa221366cdb249f20253eb70a2866f377a784cadfb9bc7c7')throw Error('INCIDENT_INPUT_MISMATCH');
const prepared=await prepareRuntimeRequest({request,cacheRoot:path.join(root,'sources'),privateWorkspaceRoot:root,publicExportRoot:'/out'});
await fs.writeFile(output,JSON.stringify(prepared));
