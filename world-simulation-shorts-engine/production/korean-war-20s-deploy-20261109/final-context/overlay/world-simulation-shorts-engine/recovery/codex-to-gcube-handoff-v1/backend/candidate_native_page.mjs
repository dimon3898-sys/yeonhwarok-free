/** Transport for existing official sessions. Browser/encoder ownership stays in captureVulkanDerived. */
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
const check=(v,c)=>{if(!v)throw Error(c)};
export async function serveNativeCandidateSession(session){
 const trace=[],server=createServer(async(req,res)=>{
  try{
   const chunks=[];let size=0;
   for await(const chunk of req){size+=chunk.length;check(size<=2048,'HANDOFF_CANDIDATE_BODY_CAP');chunks.push(chunk);}
   const result=await session.response({method:req.method,url:req.url,headers:req.headers,body:Buffer.concat(chunks)});
   trace.push({path:req.url,status:result.status,sha256:createHash('sha256').update(result.body).digest('hex'),bytes:result.body.length});
   res.writeHead(result.status,result.headers);res.end(result.body);
  }catch{res.writeHead(400);res.end();}
 });
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 let closed=false;
 return{server,trace,origin:'http://127.0.0.1:'+server.address().port,async close(){if(closed)return;closed=true;session.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}};
}
export async function initializeNativeCandidatePage(page){
 await page.evaluate(async()=>window.__worldEngineDiagnostics.run('RUNTIME_IMPORT',async()=>{
  const response=await fetch('/runtime.json');if(!response.ok)throw Error('HANDOFF_CANDIDATE_RUNTIME_HTTP');
  const data=await response.json();window.payload=data.prepared;window.officialCandidate=data.officialCandidate;
  const{prepareRegisteredOfficialScope}=await import('/recovery/universal-presentation-v2/official_candidate_bootstrap.mjs');
  const{createPresentationRuntime}=await import('/recovery/universal-presentation-v2/presentation_runtime.mjs');
  window.createRuntime=async options=>{
   window.officialScope?.dispose();const scope=await prepareRegisteredOfficialScope(window.officialCandidate.sceneKey);window.officialScope=scope;
   let runtime;options.canvas.addEventListener('webglcontextlost',()=>{scope.dispose();runtime?.dispose();},{once:true});
   try{runtime=await createPresentationRuntime({...options,officialCandidateScope:scope.scope});await scope.checkServer();return runtime;}
   catch(error){runtime?.dispose();scope.dispose();throw error;}
  };
  window.currentSegment=-1;
 }));
}
