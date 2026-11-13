from pathlib import Path
import json,hashlib,subprocess
import jsonschema
base=Path(__file__).parent;e=base/'evidence';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
validator=jsonschema.Draft202012Validator(json.loads(Path('web/map_infographic_v1/planner_scene_v1.schema.json').read_text()));scene=json.loads((base/'FORMAL_SCENE.json').read_text());validator.validate(scene)
bad=json.loads(json.dumps(scene));bad['time_steps'][0]['area_ids']=[];assert not validator.is_valid(bad)
(e/'SCHEMA_TEST.json').write_text(json.dumps({'status':'PASS','checks':['actual8state Scene schema','both area and fronts empty rejected'],'actualSceneSHA256':sha(base/'FORMAL_SCENE.json')},indent=2)+'\n')
protected=[]
for name in ['japan-6s-universality-20261113','japan-6s-v2-20261113','japan-6s-v3-20261113','mongol-empire-6s-20261113']:
 path='world-simulation-shorts-engine/production/'+name
 assert not subprocess.check_output(['git','diff','--name-only','cf320e8fd7ffdfaf37654c0cc89434bb6c196839','--',path],cwd='..',text=True)
 cp=Path('production')/name/'CHECKPOINT.json';protected.append({'path':str(cp),'sha256':sha(cp),'historicalEvidenceUnmodified':True})
(e/'PRIOR_PASS_PRESERVATION.json').write_text(json.dumps({'status':'PASS_PRESERVED_NOT_RERUN','priorHEAD':'cf320e8fd7ffdfaf37654c0cc89434bb6c196839','japanFinal':'a30cfab2175338ad2676c735b3cd213fd1c0643e','proof':protected,'oldPassReruns':0,'scopeOfNewChecks':'changed date/source/state/projection/label contracts only; no Japan rendering rerun'},indent=2)+'\n')
cp={'status':'READY_FOR_FREE_CPU_REPRESENTATIVE_FRAMES','firstIncomplete':'CPU_REPRESENTATIVE_FRAME_VISUAL_REVIEW','baseHEAD':'cf320e8fd7ffdfaf37654c0cc89434bb6c196839','workBranch':'fix/reference-6s-formal-admission-20261113','completed':['date precision','territory-only states','historical reconstruction source admission','wide source and projection admission','formal Scene','automatic policy selection','changed common contracts and all-frame mathematical admission'],'technicalPass':False,'visualQualityPass':False,'userVisualApproval':'PENDING','gpuStarts':0,'oldPassReruns':0,'historicalSourceRecollected':False,'remaining':['free CPU representative frames','6second180frame MP4','all-frame actual pixel review','delivery and user visual approval'],'newCommonConnection':True,'newRenderer':False}
(base/'CHECKPOINT.json').write_text(json.dumps(cp,indent=2)+'\n')
(e/'CHANGE_SCOPE_AND_GATES.json').write_text(json.dumps({'protectedPriorPass':'valid prior artifacts preserved; no prior production rerun','newChecksReason':'new historical/time/state/source/region admission branches and common topology correction','topologyInvalidationEvidence':'new source Scene rejected isolated point-touch parts and islands inside another part hole; source geometries Shapely valid','minimalTopologyScope':'accept point contacts; reject crossings/shared edges/interior overlap;7 focused new cases','localCaptureSkipped':'prior known /workspace ancestor mode prevents strict private output root; use public GitHub free CPU runner, no same failing local capture repeated','schemaFailureResolved':'Runtime area-only admission passed but JSON schema still required fronts; matched schema and asserted empty-state rejection'},indent=2)+'\n')
changed=subprocess.check_output(['git','-C','..','diff','--name-only'],text=True).splitlines()+subprocess.check_output(['git','-C','..','ls-files','--others','--exclude-standard'],text=True).splitlines();files=[]
for f in changed:
 p=Path('..')/f
 if p.suffix=='.mjs':subprocess.run(['node','--check',str(p)],check=True,capture_output=True);files.append(f)
(e/'STATIC_CHECKS.json').write_text(json.dumps({'status':'PASS','syntaxFiles':files,'jsonSchemaActualScene':'PASS'},indent=2)+'\n')
print(json.dumps({'syntaxFiles':len(files),'schema':'PASS','protectedCheckpoints':len(protected)}))
