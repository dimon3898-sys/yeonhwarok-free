/** Invoke the formal capture path in an isolated free CPU runner. */
import fs from'node:fs/promises';import path from'node:path';import{fileURLToPath}from'node:url';import{createHash}from'node:crypto';
import{capturePresentation}from'../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=path.dirname(fileURLToPath(import.meta.url)),packageFile=path.join(p,'REGISTERED_RUNTIME_REQUEST.json'),bytes=await fs.readFile(packageFile);
const receipt=await capturePresentation({packageFile,outputRoot:'/workspace/reference6s-probe',expectedSHA256:createHash('sha256').update(bytes).digest('hex'),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:[0,30,60,90,120,149,179]});
console.log(JSON.stringify({status:receipt.status,renderedFrames:receipt.renderedFrames,paidExecuted:receipt.paidExecuted}));
