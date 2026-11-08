import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
const require=createRequire(path.join(process.env.CPU_DEPS_ROOT,'package.json'));
const {chromium}=require('playwright');
let browser;
try {
  browser=await chromium.launch({executablePath:process.env.CPU_CHROME,headless:true,chromiumSandbox:true,
    ignoreDefaultArgs:['--disable-client-side-phishing-detection','--disable-features=AcceptCHFrame,AvoidUnnecessaryBeforeUnloadCheckSync,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,Translate,AutoDeElevate,RenderDocument,OptimizationHints','--disable-ipc-flooding-protection','--disable-popup-blocking','--disable-prompt-on-repost','--unsafely-disable-devtools-self-xss-warnings'],
    args:['--use-angle=swiftshader','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:64,height:64}});
  await page.setContent('<canvas width="64" height="64"></canvas>');
  const webgl=await page.evaluate(()=>{
    const gl=document.querySelector('canvas').getContext('webgl2');
    if(!gl)throw Error('WEBGL2_UNAVAILABLE');
    const ext=gl.getExtension('WEBGL_debug_renderer_info');
    const renderer=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
    gl.clearColor(.2,.4,.6,1);gl.clear(gl.COLOR_BUFFER_BIT);
    const p=new Uint8Array(4);gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);
    return {renderer,pixel:Array.from(p),glError:gl.getError()};
  });
  if(!/swiftshader/i.test(webgl.renderer)||webgl.glError!==0||webgl.pixel.join(',')!=='51,102,153,255')throw Error('SOFTWARE_WEBGL_CONTRACT');
  const png=await page.screenshot();
  const result={status:'NORMAL_LINUX_BROWSER_PASS',unixSocket:true,chromiumSandbox:true,securityRelaxed:false,
    chromium:browser.version(),playwright:require('playwright/package.json').version,webgl,
    pngBytes:png.length,pngSHA256:createHash('sha256').update(png).digest('hex'),projectFrames:0,videoCreated:false,gpuExecuted:false};
  await writeFile(path.join(process.env.RUNNER_TEMP,'CPU_RUNNER_READINESS.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
} catch(error) {
  console.log(JSON.stringify({status:'NORMAL_LINUX_BROWSER_BLOCKED',error:String(error.message).slice(0,7000),projectFrames:0,securityRelaxed:false}));
  process.exitCode=1;
} finally {await browser?.close();}
