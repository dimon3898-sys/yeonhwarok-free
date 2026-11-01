import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {IMAGE_DIGEST,PROFILE_SHA256,CAPTURE_INPUT,safeNativeDetail,createNativeDetailCollector,validOutputDirectory} from './diagnose_webgl_once.mjs';
const sha=value=>createHash('sha256').update(value).digest('hex');

test('updated image and profile pins match the deployed source and capture input stays unchanged',async()=>{
 assert.equal(IMAGE_DIGEST,'sha256:9e9301dec376a780f4fb2287fe092282baaef3d6cfdfc93532ea6763d9f9b0cf');
 const profile=await fs.readFile(process.env.WORLD_ENGINE_TEST_PROFILE_FILE??new URL('../codex-to-gcube-handoff-v1/backend/profile_contract.mjs',import.meta.url));
 assert.equal(sha(profile),PROFILE_SHA256);
 assert.deepEqual(CAPTURE_INPUT,{executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
});
test('verified mount root avoids assuming a nested parent',()=>{
 assert.equal(validOutputDirectory('/world-storage/webgl-init-native-20261102-a1'),true);
 for(const value of ['/world-storage/WORLD_ENGINE/webgl-init-a1','/tmp/webgl-init-a1','/world-storage/webgl-init-../x','/world-storage/webgl-init-a/b'])assert.equal(validOutputDirectory(value),false);
});
test('native function, extension, feature and numeric failure remain actionable',()=>{
 const raw='RendererVk.cpp:1927 (initialize): ANGLE Vulkan error (-9): vkCreateInstance failed: required extension VK_KHR_surface missing; feature independentBlend not supported; VK_ERROR_INCOMPATIBLE_DRIVER';
 const out=safeNativeDetail(raw);
 for(const value of ['vkCreateInstance','VK_KHR_surface','independentBlend','VK_ERROR_INCOMPATIBLE_DRIVER','-9','missing','not supported'])assert.ok(out.excerpt.includes(value));
 assert.deepEqual(out.sourceFrames,[{file:'RendererVk.cpp',line:1927}]);
 assert.equal(out.sha256,sha(raw));assert.equal(out.rawOmitted,true);
 assert.equal(out.excerptFormat,'FINITE_PUBLIC_VOCABULARY_REDACTED_NOT_RAW');
 const extension=safeNativeDetail('RendererVk.cpp:123 (initialize): Required Vulkan extension VK_KHR_surface is not supported');
 assert.ok(extension.excerpt.includes('required Vulkan extension VK_KHR_surface is not supported'));
});
test('authentication-bearing native lines export no message content',()=>{
 const raw='ANGLE Vulkan initialization failed OWNER_CODE=actual-private-value token=hidden-value EGL_NOT_INITIALIZED';
 const out=safeNativeDetail(raw),wire=JSON.stringify(out);
 assert.equal(out.sensitiveLineOmitted,true);assert.equal(out.sha256,sha(raw));
 for(const forbidden of ['actual-private-value','hidden-value','OWNER_CODE'])assert.ok(!wire.includes(forbidden));
});
test('private paths, URLs, unknown identifiers and arbitrary numeric values are removed',()=>{
 const out=safeNativeDetail('ANGLE Vulkan error: unable to load /private/user42/libhidden.so https://private.example/data?x=777 unknownValue123 01012345678 123456 initialization failed');
 const wire=JSON.stringify(out);
 for(const value of ['user42','libhidden','private.example','unknownValue123','01012345678','123456'])assert.ok(!wire.includes(value));
 assert.ok(out.omittedTokens>0);assert.ok(out.excerpt.includes('[omitted]'));
 assert.equal(safeNativeDetail('not a native message with confidential data'),null);
 assert.equal(safeNativeDetail('ANGLE error',{source:'STDOUT'}),null);
 assert.equal(safeNativeDetail('ANGLE error command line: --token=value'),null);
 assert.ok(!safeNativeDetail('Vulkan error 1234 initialization failed').excerpt.includes('1234'));
});
test('split chunks are joined before native filtering and retain the real whole-line hash',()=>{
 const collector=createNativeDetailCollector(),raw='ANGLE Vulkan error pass'+'word=DO_NOT_EXPORT EGL_NOT_INITIALIZED';
 collector.append('ANGLE Vulkan error pass');collector.append('word=DO_NOT_EXPORT EGL_NOT_');collector.append('INITIALIZED\n');
 const out=collector.finish();assert.equal(out.events.length,1);
 assert.equal(out.events[0].sha256,sha(raw));assert.equal(out.events[0].sensitiveLineOmitted,true);
 assert.ok(!JSON.stringify(out).includes('DO_NOT_EXPORT'));
 const second=createNativeDetailCollector();second.append('Vulkan vkCreate');second.append('Instance error (-9): VK_ERROR_INCOMPATIBLE_DRIVER\n');
 assert.ok(second.finish().events[0].excerpt.includes('vkCreateInstance'));
});
test('line, event, excerpt and input bounds are explicit without exporting cut line fragments',()=>{
 const collector=createNativeDetailCollector();collector.append('ANGLE error '+ 'x'.repeat(9000)+'\n');
 for(let i=0;i<40;i++)collector.append('Vulkan vkCreateInstance error (-9): VK_ERROR_INCOMPATIBLE_DRIVER\n');
 const out=collector.finish();assert.equal(out.events.length,32);assert.equal(out.omittedEvents,8);assert.equal(out.droppedLines,1);assert.equal(out.truncated,true);
 const excerpt=safeNativeDetail('ANGLE error '+ 'initialization failed '.repeat(100));
 assert.ok(Buffer.byteLength(excerpt.excerpt)<=512);assert.equal(excerpt.excerptTruncated,true);
 const overflow=createNativeDetailCollector();overflow.append(Buffer.alloc(262144,32));overflow.append('Vulkan error VK_ERROR_INCOMPATIBLE_DRIVER');
 const limited=overflow.finish();assert.equal(limited.acceptedBytes,262144);assert.equal(limited.events.length,0);assert.equal(limited.truncated,true);
});
test('context creation events use the same bounded redaction and unknown text remains explicit',()=>{
 const out=safeNativeDetail('Could not create WebGL2 context: EGL_NOT_INITIALIZED unknownReason',{source:'WEBGL_CONTEXT_CREATION_EVENT'});
 assert.equal(out.source,'WEBGL_CONTEXT_CREATION_EVENT');assert.ok(out.excerpt.includes('EGL_NOT_INITIALIZED'));
 assert.ok(!out.excerpt.includes('unknownReason'));assert.ok(out.omittedTokens>0);
 assert.equal(safeNativeDetail('ANGLE error '+'z'.repeat(9000)),null);
});
