import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {createLoaderDetailCollector,loaderDiagnosticLaunchOptions,observeLoaderStreams,safeLoaderEvent} from './diagnose_webgl_once.mjs';

test('browser-only logging preserves executable, arguments, sandbox and inherited environment without mutation',()=>{
 const environ={GPU_BACKEND:'vulkan',VK_ICD_FILENAMES:'/existing/nvidia_icd.json',LD_LIBRARY_PATH:'/existing/lib',PRIVATE_VALUE:'not-exported'};
 const args=['--use-angle=vulkan','--disable-vulkan-surface'];
 const options={executablePath:'/usr/bin/chromium',chromiumSandbox:true,headless:true,args};
 const result=loaderDiagnosticLaunchOptions(options,environ);
 assert.deepEqual(result,{...options,env:{...environ,VK_LOADER_DEBUG:'error,warn,driver'}});
 assert.equal(result.args,args);assert.equal(options.env,undefined);assert.equal(environ.VK_LOADER_DEBUG,undefined);
 const explicit={...options,env:{VK_ICD_FILENAMES:'/explicit/icd.json',VK_LOADER_DEBUG:'all'}};
 assert.deepEqual(loaderDiagnosticLaunchOptions(explicit,environ).env,{VK_ICD_FILENAMES:'/explicit/icd.json',VK_LOADER_DEBUG:'error,warn,driver'});
 assert.equal(explicit.env.VK_LOADER_DEBUG,'all');
});

test('official loader discovery and lookup messages never claim successful driver initialization',()=>{
 const manifest=safeLoaderEvent('[Vulkan Loader] DRIVER: Found ICD manifest file /etc/vulkan/icd.d/nvidia_icd.json, version "1.0.1"','BROWSER_STDOUT');
 assert.equal(manifest.code,'LOADER_MANIFEST_FOUND');assert.equal(manifest.failure,false);assert.deepEqual(manifest.basenames,['nvidia_icd.json']);
 const lookup=safeLoaderEvent('[Vulkan Loader] DEBUG | DRIVER: Searching for ICD drivers named libGLX_nvidia.so.0','BROWSER_STDERR');
 assert.equal(lookup.code,'LOADER_LIBRARY_LOOKUP');assert.equal(lookup.failure,false);
 assert.equal(manifest.driverInitialized,undefined);assert.equal(lookup.driverInitialized,undefined);
});

test('v1.3.275 library and symbol errors retain only closed failure reasons and public basenames',()=>{
 const cases=[
  ['ERROR: libGLX_nvidia.so.0: cannot open shared object file: No such file or directory','LOADER_LIBRARY_LOAD_FAILED','NOT_FOUND'],
  ['ERROR: /private/customer/libGLX_nvidia.so.0: cannot open shared object file: Permission denied','LOADER_LIBRARY_LOAD_FAILED','PERMISSION_DENIED'],
  ['[Vulkan Loader] DRIVER: Requested ICD /private/customer/libvulkan_lvp.so was wrong bit-type. Ignoring this JSON','LOADER_LIBRARY_LOAD_FAILED','WRONG_BIT_TYPE'],
  ["ERROR: loader_scanned_icd_add: Could not get 'vkCreateInstance' via 'vk_icdGetInstanceProcAddr' for ICD /private/customer/libGLX_nvidia.so.0",'LOADER_SYMBOL_MISSING','SYMBOL_MISSING'],
  ["ERROR: loader_scanned_icd_add: ICD libGLX_nvidia.so.0 doesn't support interface version compatible with loader, skip this ICD.",'LOADER_INTERFACE_INCOMPATIBLE','INTERFACE_INCOMPATIBLE'],
  ['ERROR: loader_icd_scan: Failed loading library associated with ICD JSON /private/customer/libGLX_nvidia.so.0. Ignoring this JSON','LOADER_LIBRARY_LOAD_FAILED','UNSPECIFIED'],
 ];
 for(const [line,code,reason] of cases){const event=safeLoaderEvent(line,'BROWSER_STDERR');assert.equal(event.code,code);assert.equal(event.reason,reason);assert.equal(event.failure,true);assert.ok(!JSON.stringify(event).includes('/private'));}
 assert.deepEqual(safeLoaderEvent(cases.at(-1)[0],'BROWSER_STDERR').basenames,['libGLX_nvidia.so.0']);
 assert.deepEqual(safeLoaderEvent('ERROR: libxcb-dri3.so.0: cannot open shared object file: No such file or directory','BROWSER_STDERR').basenames,['libxcb-dri3.so.0']);
});

test('credentials, private paths, arbitrary library names and environment values are not exported',()=>{
 const collector=createLoaderDetailCollector();
 collector.append('BROWSER_STDERR','ERROR: loader_icd_scan: Failed loading library associated with ICD JSON /private/customer/unique-company-driver.so. Ignoring this JSON\n');
 collector.append('BROWSER_STDOUT','[Vulkan Loader] DRIVER: Found ICD manifest file /private/customer/nvidia_icd.json, version "1.0.1"\n');
 for(const keyword of ['password','owner_code','token','authorization','cookie','api_key','credential','environment','argv'])
  collector.append('BROWSER_STDERR',`ERROR: loader_icd_scan: Failed loading library associated with ICD JSON ${keyword}=HIGHLY_PRIVATE_SENTINEL\n`);
 const result=collector.finish(),out=JSON.stringify(result);assert.equal(result.status,'EVIDENCE_INCOMPLETE');assert.equal(result.ignoredErrorLines,9);
 for(const value of ['HIGHLY_PRIVATE_SENTINEL','/private','customer','unique-company-driver'])assert.ok(!out.includes(value));
 assert.ok(out.includes('nvidia_icd.json'));
 assert.equal(safeLoaderEvent('Found ICD manifest file nvidia_icd.json','OTHER_STREAM'),null);
});

