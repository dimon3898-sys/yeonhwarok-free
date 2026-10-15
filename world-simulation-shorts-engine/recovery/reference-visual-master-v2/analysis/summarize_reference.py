#!/usr/bin/env python3
"""Summarize saved full-frame numerical evidence; no video or renderer work."""
import argparse
import json
from pathlib import Path
import statistics


def summarize(metrics,saved_audit=None):
 rows=metrics['frames'];one_second=[]
 for second in range(int(metrics['containerDurationSeconds'])+1):
  subset=[r for r in rows if second<=r['ptsSeconds']<second+1]
  if not subset:continue
  one_second.append({'startSeconds':second,'endSeconds':min(second+1,metrics['containerDurationSeconds']),
   'sourceFrames':len(subset),'mapMeanAbsDelta':round(statistics.mean(r['mapMeanAbsDelta'] or 0 for r in subset),5),
   'orangeHueFraction':round(statistics.mean(r['fractions']['orangeHue'] for r in subset),7),
   'purpleHueFraction':round(statistics.mean(r['fractions']['purpleHue'] for r in subset),7),
   'whiteBrightFraction':round(statistics.mean(r['fractions']['whiteBright'] for r in subset),7),
   'goldBrightFraction':round(statistics.mean(r['fractions']['goldBright'] for r in subset),7),
   'goldAdjacentBothFactionHuesPixels':round(statistics.mean(r['goldAdjacentBothFactionHuesPixels'] for r in subset),3)})
 motion=[r['cameraTranslationProxy'] for r in rows[1:] if r['cameraTranslationProxy'] and
  r['cameraTranslationProxy'].get('status')=='MEASURED_TRANSLATION_PROXY_ONLY']
 result={'schema':'REFERENCE_FULL_MAP_TEMPORAL_SUMMARY_V2','status':'NUMERICAL_SUMMARY_COMPLETE',
  'sourceSHA256':metrics['sourceSHA256'],'decodedFrames':metrics['decodedFrames'],
  'durationSeconds':metrics['containerDurationSeconds'],'lastPTSSeconds':metrics['lastPTSSeconds'],
  'nativeDecode':{'exitCode':metrics['ffmpegExitCode'],'stderrBytes':metrics['ffmpegErrorBytes'],
   'sourceModified':metrics['sourceModified'],'strictIncreasingPTS':metrics['strictIncreasingPTS']},
  'temporalSummary':metrics['temporalSummary'],
  'cameraProxySummary':{'consecutiveTextureEstimates':len(motion),
   'nonzeroQuantizedTranslations':sum(v['dxSourcePixels']!=0 or v['dySourcePixels']!=0 for v in motion),
   'medianPhasePeak':round(statistics.median(v['phasePeak'] for v in motion),6),
   'medianPeakToSecond':round(statistics.median(v['peakToSecond'] for v in motion),4),
   'sourcePixelQuantization':4,'zeroEstimateDoesNotProveNoCameraMotion':True,
   'zoomRollAndTranslationNotIndependentlySolved':True},
  'highestChangeFrames':[{'frame':r['frame'],'ptsSeconds':r['ptsSeconds'],'mapMeanAbsDelta':r['mapMeanAbsDelta']}
   for r in sorted(rows[1:],key=lambda r:r['mapMeanAbsDelta'],reverse=True)[:15]],
  'oneSecondBins':one_second,
  'interpretationLimits':metrics['metricLimits']+[
   'No low-motion runs under the declared threshold does not independently prove that every event mechanism runs continuously.',
   'No exact first/last-frame equality is observed; semantic replay detection still needs visual review.',
   'National-flag ending graphics can satisfy faction hue predicates; ending hue fractions are not territorial area.',
   'Human inspection identifies a white moving inner front and gold static country/coast halo; the gold proxy does not merge these effects.'],
  'gpuExecuted':False,'rendererImplementationStarted':False,'publicProofGenerated':False}
 if saved_audit is not None:
  result['savedAuditCrosscheck']={'framesEqual':len(rows)==len(saved_audit),
   'allNativeRGBHashesEqual':len(rows)==len(saved_audit) and all(a['nativeRGBSHA256']==b['decoded_rgb_sha256'] for a,b in zip(rows,saved_audit)),
   'allPTSEqual':len(rows)==len(saved_audit) and all(a['ptsSeconds']==b['pts_seconds'] for a,b in zip(rows,saved_audit))}
 return result


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--metrics',type=Path,required=True)
 parser.add_argument('--saved-audit',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 result=summarize(json.loads(args.metrics.read_text()),None if args.saved_audit is None else json.loads(args.saved_audit.read_text()))
 with args.output.open('x') as output:json.dump(result,output,indent=2);output.write('\n')
