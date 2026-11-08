/** Server-only bounded immutable in-memory bytes. Never serve by reopening a path. */
import {lstat,realpath,open} from 'node:fs/promises';import {constants} from 'node:fs';import path from 'node:path';import {createHash} from 'node:crypto';
const check=(v,c)=>{if(!v)throw Error(c);},sha=b=>createHash('sha256').update(b).digest('hex');
export async function verifyServerRoot(root){
 check(typeof root==='string'&&path.isAbsolute(root)&&path.normalize(root)===root,'UP2_CANDIDATE_ROOT_INVALID');
 for(let p=root;;p=path.dirname(p)){
  const s=await lstat(p);check(s.isDirectory()&&!s.isSymbolicLink()&&(s.uid===process.getuid()||s.uid===0)&&!(s.mode&0o022),'UP2_CANDIDATE_PARENT_UNSAFE');if(p===path.dirname(p))break;
 }
 check(await realpath(root)===root,'UP2_CANDIDATE_ROOT_ALIAS');return root;
}
export async function readPinnedServerFile(root,name,pin){
 check(typeof name==='string'&&path.basename(name)===name&&!name.includes('..')&&!name.includes('\\'),'UP2_CANDIDATE_FILE_NAME_INVALID');
 check(pin&&Number.isSafeInteger(pin.bytes)&&pin.bytes>0&&pin.bytes<=64*1024**2&&/^[a-f0-9]{64}$/.test(pin.sha256),'UP2_CANDIDATE_FILE_PIN_INVALID');
 await verifyServerRoot(root);const file=path.join(root,name),before=await lstat(file);
 check(before.isFile()&&!before.isSymbolicLink()&&before.uid===process.getuid()&&!(before.mode&0o022),'UP2_CANDIDATE_FILE_UNSAFE');
 const handle=await open(file,constants.O_RDONLY|constants.O_NOFOLLOW);
 try{const opened=await handle.stat();check(opened.dev===before.dev&&opened.ino===before.ino,'UP2_CANDIDATE_FILE_SWAPPED');check(opened.size===pin.bytes,'UP2_CANDIDATE_SNAPSHOT_HASH_MISMATCH');const b=Buffer.alloc(pin.bytes);let offset=0;while(offset<b.length){const n=await handle.read(b,offset,b.length-offset,offset);check(n.bytesRead>0,'UP2_CANDIDATE_FILE_TRUNCATED');offset+=n.bytesRead;}check((await handle.read(Buffer.alloc(1),0,1,b.length)).bytesRead===0,'UP2_CANDIDATE_FILE_GREW');const after=await handle.stat(),current=await lstat(file);await verifyServerRoot(root);
  check(after.uid===process.getuid()&&current.uid===process.getuid()&&!(after.mode&0o022)&&!(current.mode&0o022)&&after.dev===current.dev&&after.ino===current.ino&&opened.size===after.size&&opened.mtimeMs===after.mtimeMs&&opened.ctimeMs===after.ctimeMs,'UP2_CANDIDATE_FILE_CHANGED');
  check(b.length===pin.bytes&&sha(b)===pin.sha256,'UP2_CANDIDATE_SNAPSHOT_HASH_MISMATCH');return b;
 }finally{await handle.close();}
}
export async function captureAssetSnapshot(groups){
 const bytes=new Map();let total=0;
 for(const{root,assets}of groups){await verifyServerRoot(root);for(const[key,a]of Object.entries(assets)){
  check(key==='sha256/'+a.sha256,'UP2_CANDIDATE_ASSET_KEY_INVALID');const b=await readPinnedServerFile(root,a.localFile,a);
  if(!bytes.has(key)){total+=b.length;check(total<=64*1024**2,'UP2_CANDIDATE_SNAPSHOT_LIMIT');bytes.set(key,b);}
 }}
 return Object.freeze({byteCount:total,read(key){check(bytes.has(key),'UP2_CANDIDATE_ASSET_NOT_REGISTERED');return Buffer.from(bytes.get(key));}});
}
