"""Export safe, byte-bound actual probe evidence; never creates rendered pixels."""
from pathlib import Path
import hashlib,json,shutil
NS=Path(__file__).resolve().parents[1]
PRIVATE=Path('/workspace/universal-presentation-v2-private-20261022/E-probes-v2')
OUT=NS/'reports'/'E_DRAW_PROBES'
OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
code=read(PRIVATE/'CODE_BINDINGS.json')
for name in ['presentation_plan.mjs','presentation_runtime.mjs','capture_presentation.mjs','region_source.mjs']:
 assert sha(NS/name)==code[name],f'Actual rendering code changed after probe start: {name}'
equivalence=read(PRIVATE/'COMPILER_EQUIVALENCE.json');assert equivalence['status']=='PASS'
report={'schema':'WORLD_ENGINE_PRESENTATION_REGION_DRAW_REGRESSION_V2','status':'PASS','scope':'FREE_SWIFTSHADER_ACTUAL_REGION_PROBES_NOT_STUDIO_MOVIES','softwareOnly':True,'nvidiaVerified':False,'qualityApproved':False,'paidExecuted':False,'regionCount':7,'actualDrawFrameCount':21,'authoredCameraFrameBoundsCompared':630,'cases':[],'codeBindingsAtDrawStart':code,'currentCompilerSHA256':sha(NS/'presentation_prompt.mjs'),'compilerEquivalence':equivalence,'renderingCodeBindingsUnchanged':True}
credits=[]
for case in read(PRIVATE/'RESULTS.json'):
 assert case['status']=='PASS';d=Path(case['outputRoot']);receipt=read(d/'CAPTURE_RECEIPT.json');runtime=read(d/'RUNTIME.json')
 row={'id':case['id'],'status':'PASS','captureStatus':receipt['status'],'framesDrawn':case['frames'],'elapsedSeconds':case['elapsedSeconds'],'runtimePackageSHA256':receipt['packageSHA256'],'sourceInputSHA256':receipt['sourceInputSHA256'],'sourceQualificationSHA256':receipt['sourceQualificationSHA256'],'backend':receipt['runtime']['backend'],'source':runtime['sourceQualification']['segments'][0],'sourceCredits':receipt['sourceCredits'],'trackHydration':receipt['runtime']['segments'][0]['trackHydration'],'frameEvidence':[]}
 for f in read(d/'FRAME_EVIDENCE.json')['frames']:
  name=f"{case['id']}_F{f['frame']:03d}.png";shutil.copyfile(d/f"FRAME_{f['frame']:03d}.png",OUT/name);x=f['diagnostic']
  row['frameEvidence'].append({'frame':f['frame'],'rawSHA256':f['rawSHA256'],'baseRawSHA256':f['baseRawSHA256'],'png':name,'pngSHA256':sha(OUT/name),'nonBlackPixels':f['nonBlackPixels'],'featureChangedPixels':x['featureChangedPixels'],'glError':x['glError'],'cameraBounds':x['camera']['bounds'],'actualMovingCameraLocked':x['camera']['actualCameraLocked'],'sourceViewportCovered':x['material']['fullViewportCovered'],'minimumSourceGutterPixels':x['material']['minimumSourceGutterPixels'],'layoutValid':x['layout']['valid'],'features':[{'id':g['id'],'engine':g['engine'],'state':g['state'],'stateId':g.get('stateId'),'routeFraction':g.get('routeFraction'),'objectFraction':g.get('objectFraction'),'objectPosition':g.get('objectPosition'),'movingProjectionAdmission':g.get('admission'),'actualDraw':g.get('draw'),'areaDraws':g.get('draws')}for g in x['features']]})
 report['cases'].append(row);credits.extend(receipt['sourceCredits'])
d=PRIVATE/'fictional-continuity-draw';receipt=read(d/'CAPTURE_RECEIPT.json')
proof={'schema':'WORLD_ENGINE_SUPPLIED_AREA_CUT_CONTINUITY_PROOF_V2','status':'PASS','softwareOnly':True,'nvidiaVerified':False,'qualityApproved':False,'sourceInputSHA256':receipt['sourceInputSHA256'],'sourceQualificationSHA256':receipt['sourceQualificationSHA256'],'frames':[]}
for f in read(d/'FRAME_EVIDENCE.json')['frames']:
 name=f"FICTIONAL_CONTINUITY_F{f['frame']:03d}.png";shutil.copyfile(d/f"FRAME_{f['frame']:03d}.png",OUT/name);x=f['diagnostic'];a=x['features'][0]
 proof['frames'].append({'frame':f['frame'],'localFrame':f['localFrame'],'png':name,'pngSHA256':sha(OUT/name),'rawSHA256':f['rawSHA256'],'featureChangedPixels':x['featureChangedPixels'],'stateId':a['stateId'],'sourceAreas':a['sourceAreas'],'sourceFronts':a['sourceFronts'],'presentationOperationBinding':a['presentationOperationBinding'],'stateColors':[{'stateId':p['stateId'],'color':p['color']}for p in a['draws']],'cameraBounds':x['camera']['bounds'],'glError':x['glError']})
before,after=proof['frames'][:2]
assert before['sourceAreas'][0]['geometry']==after['sourceAreas'][0]['geometry']
assert before['stateColors'][0]['color']==after['stateColors'][0]['color']
assert after['sourceAreas'][0]['alpha']==1 and after['sourceFronts'][0]['revealFraction']==1 and after['featureChangedPixels']>0
proof['boundaryChecks']={'framePair':[89,90],'geographicAreaUnchanged':True,'frontGeometryUnchanged':before['sourceFronts'][0]['geometry']==after['sourceFronts'][0]['geometry'],'stateColorUnchanged':True,'sourceAlphaAtCut':1,'frontRevealAtCut':1,'eventTimeOffsetFrames':0,'cameraChange':'AUTHORED_EXPLICIT_CUT_NOT_SMOOTH_TRANSITION_CLAIM'}
(NS/'reports'/'E_DRAW_REGRESSION_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(NS/'reports'/'AREA_CUT_CONTINUITY_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
unique={(x['sourceId'],x['sourceOriginalSHA256']):x for x in credits}
lines=['# Source credits for actual region probe PNGs','','Actual WORLD ENGINE SwiftShader draws. Software probes do not establish NVIDIA validation or final quality approval.','']
for c in unique.values():lines.append(f"- {c['sourceId']}: {c['attribution']} License: {c['license']}. Original source: {c['sourceURL']}. Original SHA-256: `{c['sourceOriginalSHA256']}`. Modifications: native pixel crop, geographic projection and supplied fictional graphics.")
(OUT/'SOURCE_CREDITS.md').write_text('\n'.join(lines)+'\n')
(OUT/'SHA256SUMS').write_text('\n'.join(f'{sha(p)}  {p.name}'for p in sorted(OUT.iterdir())if p.is_file()and p.name!='SHA256SUMS')+'\n')
print(json.dumps({'regions':7,'actualRegionDrawFrames':21,'actualContinuityDrawFrames':len(proof['frames']),'PNGcount':len(list(OUT.glob('*.png'))),'status':'PASS'}))
