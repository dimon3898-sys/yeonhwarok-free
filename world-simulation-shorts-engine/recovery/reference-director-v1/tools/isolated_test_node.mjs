/* Only relocate two fresh test output roots; source files/assertions stay intact. */
import {registerHooks} from 'node:module';
const root=process.env.REFERENCE_DIRECTOR_TEST_PRIVATE_ROOT;
if(!root?.startsWith('/workspace/reference-director-v1-private-20261022/'))throw Error('NEW_PRIVATE_TEST_ROOT_REQUIRED');
const substitutions=new Map([
 ['universal-presentation-v2/tests/region_source.test.mjs', ["'/workspace/region-provider-tests-'",JSON.stringify(root+'/region-provider-tests-')]],
 ['universal-presentation-v2/tests/test_presentation_preparation.mjs', ["'/workspace/up2-preparation-tests-'",JSON.stringify(root+'/up2-preparation-tests-')]],
]);
registerHooks({load(url,context,next){
 const loaded=next(url,context);
 for(const [suffix,[from,to]]of substitutions){
  if(url.endsWith(suffix)){
   const source=String(loaded.source);
   if(source.split(from).length!==2)throw Error('OUTPUT_ROOT_RELOCATION_EXPECTED_EXACTLY_ONCE');
   return {...loaded,source:source.replace(from,to)};
  }
 }
 return loaded;
}});
