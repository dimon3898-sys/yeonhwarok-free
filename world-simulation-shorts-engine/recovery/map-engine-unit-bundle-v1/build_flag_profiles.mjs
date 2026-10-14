/** Authored national-flag geometry, separate from original marker artwork.
 * Flag proportions and symbols are public national designs, not copied video art.
 * Public modern actors and private historical checks select different profiles.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const rect = (x,y,width,height,fill) => ({type:'rect',x,y,width,height,fill});
const star = (cx,cy,radius,fill,rotation=0) => ({type:'star',cx,cy,radius,fill,rotation});
const polygon = (points,fill) => ({type:'polygon',points,fill});
const flag = (id,country_id,aspect_ratio,valid_from,traits,flag_geometry,extra={}) => ({
 id,country_id,aspect_ratio,valid_from,traits,flag_geometry,
 artwork:'WORLD_ENGINE_ORIGINAL_ROUNDED_TABLET',default_role:'GROUND',
 flag_authorship:'AUTHORED_STANDARD_NATIONAL_SYMBOLS_NOT_REFERENCE_BADGE_ART',
 era_geometry_certificate:false,...extra});

function us(starCount) {
 const ratio=1.9, stripe=1/13, geometry=[rect(0,0,ratio,1,'#ffffff')];
 for(let row=0;row<13;row+=2)geometry.push(rect(0,row*stripe,ratio,stripe,'#b22234'));
 geometry.push(rect(0,0,ratio*.4,stripe*7,'#3c3b6e'));
 const rows=starCount===48?6:9;
 for(let row=0;row<rows;row++) {
  const columns=starCount===48?8:row%2===0?6:5;
  for(let column=0;column<columns;column++) {
   const cx=starCount===48?(column+.5)*ratio*.4/8
    :(column+(columns===6?.5:1))*ratio*.4/6;
   geometry.push(star(cx,(row+.5)*stripe*7/rows,.0205,'#ffffff'));
  }
 }
 return geometry;
}

function rok() {
 const k=.5522847498307936,r=.25;
 const geometry=[rect(0,0,1.5,1,'#ffffff'),{
  type:'group',translate:[.75,.5],rotation:-Math.atan2(2,3),shapes:[
   {type:'circle',cx:0,cy:0,radius:r,fill:'#0047a0'},
   {type:'path',commands:[['M',-r,0],['C',-r,-k*r,-k*r,-r,0,-r],
    ['C',k*r,-r,r,-k*r,r,0],['C',r,k*r/2,r/2+k*r/2,r/2,r/2,r/2],
    ['C',r/2-k*r/2,r/2,0,k*r/2,0,0],
    ['C',0,-k*r/2,-r/2+k*r/2,-r/2,-r/2,-r/2],
    ['C',-r/2-k*r/2,-r/2,-r,-k*r/2,-r,0],['Z']],fill:'#cd2e3a'},
  ]}];
 const trigrams=[
  {center:[.285,.215],rotation:-Math.atan2(3,2),broken:[false,false,false]},
  {center:[1.215,.215],rotation:Math.atan2(3,2),broken:[true,false,true]},
  {center:[.285,.785],rotation:Math.atan2(3,2),broken:[false,true,false]},
  {center:[1.215,.785],rotation:-Math.atan2(3,2),broken:[true,true,true]},
 ];
 for(const {center,rotation,broken} of trigrams) {
  const shapes=[];
  broken.forEach((split,row)=> {
   const y=(row-1)*.052-.017;
   if(split)shapes.push(rect(-.125,y,.112,.034,'#101316'),rect(.013,y,.112,.034,'#101316'));
   else shapes.push(rect(-.125,y,.25,.034,'#101316'));
  });
  geometry.push({type:'group',translate:center,rotation,shapes});
 }
 return geometry;
}

function prc() {
 const geometry=[rect(0,0,1.5,1,'#de2910'),star(.25,.25,.15,'#ffde00')];
 for(const [cx,cy] of [[.5,.1],[.6,.2],[.6,.35],[.5,.45]])
  geometry.push(star(cx,cy,.05,'#ffde00',Math.atan2(.25-cy,.25-cx)+Math.PI/2));
 return geometry;
}

function dprk() {
 return [rect(0,0,2,1,'#024fa2'),rect(0,1/6,2,2/3,'#ffffff'),
  rect(0,5/24,2,7/12,'#ed1c27'),{type:'circle',cx:.5,cy:.5,radius:.2,fill:'#ffffff'},
  star(.5,.5,.184,'#ed1c27')];
}

function ussr() {
 const gold='#ffd64b';
 return [rect(0,0,2,1,'#cc0000'),
  {type:'star',cx:.34,cy:.13,radius:.075,inner_radius:.031,
   fill:'#cc0000',stroke:gold,stroke_width:.018},
  // The recognisable national hammer/sickle emblem is independent of unit art.
  {type:'path',commands:[['M',.24,.245],['C',.44,.245,.53,.39,.46,.505],
   ['C',.415,.59,.28,.61,.18,.515],['L',.21,.475],
   ['C',.28,.535,.375,.53,.405,.465],['C',.448,.38,.38,.29,.29,.27],['Z']],fill:gold},
  polygon([[.195,.257],[.229,.223],[.495,.489],[.461,.523]],gold),
  polygon([[.145,.215],[.225,.135],[.33,.24],[.25,.32]],gold),
 ];
}

const profiles={
 ROK_1949_TAEGEUK:flag('ROK_1949_TAEGEUK','ROK',1.5,'1949-10-15',
  {taegeuk:true,trigram_count:4},rok(),{historical_check:'CORRECT_NATIONAL_ELEMENTS_NOT_SURVEY_OF_EVERY_1949_FLAG_SPECIMEN'}),
 US_MODERN_50_STAR:flag('US_MODERN_50_STAR','US',1.9,'1960-07-04',
  {star_count:50,star_rows:9,alternating_star_columns:[6,5]},us(50)),
 US_1950_48_STAR:flag('US_1950_48_STAR','US',1.9,'1912-07-04',
  {star_count:48,star_rows:6,star_columns:8},us(48),{valid_to:'1959-07-03',private_only:true}),
 DPRK_1948:flag('DPRK_1948','DPRK',2,'1948-09-08',
  {star_count:1,white_disk:true,blue_white_red_horizontal:true},dprk()),
 PRC_1949:flag('PRC_1949','PRC',1.5,'1949-10-01',
  {star_count:5,small_stars_point_toward_large:true},prc()),
 RUS_MODERN_TRICOLOR:flag('RUS_MODERN_TRICOLOR','RUS',1.5,'1991-08-22',
  {modern_tricolor:true,band_order:['WHITE','BLUE','RED']},[
   rect(0,0,1.5,1/3,'#ffffff'),rect(0,1/3,1.5,1/3,'#0039a6'),rect(0,2/3,1.5,1/3,'#d52b1e')]),
 USSR_1936:flag('USSR_1936','USSR',2,'1936-12-05',
  {hammer_sickle:true,outlined_star:true,modern_tricolor:false},ussr(),{
   valid_to:'1955-08-18',private_only:true,default_role:'AVIATION',
   historical_check:'AUTHORED_PERIOD_NATIONAL_EMBLEM_NOT_AN_OFFICIAL_FLAG_ASSET_CERTIFICATE'}),
};
const result={schema:'WORLD_ENGINE_NATIONAL_FLAG_PROFILES_V1',coordinate_units:'FLAG_HEIGHT',profiles,
 public_semantics:'MODERN_COUNTERFACTUAL_VISUAL_STUDY_NOT_REAL_KOREAN_WAR',
 historical_profiles:'PRIVATE_DATE_ROLE_TESTS_ONLY',
 originality:'ORIGINAL_UNIT_CONTAINER_AND_ABSTRACT_ROLE_GLYPH_STANDARD_NATIONAL_FLAG_SYMBOLS',
 source_reference_icon_copied:false,source_reference_pixel_copied:false,
 flag_visual_verification:'REQUIRES_ACTUAL_PRIVATE_CANVAS_SHEET',
 no_rendered_text:true};
fs.mkdirSync(path.join(root,'fixtures'),{recursive:true});
fs.writeFileSync(path.join(root,'fixtures/NATIONAL_FLAG_PROFILES.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:'PROFILES_WRITTEN',profiles:Object.keys(profiles).length,
 publicModern:5,historicalOnly:2,us48stars:profiles.US_1950_48_STAR.flag_geometry.filter(s=>s.type==='star').length,
 us50stars:profiles.US_MODERN_50_STAR.flag_geometry.filter(s=>s.type==='star').length}));
