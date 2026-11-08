import path from 'node:path';
import {fileURLToPath} from 'node:url';
export function parsePaths(argv=process.argv.slice(2),env=process.env){
 const code=path.dirname(fileURLToPath(import.meta.url));
 const result={outputRoot:env.WORLD_ENGINE_OUTPUT_ROOT||path.join(code,'generation1'),validator:env.WORLD_ENGINE_CANDIDATE_VALIDATOR||path.join(code,'../../../source-candidate-contract/derived_source_manifest.mjs'),report:null,checkPaths:false};
 const names={'--output-root':'outputRoot','--validator':'validator','--report':'report'};
 for(let i=0;i<argv.length;i++){
  if(argv[i]==='--check-paths'){result.checkPaths=true;continue;}
  const k=names[argv[i]];if(!k||!argv[i+1]||argv[i+1].startsWith('--'))throw new Error('Unknown or incomplete option: '+argv[i]);result[k]=argv[++i];
 }
 result.outputRoot=path.resolve(result.outputRoot);result.validator=path.resolve(result.validator);result.report=path.resolve(result.report||path.join(path.dirname(result.outputRoot),'VALIDATION_RESULTS.json'));
 const rel=path.relative(result.outputRoot,result.report);if(!rel.startsWith('..'+path.sep)&&rel!=='..'&&!path.isAbsolute(rel))throw new Error('Report must stay outside immutable generation');
 return result;
}
