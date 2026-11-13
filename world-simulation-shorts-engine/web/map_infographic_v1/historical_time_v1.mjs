/** Historical precision is data. Bounds are comparison keys, never invented event dates. */
const own=(v,k)=>Object.prototype.hasOwnProperty.call(v,k);
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const check=(v,c)=>{if(!v)throw Error('HISTORICAL_TIME_'+c);};
const day=(y,m,d)=>{const date=new Date(0);date.setUTCFullYear(y,m-1,d);date.setUTCHours(0,0,0,0);return date.getTime()/86400000;};
const leap=y=>y%4===0&&(y%100!==0||y%400===0);
function point(value){
 let year,month,date,era='CE',precision;
 if(typeof value==='string'){
  const match=/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(value);
  check(match,'FORMAT_REQUIRED');year=Number(match[1]);month=match[2]&&Number(match[2]);date=match[3]&&Number(match[3]);
  precision=date!==undefined?'DAY':month!==undefined?'MONTH':'YEAR';
 }else{
  check(object(value)&&Object.keys(value).every(k=>['year','month','day','era','precision'].includes(k)),'POINT_FIELDS');
  ({year,month,day:date,era='CE',precision='YEAR'}=value);
  check(['YEAR','MONTH','DAY'].includes(precision),'PRECISION');
  check(precision==='YEAR'?month===undefined&&date===undefined:precision==='MONTH'?month!==undefined&&date===undefined:month!==undefined&&date!==undefined,'PRECISION_FIELDS');
 }
 check(Number.isSafeInteger(year)&&year>=1&&year<=9999&&['CE','BCE'].includes(era),'YEAR_ERA');
 const astro=era==='BCE'?1-year:year;
 const days=[31,leap(astro)?29:28,31,30,31,30,31,31,30,31,30,31];
 if(month!==undefined)check(Number.isSafeInteger(month)&&month>=1&&month<=12,'MONTH');
 if(date!==undefined)check(Number.isSafeInteger(date)&&date>=1&&date<=days[month-1],'DAY');
 return {lower:day(astro,month??1,date??1),upper:day(astro,month??12,date??days[(month??12)-1]),precision,uncertain:false};
}
export function historicalTime(value){
 if(object(value)&&(own(value,'start')||own(value,'end')||own(value,'earliest')||own(value,'latest'))){
  const uncertain=own(value,'earliest')||own(value,'latest');
  check(Object.keys(value).every(k=>(uncertain?['earliest','latest','uncertain','label']:['start','end']).includes(k)),'RANGE_FIELDS');
  if(uncertain)check(value.uncertain===true&&typeof value.label==='string'&&value.label.trim(),'UNCERTAINTY_BOUNDS_AND_LABEL');
  const a=point(value[uncertain?'earliest':'start']),b=point(value[uncertain?'latest':'end']);
  check(a.lower<=b.lower&&a.upper<=b.upper,'RANGE_ORDER');
  return {lower:a.lower,upper:b.upper,precision:uncertain?'UNCERTAIN':'RANGE',uncertain};
 }
 return point(value);
}
export function validHistoricalTime(value){try{historicalTime(value);return true;}catch{return false;}}
export function historicalRange(range){
 check(object(range)&&own(range,'start')&&own(range,'end'),'RANGE_REQUIRED');
 const a=historicalTime(range.start),b=historicalTime(range.end);
 check(a.lower<=b.lower&&a.upper<=b.upper,'RANGE_ORDER');
 return {lower:a.lower,upper:b.upper};
}
export function timeWithin(value,range){const a=historicalTime(value),b=historicalRange(range);return a.lower>=b.lower&&a.upper<=b.upper;}
export function timeBefore(a,b){return historicalTime(a).upper<historicalTime(b).lower;}
export function compareHistoricalTime(a,b){return historicalTime(a).lower-historicalTime(b).lower;}
export function timeIntersectsRange(value,range){const a=historicalTime(value),b=historicalRange(range);return a.lower<=b.upper&&a.upper>=b.lower;}
export function historicalTimeLabel(value){
 historicalTime(value);
 if(typeof value==='string')return value;
 if(own(value,'earliest'))return value.label;
 if(own(value,'start'))return historicalTimeLabel(value.start)+'-'+historicalTimeLabel(value.end);
 const year=String(value.year).padStart(4,'0'),suffix=value.era==='BCE'?' BCE':'';
 return year+(value.month===undefined?'':'-'+String(value.month).padStart(2,'0'))+(value.day===undefined?'':'-'+String(value.day).padStart(2,'0'))+suffix;
}
