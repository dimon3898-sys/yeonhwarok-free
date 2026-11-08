import {selectSealedOfficialCandidate} from './official_candidate_activation.mjs';
/** Fixed official worker transport. Not an operator/diagnostic factory route. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {capturePresentation} from './capture_presentation.mjs';
import {verifySceneChunk} from './sealed_scene_chunks.mjs';
import {continuityFor} from './presentation_timeline.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
export async function captureOfficialSceneChunk({packageFile,expectedSHA256,expectedOriginalSHA256,expectedSourceQualificationSHA256,outputRoot,depsRoot}={}){
 if(![expectedSHA256,expectedOriginalSHA256,expectedSourceQualificationSHA256].every(x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x)))throw Error('UP2_CHUNK_EXPECTED_PINS_REQUIRED');
 const raw=await readFile(packageFile);if(hash(raw)!==expectedSHA256)throw Error('UP2_CHUNK_PACKAGE_HASH');
 const envelope=JSON.parse(raw);if(envelope.schema!=='WORLD_ENGINE_OFFICIAL_SCENE_CHUNK_CAPTURE_V1')throw Error('UP2_CHUNK_CAPTURE_SCHEMA');
 verifySceneChunk(envelope.plan,envelope.chunk,expectedOriginalSHA256);
 const officialCandidate=await selectSealedOfficialCandidate({activation:envelope.candidateActivation,expectedActivationSHA256:envelope.candidateActivationSHA256,originalSHA256:expectedOriginalSHA256,chunkRequestSHA256:envelope.chunk.requestSHA256,nativeSourceQualificationSHA256:expectedSourceQualificationSHA256});
 const requestRaw=JSON.stringify(envelope.chunk.request),runtimeFile=packageFile+'.runtime.json';
 await writeFile(runtimeFile,requestRaw,{flag:'wx',mode:0o600});
 return capturePresentation({packageFile:runtimeFile,expectedSHA256:hash(requestRaw),expectedSourceQualificationSHA256,outputRoot,depsRoot,
  continuity:continuityFor(envelope.plan,envelope.chunk),officialCandidate});
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const allowed=new Set(['package','expected-sha256','expected-original-sha256','expected-source-qualification-sha256','output-root','deps-root']),args={};
 try{for(const value of process.argv.slice(2)){const match=/^--([^=]+)=(.+)$/.exec(value);if(!match||!allowed.has(match[1])||args[match[1]])throw Error('UP2_CHUNK_ARGUMENT');args[match[1]]=match[2];}
 await captureOfficialSceneChunk({packageFile:args.package,expectedSHA256:args['expected-sha256'],expectedOriginalSHA256:args['expected-original-sha256'],expectedSourceQualificationSHA256:args['expected-source-qualification-sha256'],outputRoot:args['output-root'],depsRoot:args['deps-root']});
 }catch(error){process.stderr.write(String(error.message)+'\n');process.exitCode=1;}
}
