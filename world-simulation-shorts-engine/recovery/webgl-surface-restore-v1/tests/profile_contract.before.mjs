/** Pure versioned backend/authorization contract. No browser, GPU or API calls. */
import path from 'node:path';
import {createHash} from 'node:crypto';

export const PROFILE = 'GCUBE_NVIDIA_SIX_SECOND_REVIEW_V1';
export const PLAN_SCHEMA = 'WORLD_ENGINE_NVIDIA_PRESENTATION_PLAN_V1';
export const APPROVAL_SCHEMA = 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1';
const check=(value,code)=>{if(!value)throw Error(code);};
const plain=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&[Object.prototype,null].includes(Object.getPrototypeOf(value));
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const digest=value=>typeof value==='string'&&/^sha256:[a-f0-9]{64}$/.test(value);
const finiteJSON=(value,seen=new Set())=>{
 if(value===null||typeof value==='string'||typeof value==='boolean')return true;
 if(typeof value==='number')return Number.isFinite(value);
 if(!Array.isArray(value)&&!plain(value)||seen.has(value))return false;
 seen.add(value);const result=(Array.isArray(value)?value:Object.values(value)).every(v=>finiteJSON(v,seen));seen.delete(value);return result;
};
export const sha=value=>createHash('sha256').update(value).digest('hex');
export function canonicalJSON(value){
 check(finiteJSON(value),'HANDOFF_FINITE_JSON_REQUIRED');
 const serialize=v=>Array.isArray(v)?'['+v.map(serialize).join(',')+']':plain(v)?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+serialize(v[k])).join(',')+'}':JSON.stringify(v);
 return serialize(value);
}

export function selectBackend(environ={}){
 check(environ===process.env||plain(environ),'HANDOFF_BACKEND_ENV_INVALID');
 const selected=environ.GPU_BACKEND;
 if(selected===undefined)return 'swiftshader';
 check(selected==='swiftshader'||selected==='vulkan','HANDOFF_GPU_BACKEND_UNSUPPORTED');
 return selected;
}

const featureName=value=>value.split(/[<:]/,1)[0];
const stripped=new Set(['--no-sandbox','--disable-setuid-sandbox','--enable-unsafe-swiftshader',
 '--disable-gpu','--disable-gpu-compositing','--disable-gpu-rasterization',
 '--disable-webgl','--disable-webgl2','--enable-gpu','--enable-webgl',
 '--disable-software-rasterizer','--disable-vulkan-surface','--headless']);
const replacements=new Set(['--use-angle','--use-gl','--use-vulkan']);
const noBypass=new Set(['--disable-web-security','--allow-running-insecure-content',
 '--ignore-certificate-errors','--proxy-server','--host-resolver-rules']);

export function buildVulkanLaunchOptions(options,{uid=process.getuid?.(),rootTestOptIn=false,executablePath}={}){
 check(plain(options),'HANDOFF_BROWSER_OPTIONS_INVALID');
 check(Number.isInteger(uid)&&uid>=0&&typeof rootTestOptIn==='boolean','HANDOFF_BROWSER_IDENTITY_INVALID');
 check(uid!==0||rootTestOptIn,'HANDOFF_NONROOT_SANDBOX_REQUIRED');
 check(!rootTestOptIn||uid===0,'HANDOFF_ROOT_TEST_OPTIN_ROOT_ONLY');
 const executable=executablePath??options.executablePath;
 check(typeof executable==='string'&&path.isAbsolute(executable)&&!executable.includes('\0')&&!executable.split(path.sep).includes('..'),'HANDOFF_BROWSER_EXECUTABLE_INVALID');
 const args=options.args??[];
 check(Array.isArray(args)&&args.every(a=>typeof a==='string'&&!a.includes('\0')),'HANDOFF_BROWSER_ARGS_INVALID');
 check(options.ignoreDefaultArgs!==true&&(options.ignoreDefaultArgs===undefined||Array.isArray(options.ignoreDefaultArgs)&&options.ignoreDefaultArgs.every(a=>typeof a==='string')),'HANDOFF_BROWSER_DEFAULTS_REQUIRED');
 const result=[],enabled=[],disabled=[];
 for(let i=0;i<args.length;i++){
  const arg=args[i],equal=arg.indexOf('='),flag=equal<0?arg:arg.slice(0,equal);
  check(!noBypass.has(flag),'HANDOFF_BROWSER_SECURITY_BYPASS_FORBIDDEN');
  if(flag==='--enable-features'||flag==='--disable-features'||replacements.has(flag)){
   let value=equal<0?undefined:arg.slice(equal+1);
   if(value===undefined){check(i+1<args.length&&!args[i+1].startsWith('--'),'HANDOFF_BROWSER_OPTION_VALUE_REQUIRED');value=args[++i];}
   check(value.length>0,'HANDOFF_BROWSER_OPTION_VALUE_REQUIRED');
   if(flag==='--enable-features')enabled.push(...value.split(','));
   if(flag==='--disable-features')disabled.push(...value.split(','));
   continue;
  }
  if(!stripped.has(flag))result.push(arg);
 }
 const distinct=values=>[...new Set(values.filter(Boolean).filter(v=>featureName(v)!=='Vulkan'))];
 const features=distinct(enabled);features.push('Vulkan');
 const disable=distinct(disabled);
 if(disable.length)result.push('--disable-features='+disable.join(','));
 result.push('--headless=new','--enable-gpu','--enable-webgl','--use-gl=angle',
  '--use-angle=vulkan','--enable-features='+features.join(','),
  '--disable-software-rasterizer');
 if(rootTestOptIn)result.push('--no-sandbox');
 const launch={...options,executablePath:executable,headless:true,chromiumSandbox:!rootTestOptIn,args:result};
 return {options:launch,evidence:{backend:'vulkan',rootTestOnly:rootTestOptIn,
  sandbox:rootTestOptIn?'EXPLICIT_ROOT_TEST_ONLY':'CHROMIUM_SANDBOX',selectedArgs:[...result]}};
}

