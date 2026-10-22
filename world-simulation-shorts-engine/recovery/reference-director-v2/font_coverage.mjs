/** Existing pinned font's actual cmap, not a general Unicode rendering promise. */
import coverage from './FONT_COVERAGE.json' with {type:'json'};
export const PINNED_FONT_COVERAGE=Object.freeze(coverage);
export function assertPinnedFontText(text){
 if(typeof text!=='string'||!text.trim())throw Error('DIRECTOR_PROGRAM_FONT_TEXT_REQUIRED');
 for(const character of text){
  const codePoint=character.codePointAt(0);let left=0,right=coverage.ranges.length-1,found=false;
  while(left<=right){const middle=(left+right)>>1,[a,b]=coverage.ranges[middle];if(codePoint<a)right=middle-1;else if(codePoint>b)left=middle+1;else {found=true;break;}}
  if(!found)throw Error('DIRECTOR_PROGRAM_FONT_CODEPOINT_UNSUPPORTED_U_'+codePoint.toString(16).toUpperCase());
 }
 return {fontSHA256:coverage.fontSHA256,codePointsVerified:true,sequenceShapingVerified:false};
}
