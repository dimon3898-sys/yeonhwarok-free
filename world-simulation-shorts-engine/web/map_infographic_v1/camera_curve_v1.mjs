/** Opt-in quintic least-squares camera curve. No scene, country or screen data. */
const check=(v,c)=>{if(!v)throw Error(c);};
function basis(t,knots,count){
 if(t===knots.at(-1)){const row=Array(count).fill(0);row[count-1]=1;return row;}
 let row=knots.slice(0,-1).map((x,i)=>t>=x&&t<knots[i+1]?1:0);
 for(let degree=1;degree<=5;degree++)row=row.slice(0,-1).map((_,i)=>{
  const a=knots[i+degree]-knots[i],b=knots[i+degree+1]-knots[i+1];
  return(a?(t-knots[i])/a*row[i]:0)+(b?(knots[i+degree+1]-t)/b*row[i+1]:0);
 });
 return row;
}
export function fitC2VectorSamples(samples,{knotSpacingFrames}={}){
 check(Array.isArray(samples)&&samples.length>=8&&samples.length<=36000,'CAMERA_CURVE_SAMPLE_COUNT');
 const dimensions=samples[0]?.length,end=samples.length-1;
 check(Number.isSafeInteger(dimensions)&&dimensions>0&&dimensions<=8&&samples.every(v=>Array.isArray(v)&&v.length===dimensions&&v.every(Number.isFinite)),'CAMERA_CURVE_VECTOR');
 check(Number.isSafeInteger(knotSpacingFrames)&&knotSpacingFrames>=3&&knotSpacingFrames<=120,'CAMERA_CURVE_SPACING');
 const knots=Array(6).fill(0);for(let t=knotSpacingFrames;t<end;t+=knotSpacingFrames)knots.push(t);knots.push(...Array(6).fill(end));
 const count=knots.length-6;check(count<=256,'CAMERA_CURVE_CONTROL_CAPACITY');
 // Clamping the last three controls gives exact position, zero velocity and
 // zero acceleration at the hold boundary. The first pose is also exact.
 const controls=Array.from({length:count},()=>Array(dimensions).fill(0));
 controls[0]=[...samples[0]];for(let i=count-3;i<count;i++)controls[i]=[...samples.at(-1)];
 const free=Array.from({length:count-4},(_,i)=>i+1),n=free.length;
 const normal=Array.from({length:n},()=>Array(n).fill(0)),rhs=Array.from({length:n},()=>Array(dimensions).fill(0));
 const rows=samples.map((_,f)=>basis(f,knots,count));
 for(let f=0;f<rows.length;f++){
  const row=rows[f],target=samples[f].map((v,d)=>v-row[0]*controls[0][d]-row.slice(count-3).reduce((s,w)=>s+w*samples.at(-1)[d],0));
  for(let a=0;a<n;a++){const wa=row[free[a]];if(!wa)continue;
   for(let d=0;d<dimensions;d++)rhs[a][d]+=wa*target[d];
   for(let b=0;b<=a;b++)normal[a][b]+=wa*row[free[b]];
  }
 }
 // Bounded positive-definite least squares; no runtime numerical dependency.
 const L=Array.from({length:n},()=>Array(n).fill(0));
 for(let i=0;i<n;i++)for(let j=0;j<=i;j++){
  let v=normal[i][j];for(let k=0;k<j;k++)v-=L[i][k]*L[j][k];
  if(i===j){check(v>1e-12,'CAMERA_CURVE_SINGULAR');L[i][j]=Math.sqrt(v);}else L[i][j]=v/L[j][j];
 }
 for(let d=0;d<dimensions;d++){
  const y=Array(n).fill(0),x=Array(n).fill(0);
  for(let i=0;i<n;i++){let v=rhs[i][d];for(let j=0;j<i;j++)v-=L[i][j]*y[j];y[i]=v/L[i][i];}
  for(let i=n-1;i>=0;i--){let v=y[i];for(let j=i+1;j<n;j++)v-=L[j][i]*x[j];x[i]=v/L[i][i];controls[free[i]][d]=x[i];}
 }
 const frames=rows.map(row=>Array.from({length:dimensions},(_,d)=>row.reduce((sum,w,i)=>sum+w*controls[i][d],0)));
 frames[0]=[...samples[0]];frames[end]=[...samples.at(-1)];
 return{frames,evidence:{mode:'QUINTIC_C2',degree:5,knotSpacingFrames,controls:count,interiorContinuity:'C4',holdVelocity:0,holdAcceleration:0}};
}
