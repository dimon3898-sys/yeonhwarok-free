import assert from 'node:assert/strict';
import {historicalTime, historicalRange, timeWithin, timeBefore, timeIntersectsRange, historicalTimeLabel} from '../../web/map_infographic_v1/historical_time_v1.mjs';
const checks=[];function check(name,fn){fn();checks.push(name);}
check('year retains precision and label',()=>{assert.equal(historicalTime('1206').precision,'YEAR');assert.equal(historicalTimeLabel('1206'),'1206');});
check('year and inclusive range membership',()=>{assert.ok(timeWithin('1259',{start:'1206',end:'1259'}));assert.ok(!timeWithin('1260',{start:'1206',end:'1259'}));});
check('month without day is accepted',()=>{assert.equal(historicalTime('1950-06').precision,'MONTH');assert.ok(timeWithin('1950-06-25',{start:'1950-06',end:'1950-06'}));});
check('legacy leap day remains a point',()=>{const t=historicalTime('2000-02-29');assert.equal(t.lower,t.upper);assert.equal(historicalTimeLabel('1950-06-25'),'1950-06-25');});
check('impossible days and year zero rejected',()=>{for(const t of ['1900-02-29','1950-02-30','1206-13','0000','circa 1206'])assert.throws(()=>historicalTime(t));});
check('BCE order and no historical year zero',()=>{assert.ok(timeBefore({year:44,era:'BCE'},{year:1,era:'BCE'}));assert.ok(timeBefore({year:1,era:'BCE'},'0001'));assert.throws(()=>historicalTime({year:0,era:'BCE'}));});
check('bounded uncertainty preserved, not converted to date',()=>{const v={earliest:'1190',latest:'1210',uncertain:true,label:'약 1200년'};assert.equal(historicalTime(v).uncertain,true);assert.equal(historicalTimeLabel(v),'약 1200년');assert.ok(!timeBefore(v,'1206'));});
check('range precision and overlaps',()=>{assert.equal(historicalTime({start:'1206',end:'1209'}).precision,'RANGE');assert.ok(timeBefore({start:'1206',end:'1209'},'1210'));assert.ok(timeIntersectsRange('1259',{start:'1206',end:'1259'}));});
check('reversed and ambiguous malformed ranges rejected',()=>{assert.throws(()=>historicalRange({start:'1259',end:'1206'}));assert.throws(()=>historicalTime({start:'1206',end:'1209',earliest:'1205'}));});
check('month/year precision fields cannot silently disappear',()=>{assert.throws(()=>historicalTime({year:1206,month:3,precision:'YEAR'}));assert.throws(()=>historicalTime({year:1206,precision:'DAY'}));});
console.log(JSON.stringify({status:'PASS',scope:'new historical time precision and date compatibility only',checks},null,2));