test('existing child observer collects stdout and stderr separately and joins fragmented lines',()=>{
 const child={stdout:new EventEmitter(),stderr:new EventEmitter()},collector=createLoaderDetailCollector();observeLoaderStreams(child,collector);
 child.stdout.emit('data',Buffer.from('[Vulkan Loader] DRIVER: Found ICD mani'));
 child.stderr.emit('data',Buffer.from('ERROR: libGLX_nvidia.so.0: cannot open shared object file: Permission denied\n'));
 child.stdout.emit('data',Buffer.from('fest file /etc/vulkan/icd.d/nvidia_icd.json\n'));
 const result=collector.finish();assert.equal(result.status,'EVIDENCE_RECORDED');assert.equal(result.events.length,2);
 assert.equal(result.events[0].source,'BROWSER_STDERR');assert.equal(result.events[0].reason,'PERMISSION_DENIED');
 assert.equal(result.events[1].source,'BROWSER_STDOUT');assert.equal(result.events[1].code,'LOADER_MANIFEST_FOUND');
 assert.ok(result.events[0].firstLineOrdinal<result.events[1].firstLineOrdinal);
 assert.ok(result.bytesObserved.BROWSER_STDOUT>0&&result.bytesObserved.BROWSER_STDERR>0);
});

test('repeated informational messages are deduplicated and cannot consume the failure reserve',()=>{
 const collector=createLoaderDetailCollector();
 for(let i=0;i<300;i++)collector.append('BROWSER_STDOUT','[Vulkan Loader] DRIVER: Found ICD manifest file /etc/vulkan/icd.d/nvidia_icd.json\n');
 const names=['libGLX_nvidia.so.0','libEGL_nvidia.so.0','libvulkan.so.1','libvulkan_intel.so','libvulkan_lvp.so','libvulkan_radeon.so','libX11.so.6','libXext.so.6','libxcb.so.1'];
 for(const source of ['BROWSER_STDOUT','BROWSER_STDERR'])for(const name of names)collector.append(source,`[Vulkan Loader] DRIVER: Searching for ICD drivers named ${name}\n`);
 collector.append('BROWSER_STDERR','ERROR: libGLX_nvidia.so.0: cannot open shared object file: Permission denied\n');
 const result=collector.finish();assert.equal(result.events[0].reason,'PERMISSION_DENIED');assert.equal(result.events[0].failure,true);
 assert.ok(result.events.length<=32);assert.equal(result.events.find(e=>e.code==='LOADER_MANIFEST_FOUND').occurrences,300);
 assert.ok(result.omittedEvents>0);assert.equal(result.status,'EVIDENCE_INCOMPLETE');
});

test('input, line and event limits remain bounded and incomplete lines are not exported',()=>{
 const collector=createLoaderDetailCollector();
 collector.append('BROWSER_STDERR','[Vulkan Loader] DRIVER: '+ 'x'.repeat(9000));
 collector.append('BROWSER_STDERR','\n[Vulkan Loader] DRIVER: Found ICD manifest file /etc/vulkan/icd.d/nvidia_icd.json\n');
 collector.append('BROWSER_STDOUT',Buffer.alloc(300000,120));
 const result=collector.finish();assert.equal(result.acceptedBytes,262144);assert.ok(result.droppedLines>=1);assert.equal(result.truncated,true);
 assert.ok(JSON.stringify(result).length<8192);assert.ok(result.events.every(e=>!Object.hasOwn(e,'excerpt')));
 assert.deepEqual(collector.finish(),result);
});

test('missing loader output or observer errors produce unavailable/incomplete evidence, never a runtime PASS',()=>{
 const empty=createLoaderDetailCollector();observeLoaderStreams({},empty);const unavailable=empty.finish();assert.equal(unavailable.status,'UNAVAILABLE');assert.equal(unavailable.observerErrors,2);
 const child={stdout:new EventEmitter(),stderr:new EventEmitter()},collector=createLoaderDetailCollector();observeLoaderStreams(child,collector);
 child.stdout.emit('data','[Vulkan Loader] DRIVER: Searching for driver manifest files\n');child.stderr.emit('error',Error('PRIVATE_ERROR_SENTINEL'));
 const out=collector.finish();assert.equal(out.status,'EVIDENCE_INCOMPLETE');assert.equal(out.observerErrors,1);assert.ok(!JSON.stringify(out).includes('PRIVATE_ERROR_SENTINEL'));
 assert.ok(![out.status,unavailable.status].includes('PASS'));
});

test('unrecognized loader errors preserve an explicit unknown classification without raw words or paths',()=>{
 const event=safeLoaderEvent('[Vulkan Loader] ERROR: UnexpectedFutureReason /private/customer/driver.so','BROWSER_STDERR');
 assert.equal(event.code,'LOADER_UNCLASSIFIED_ERROR');assert.equal(event.failure,true);assert.equal(event.reason,'UNSPECIFIED');
 const warning=safeLoaderEvent('[Vulkan Loader] WARNING: UnexpectedFutureReason libGLX_nvidia.so.0','BROWSER_STDOUT');
 assert.equal(warning.code,'LOADER_UNCLASSIFIED_WARNING');assert.equal(warning.failure,false);
 assert.ok(!JSON.stringify([event,warning]).includes('UnexpectedFutureReason'));assert.ok(!JSON.stringify(event).includes('/private'));
});
