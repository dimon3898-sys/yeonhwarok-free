/** Pinned Acorn AST import inventory; no source evaluation or browser context. */
import {parse} from './vendor_acorn.mjs';
export function browserModuleImports(source){
 const ast=parse(source,{ecmaVersion:'latest',sourceType:'module'}),imports=[];let unsupportedDynamic=0;
 const pending=[ast];
 while(pending.length){const node=pending.pop();
  if(['ImportDeclaration','ExportNamedDeclaration','ExportAllDeclaration'].includes(node.type)&&node.source){
   if(node.source.type!=='Literal'||typeof node.source.value!=='string')throw Error('UP2_MODULE_STATIC_SPECIFIER');imports.push(node.source.value);
  }else if(node.type==='ImportExpression'){
   if(node.source.type==='Literal'&&typeof node.source.value==='string')imports.push(node.source.value);else unsupportedDynamic++;
  }
  for(const value of Object.values(node)){if(Array.isArray(value)){for(const child of value)if(child&&typeof child.type==='string')pending.push(child);}else if(value&&typeof value.type==='string')pending.push(value);}
 }
 return{imports,unsupportedDynamic};
}