function money(value){
 check((typeof value==='string'||Number.isSafeInteger(value))&&typeof value!=='boolean'&&/^[0-9]{1,12}(?:\.[0-9]{1,8})?$/.test(String(value)),'HANDOFF_OPERATOR_POLICY_INVALID');
 const [whole,fraction='']=String(value).split('.');
 const units=BigInt(whole)*100000000n+BigInt(fraction.padEnd(8,'0'));
 check(units>0n,'HANDOFF_OPERATOR_POLICY_INVALID');return units;
}
function expiry(value){
 check(typeof value==='string','HANDOFF_OPERATOR_POLICY_INVALID');
 const match=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
 check(match,'HANDOFF_OPERATOR_POLICY_TIMEZONE_REQUIRED');
 const [year,month,day,hour,minute,second]=match.slice(1,7).map(Number);
 const days=new Date(Date.UTC(year,month,0));
 check(year>=100&&month>=1&&month<=12&&day>=1&&day<=days.getUTCDate()&&hour<=23&&minute<=59&&second<=59,'HANDOFF_OPERATOR_POLICY_INVALID');
 if(match[8]!=='Z'){const [offsetHour,offsetMinute]=match[8].slice(1).split(':').map(Number);check(offsetHour<=23&&offsetMinute<=59,'HANDOFF_OPERATOR_POLICY_INVALID');}
 const valueMs=Date.parse(value);check(Number.isFinite(valueMs),'HANDOFF_OPERATOR_POLICY_INVALID');return valueMs;
}

