/** Exact squared Euclidean distance to ink pixels in O(width*height).
 * Glyph-only preparation. No source/map/frame pixels are accepted by this API.
 */
export function glyphSquaredDistance(alpha,width,height){
 if(!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||width<1||height<1||width>1024||height>1024||width*height>1048576||!ArrayBuffer.isView(alpha)||alpha.length!==width*height)throw Error('DIRECTOR_GLYPH_DISTANCE_DIMENSIONS');
 if(!alpha.some(a=>a>0))throw Error('DIRECTOR_GLYPH_DISTANCE_EMPTY_INK');
 const size=Math.max(width,height),line=new Float64Array(size),out=new Float64Array(size),vertices=new Int32Array(size),breaks=new Float64Array(size+1),rows=new Float64Array(width*height),result=new Float32Array(width*height),far=1e12;
 function transform(n){
  let k=0;vertices[0]=0;breaks[0]=-Infinity;breaks[1]=Infinity;
  for(let q=1;q<n;q++){
   let p=vertices[k],cross=((line[q]+q*q)-(line[p]+p*p))/(2*(q-p));
   while(cross<=breaks[k]){k--;p=vertices[k];cross=((line[q]+q*q)-(line[p]+p*p))/(2*(q-p));}
   k++;vertices[k]=q;breaks[k]=cross;breaks[k+1]=Infinity;
  }
  k=0;for(let q=0;q<n;q++){while(breaks[k+1]<q)k++;const d=q-vertices[k];out[q]=d*d+line[vertices[k]];}
 }
 for(let y=0;y<height;y++){for(let x=0;x<width;x++)line[x]=alpha[y*width+x]>0?0:far;transform(width);for(let x=0;x<width;x++)rows[y*width+x]=out[x];}
 for(let x=0;x<width;x++){for(let y=0;y<height;y++)line[y]=rows[y*width+x];transform(height);for(let y=0;y<height;y++)result[y*width+x]=out[y];}
 return result;
}
