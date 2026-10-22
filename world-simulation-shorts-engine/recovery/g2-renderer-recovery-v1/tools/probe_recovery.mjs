/** Bounded actual native draw probe; never creates an MP4 or a Studio success. */
import {probeRecovery} from '../capture_recovery.mjs';
const args={};
for(const arg of process.argv.slice(2)){
 const match=/^--(plan|expected-sha256|output-root|frames)=(.+)$/.exec(arg);
 if(!match||args[match[1]])throw Error('RECOVERY_PROBE_ARGUMENT_INVALID');args[match[1]]=match[2];
}
if(!args.plan||!args['expected-sha256']||!args['output-root'])throw Error('RECOVERY_PROBE_ARGUMENT_MISSING');
const frames=args.frames?.split(',').map(v=>/^\d+$/.test(v)?Number(v):NaN);
const report=await probeRecovery({planFile:args.plan,expectedSHA256:args['expected-sha256'],outputRoot:args['output-root'],...(frames?{frames}:{})});
process.stdout.write(JSON.stringify({status:report.status,actualDraws:report.frames.length,backend:report.runtime.backend,nvidiaVerified:false})+'\n');
