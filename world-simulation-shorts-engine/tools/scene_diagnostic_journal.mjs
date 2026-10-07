// Synchronous append+fsync before audit rejection. No env dump or arbitrary files.
import fs from 'node:fs';
import path from 'node:path';
const sensitive=/owner.?code|cookie|authorization|token|session|secret|password/i;
const values=Object.entries(process.env).filter(([k,v])=>sensitive.test(k)&&v.length>=4).map(([,v])=>v);
export function registerRedactionFile(file){
 if(!file)return;const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
 try{const info=fs.fstatSync(fd);if(info.uid!==process.getuid()||(info.mode&0o077)||info.size>4096)throw Error('INVALID_REDACTION_SOURCE');const value=fs.readFileSync(fd,'utf8').trim();if(value.length>=4)values.push(value);}finally{fs.closeSync(fd);}
}
export function redact(value){
 if(typeof value==='number'&&!Number.isFinite(value))return {non_finite:String(value)};
 if(typeof value==='undefined')return {not_available:'undefined'};
 if(Array.isArray(value))return value.map(redact);
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).filter(([k])=>!sensitive.test(k)).map(([k,v])=>[k,redact(v)]));
 if(typeof value==='string'){for(const secret of values)value=value.split(secret).join('[REDACTED]');value=value.replace(/https?:\/\/[^\s"'<>]+/g,'[URL omitted]');return sensitive.test(value)?'[sensitive text omitted]':value;}
 return value;
}
export class SceneJournal{
 constructor(root,sceneId){
  if(!/^S\d{3,5}$/.test(sceneId))throw Error('INVALID_DIAGNOSTIC_SCENE');
  this.root=path.join(root,sceneId);this.sceneId=sceneId;this.seq=0;
  fs.mkdirSync(this.root,{recursive:true,mode:0o700});if(fs.lstatSync(this.root).isSymbolicLink())throw Error('INVALID_DIAGNOSTIC_PATH');
 }
 write(name,value){
  if(!/^[\w.-]+\.json$/.test(name))throw Error('INVALID_DIAGNOSTIC_FILE');
  const target=path.join(this.root,name),temp=target+`.${process.pid}.${++this.seq}.writing`;
  const fd=fs.openSync(temp,fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
  try{fs.writeFileSync(fd,JSON.stringify(redact(value),null,2));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  fs.renameSync(temp,target);const directory=fs.openSync(this.root,fs.constants.O_RDONLY);try{fs.fsyncSync(directory);}finally{fs.closeSync(directory);}
 }
 frame(value){
  const fd=fs.openSync(path.join(this.root,'frame-audit.jsonl'),fs.constants.O_WRONLY|fs.constants.O_APPEND|fs.constants.O_CREAT|fs.constants.O_NOFOLLOW,0o600);
  try{fs.writeFileSync(fd,JSON.stringify(redact(value))+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
 }
 failure(value){this.write('failed-invariant.json',value);}
}
export const requiredAuditFields=['webglError','textClipped','entityClipped','missingTextures','fontReady','cameraPosition','cameraQuaternion','cameraFov','routeProgress','routeDisplay','routeInsideEarth','routeDiscontinuities','entities','entitySeparation','productionDefaults'];
export function frameEvidence({sceneId,frameIndex,t,audit,errors,renderer,failedInvariants,decoded,decodeError}){
 return {...audit,scene_id:sceneId,frame_index:frameIndex,timestamp:t,shot:audit?.shot??null,errors:[...errors],renderer:renderer?.renderer??null,vendor:renderer?.vendor??null,backend:renderer?.backend??null,decoded,decodeError,FAILED_INVARIANT:failedInvariants,missing_audit_fields:requiredAuditFields.filter(key=>!(key in (audit&&typeof audit==='object'?audit:{})))};
}
