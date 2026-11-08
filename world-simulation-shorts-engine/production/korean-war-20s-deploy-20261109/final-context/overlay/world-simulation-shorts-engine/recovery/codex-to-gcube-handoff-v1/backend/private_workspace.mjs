/** Qualified new-profile POSIX workspace; never repairs existing directories. */
import {lstat,realpath,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const REPO=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..');
const check=(value,code)=>{if(!value)throw Error(code);};
const within=(file,root)=>file===root||file.startsWith(root+path.sep);
const canonical=value=>typeof value==='string'&&path.isAbsolute(value)&&path.resolve(value)===value&&!value.split(path.sep).includes('..');
async function ancestors(file){
 for(let current=file;;current=path.dirname(current)){
  const stat=await lstat(current);check(stat.isDirectory()&&!stat.isSymbolicLink()&&!(stat.mode&0o022),'HANDOFF_PRIVATE_ANCESTOR_UNSAFE');
  if(current===path.dirname(current))break;
 }
}
export async function assertPrivateWorkspace({privateWorkspaceRoot,publicExportRoot}={}){
 check(canonical(privateWorkspaceRoot)&&canonical(publicExportRoot),'HANDOFF_QUALIFIED_WORKSPACE_PATH_REQUIRED');
 check(!within(privateWorkspaceRoot,REPO)&&!within(REPO,privateWorkspaceRoot),'HANDOFF_PRIVATE_WORKSPACE_OUTSIDE_REPO_REQUIRED');
 await ancestors(privateWorkspaceRoot);
 const actual=await realpath(privateWorkspaceRoot),publicActual=await realpath(publicExportRoot),stat=await lstat(privateWorkspaceRoot);
 check(actual===privateWorkspaceRoot&&publicActual===publicExportRoot,'HANDOFF_WORKSPACE_SYMLINK_FORBIDDEN');
 check(!within(actual,publicActual)&&!within(publicActual,actual),'HANDOFF_PRIVATE_PUBLIC_ROOTS_MUST_BE_SEPARATE');
 check(stat.uid===process.getuid()&&!(stat.mode&0o077),'HANDOFF_OWNED_0700_WORKSPACE_REQUIRED');
 return{privateWorkspaceRoot:actual,publicExportRoot:publicActual,existingOwnedPrivateRootVerified:true};
}
export async function assertQualifiedPrivatePath(root,options){
 const qualified=await assertPrivateWorkspace(options);
 check(canonical(root)&&root!==qualified.privateWorkspaceRoot&&within(root,qualified.privateWorkspaceRoot),'HANDOFF_FRESH_PRIVATE_DESCENDANT_REQUIRED');
 await ancestors(path.dirname(root));
 return root;
}
async function create(root,options,allowExisting){
 await assertQualifiedPrivatePath(root,options);
 try{await mkdir(root,{mode:0o700});}catch(error){if(!allowExisting||error.code!=='EEXIST')throw error;}
 const stat=await lstat(root);check(stat.isDirectory()&&!stat.isSymbolicLink()&&stat.uid===process.getuid()&&!(stat.mode&0o077),'HANDOFF_FRESH_PRIVATE_DIRECTORY_INVALID');
 return root;
}
export const createFreshPrivateDirectory=(root,options)=>create(root,options,false);
export const ensureQualifiedPrivateDirectory=(root,options)=>create(root,options,true);