export function validateExecutionPermit({plan,planWire,approval,packageWire,expectedPlanSHA256,expectedPackageSHA256,now=Date.now()}={}){
 check(plain(plan)&&plain(approval)&&finiteJSON(plan)&&finiteJSON(approval),'HANDOFF_EXECUTION_DOCUMENT_REQUIRED');
 check((typeof planWire==='string'||Buffer.isBuffer(planWire))&&(typeof packageWire==='string'||Buffer.isBuffer(packageWire)),'HANDOFF_EXACT_WIRE_REQUIRED');
 const planText=Buffer.isBuffer(planWire)?planWire.toString('utf8'):planWire;
 const packageText=Buffer.isBuffer(packageWire)?packageWire.toString('utf8'):packageWire;
 check(Buffer.byteLength(planText)<=24*1024**2&&Buffer.byteLength(packageText)<=8*1024**2,'HANDOFF_EXECUTION_DOCUMENT_TOO_LARGE');
 let parsedPlan,parsedRuntime;try{parsedPlan=JSON.parse(planText);parsedRuntime=JSON.parse(packageText);}catch{throw Error('HANDOFF_EXECUTION_JSON_INVALID');}
 check(canonicalJSON(parsedPlan)===canonicalJSON(plan),'HANDOFF_PLAN_WIRE_CHANGED');
 check(hex(expectedPlanSHA256)&&sha(planWire)===expectedPlanSHA256&&approval.planSHA256===expectedPlanSHA256,'HANDOFF_APPROVED_PLAN_SHA_MISMATCH');
 check(plan.schema===PLAN_SCHEMA&&[6,10].includes(plan.durationSeconds)&&plan.totalFrames===plan.durationSeconds*30&&plan.fps===30&&plan.aspectRatio==='9:16'&&canonicalJSON(plan.resolution)==='{"height":1920,"width":1080}','HANDOFF_SIX_SECOND_PLAN_REQUIRED');
 check(canonicalJSON(plan.audioSettings)==='{"enabled":false,"mode":"SILENT"}'&&['GENERAL','FICTIONAL'].includes(plan.simulationType),'HANDOFF_NONHISTORICAL_SILENT_SCOPE_REQUIRED');
 const render=plan.renderProfile;
 check(plain(render)&&render.profileId===PROFILE&&render.backend==='vulkan'&&hex(render.sourceClosureSHA256)&&digest(render.imageDigest),'HANDOFF_NVIDIA_RENDER_PROFILE_REQUIRED');
 check(approval.schema===APPROVAL_SCHEMA&&approval.approved===true&&approval.imageDigest===render.imageDigest,'HANDOFF_GPU_APPROVAL_REQUIRED');
 const policyKeys=['schema','approved','planSHA256','imageDigest','validUntil','maxWallSeconds','maxRetries','maxCostAmount','currency','gpuHourlyRate'];
 check(Object.keys(approval).length===policyKeys.length&&Object.keys(approval).every(k=>policyKeys.includes(k)),'HANDOFF_OPERATOR_POLICY_FIELDS_INVALID');
 check(Number.isInteger(approval.maxWallSeconds)&&approval.maxWallSeconds>=1&&approval.maxWallSeconds<=86400&&Number.isInteger(approval.maxRetries)&&approval.maxRetries>=0&&approval.maxRetries<=2&&typeof approval.currency==='string'&&/^[A-Z]{3}$/.test(approval.currency),'HANDOFF_BOUNDED_GPU_POLICY_REQUIRED');
 const deadline=expiry(approval.validUntil);
 const nowMs=now instanceof Date?now.getTime():now;
 check(Number.isFinite(nowMs)&&deadline>nowMs,'HANDOFF_GPU_APPROVAL_EXPIRED');
 const cost=money(approval.maxCostAmount),rate=money(approval.gpuHourlyRate);
 check(BigInt(approval.maxWallSeconds)*rate<=cost*3600n,'HANDOFF_GPU_COST_LIMIT_EXCEEDED');
 check(typeof plan.runtimeWireJSON==='string'&&plan.runtimeWireJSON===packageText&&hex(expectedPackageSHA256)&&sha(packageWire)===expectedPackageSHA256&&plan.runtimeWireSHA256===expectedPackageSHA256,'HANDOFF_RUNTIME_WIRE_SHA_MISMATCH');
 check(plain(plan.runtime)&&canonicalJSON(parsedRuntime)===canonicalJSON(plan.runtime)&&parsedRuntime.schema==='WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2'&&parsedRuntime.totalFrames===plan.totalFrames&&(parsedRuntime.durationSeconds===undefined?6:parsedRuntime.durationSeconds)===plan.durationSeconds,'HANDOFF_RUNTIME_PLAN_MISMATCH');
 check(Array.isArray(parsedRuntime.segments)&&parsedRuntime.segments.length>=1&&parsedRuntime.segments.length<=16,'HANDOFF_RUNTIME_SEGMENTS_REQUIRED');
 let cursor=0;for(const segment of parsedRuntime.segments){check(plain(segment)&&segment.startFrame===cursor&&Number.isSafeInteger(segment.endFrame)&&segment.endFrame>cursor&&segment.endFrame<=plan.totalFrames,'HANDOFF_RUNTIME_FRAME_RANGE_INVALID');cursor=segment.endFrame;}
 check(cursor===plan.totalFrames&&hex(plan.sourceQualificationSHA256),'HANDOFF_SOURCE_QUALIFICATION_REQUIRED');
 const executionSeconds=Math.min(600,approval.maxWallSeconds,Math.floor((deadline-nowMs)/1000));
 check(executionSeconds>=1,'HANDOFF_GPU_APPROVAL_EXPIRED');
 return {profile:PROFILE,planSHA256:expectedPlanSHA256,runtimePackageSHA256:expectedPackageSHA256,
  authorizationScope:'EXPLICIT_EXISTING_OPERATOR_APPROVAL',maxWallSeconds:executionSeconds,
  approvedMaxWallSeconds:approval.maxWallSeconds,approvedMaxRetries:approval.maxRetries,
  maxRetries:0,deadlineUnixMilliseconds:Math.min(deadline,nowMs+executionSeconds*1000),
  imageDigest:render.imageDigest,sourceClosureSHA256:render.sourceClosureSHA256,
  sourceQualificationSHA256:plan.sourceQualificationSHA256};
}
