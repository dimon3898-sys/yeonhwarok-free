#!/usr/bin/env python3
"""Persist the glow-only Candidate inventory without rendering or FINAL gates.

Read-only parent hash/LFS, AST and asset readers are reused in memory. Only
--write-manifests writes, exclusively under this new Candidate/manifests.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

REPO=Path(__file__).resolve().parents[3]
ENGINE='world-simulation-shorts-engine'
BASE=ENGINE+'/recovery/moving-frontier-glow-fix-v1'
PARENT_BASE=ENGINE+'/recovery/map-engine-unit-bundle-v1'
PARENT='8e2b994755330907ceed9b9bfcc922e9b113138d'
BRANCH='development/moving-frontier-glow-fix-20261014'
SCOPE='MOVING_FRONTIER_GLOW_FIX_V1'
MP4='WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4'
BASELINE_MP4='WORLD_ENGINE_MAP_ENGINE_UNIT_BUNDLE_5S.mp4'
BASELINE_SHA='4f1b676baef6a4ba6fefbfd58a5d6b2e235fb57ada7d11cfd2baf827ec79f12e'
REFERENCE=ENGINE+'/recovery/reference-reproduction-v1/data/REFERENCE_65379_COMPRESSED.mp4'
REFERENCE_SHA='5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6'
PUBLIC_NAMES={MP4,'COMPARE_01_START.png','COMPARE_02_ADVANCE.png','COMPARE_03_TRACKING.png',
 'COMPARE_04_CONTINUOUS_CONTROL.png','COMPARE_05_END.png','SHA256SUMS'}
GLOW_KEYS={'profileName','centerColor','haloColor','centerWidthPixels','haloSigmaPixels',
 'haloSupportPixels','centerAlpha','haloAlpha','settledStrength','velocityWindowFrames'}
POSTSAVE_NAMES={'HTTP_DOWNLOAD_VERIFY.json','PERSISTENCE_VERIFICATION.json','REMOTE_VERIFICATION.json',
 'POST_COMMIT_VERIFICATION.json','FINAL_PERSISTENCE.json','POST_SAVE_VERIFICATION.json',
 'SOURCE_AFTER_SECRET_SCAN.json','POST_SCAN_SOURCE_CHECK.json','SECRET_SCAN.json',
 'SECRET_SCAN_SOURCE.json','SECRET_SCAN_PUBLIC.json','SECRET_SCAN_IMPLEMENTATION.json',
 'SECRET_SCAN_PRE_RENDER.json','SECRET_SCAN_CANDIDATE.json','SECRET_SCAN_FINAL_REPORT.json',
 'SECRET_SCAN_A.json','SECRET_SCAN_B.json'}

def require(condition,reason):
 if not condition:raise ValueError('MOVING_FRONTIER_STORAGE: '+reason)

def git(*args):
 return subprocess.check_output(['git',*args],cwd=REPO,stderr=subprocess.PIPE)

def sha(value):return hashlib.sha256(value).hexdigest()

def readonly_helpers():
 relative=PARENT_BASE+'/build_candidate_manifest.py'
 require((REPO/relative).read_bytes()==git('show',PARENT+':'+relative),'PARENT_INVENTORY_READER_CHANGED')
 spec=importlib.util.spec_from_file_location('readonly_glow_parent_inventory',REPO/relative)
 parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
 parent.BASE,parent.PARENT=BASE,PARENT
 parent.H.BASE=BASE
 parent.H.V2=ENGINE+'/recovery/planner-scene-json-v1'
 parent.H.NEW_MODULES=[];parent.H.NEW_TESTS=[]
 return parent

P=readonly_helpers();H=P.H
record,encode=H.record,H.encode

def load(relative):return json.loads(H.HELPER.safe_file(relative).read_text())

def protection():
 original=set(git('ls-tree','-r','--name-only',PARENT).decode().splitlines())
 changed=set(git('diff','--no-ext-diff','--name-only',PARENT).decode().splitlines())
 committed=set(git('diff','--no-ext-diff','--name-only',PARENT,'HEAD').decode().splitlines())
 require(not original&changed,'PREEXISTING_TRACKED_BODY_CHANGED: '+','.join(sorted(original&changed)))
 require(not original&committed,'PREEXISTING_COMMITTED_BODY_CHANGED')
 require(git('merge-base',PARENT,'HEAD').decode().strip()==PARENT,'WRONG_DEVELOPMENT_PARENT')
 return {'comparison_parent_commit':PARENT,'original_tracked_paths':len(original),
  'changed_original_paths':[],'committed_original_changes':[],'worktree_and_head_compared':True,
  'new_engine_modules':0,'camera_renderer_control_geometry_terrain_units':'UNCHANGED'}

def exclusions():
 return {BASE+'/CHECKPOINT_STATUS.json',*(BASE+'/evidence/'+name for name in POSTSAVE_NAMES)}

def candidate_paths(excluded):
 result=[]
 for file in (REPO/BASE).rglob('*'):
  parts=file.relative_to(REPO/BASE).parts
  if not file.is_file() or any(p in {'manifests','__pycache__','.pytest_cache'} for p in parts):continue
  relative=file.relative_to(REPO).as_posix();H.HELPER.safe_file(relative)
  if relative in excluded:continue
  if file.parent==(REPO/BASE/'evidence') and re.fullmatch(r'SECRET_SCAN_[A-Z0-9_]+\.json',file.name):continue
  result.append(relative)
 return sorted(result)

def locked_scene():
 relative=BASE+'/fixtures/SCENE_PLAN.json';scene=load(relative)
 prior_path=PARENT_BASE+'/fixtures/SCENE_PLAN.json';prior=load(prior_path)
 H.protected_record(PARENT,prior_path)
 require(scene.get('version')==scene.get('schema')=='MAP_ENGINE_UNIT_SCENE_V4','PRIVATE_EXECUTED_SCENE_VERSION')
 require(scene=={**prior,'frontierProfile':scene.get('frontierProfile')},'NON_GLOW_SCENE_FIELD_CHANGED')
 current=scene.get('frontierProfile');old=prior.get('frontierProfile')
 require(isinstance(current,dict) and isinstance(old,dict),'GLOW_PROFILE_REQUIRED')
 require({k:v for k,v in current.items() if k not in GLOW_KEYS}=={k:v for k,v in old.items() if k not in GLOW_KEYS},
  'TERRAIN_LIGHT_OR_OTHER_FRONTIER_PASS_PROPERTY_CHANGED')
 require(scene['metadata']['semanticMode']=='COUNTERFACTUAL_REFERENCE_VISUAL_STUDY_NOT_KOREAN_WAR_HISTORY',
  'PUBLIC_SEMANTICS_CHANGED')
 require(scene['metadata']['output']=={'width':1080,'height':1920,'fps':30,'audio':False},'OUTPUT_CONTRACT')
 return {'private_executed_scene':record(relative),'protected_parent_scene':record(prior_path),
  'changed_fields':sorted(k for k in set(current)|set(old) if current.get(k)!=old.get(k)),
  'allowed_changes':'CURRENT_REAL_BOUNDARY_GLOW_PROFILE_ONLY','terrain_relief_keys_locked':True,
  'scene_exported_to_public':False}

def input_binding():
 value=load(BASE+'/evidence/INPUT_BINDING.json')
 require(value.get('status')=='PASS' and value.get('actualRemoteHead')==PARENT,'VERIFIED_PARENT_INPUT_BINDING')
 require(value.get('candidate',{}).get('sha256')==BASELINE_SHA and
  value.get('reference',{}).get('sha256')==REFERENCE_SHA,'INPUT_SHA_DECLARATION_CHANGED')
 original=H.protected_record(PARENT,PARENT_BASE+'/public-review/'+BASELINE_MP4)
 reference=H.protected_record(PARENT,REFERENCE)
 require(original['sha256']==BASELINE_SHA and reference['sha256']==REFERENCE_SHA,'ORIGINAL_MEDIA_CHANGED')
 return {'protected_baseline_movie':original,'protected_reference':reference,
  'input_binding_evidence':record(BASE+'/evidence/INPUT_BINDING.json'),
  'reference_actual_prior_audit':H.protected_record(PARENT,ENGINE+'/recovery/reference-reproduction-v1/evidence/REFERENCE_AUDIT_SUMMARY.json'),
  'reference_redecode_claimed':False,'reference_reencoded':False,'baseline_reencoded':False}

def public_files():
 folder=REPO/BASE/'public-review';paths=sorted(folder.iterdir())
 require(all(p.is_file() and not p.is_symlink() for p in paths),'PUBLIC_DIRECTORY_MUST_CONTAIN_REGULAR_FILES_ONLY')
 require({p.name for p in paths}==PUBLIC_NAMES,'PUBLIC_EXACT_SEVEN_ALLOWLIST_NO_SCENE_SOURCE_DIAGNOSTICS')
 rows=[record(p.relative_to(REPO).as_posix()) for p in paths]
 sums=''.join(row['sha256']+'  '+Path(row['path']).name+'\n' for row in rows if Path(row['path']).name!='SHA256SUMS')
 require((folder/'SHA256SUMS').read_text()==sums,'PUBLIC_SHA256SUMS_BODY')
 declaration=load(BASE+'/evidence/PUBLIC_REVIEW_FILES.json')
 entries=declaration.get('files') if isinstance(declaration,dict) else declaration
 require(isinstance(entries,list) and len(entries)==7,'PUBLIC_DECLARATION_SEVEN_FILES_REQUIRED')
 require({r['file'] for r in entries}==PUBLIC_NAMES,'PUBLIC_DECLARATION_ALLOWLIST')
 for entry in entries:
  actual=next(row for row in rows if Path(row['path']).name==entry['file'])
  require(all(entry.get(k)==actual[k] for k in ['sha256','bytes']),'PUBLIC_DECLARATION_HASH_CHANGED')
 return rows

def proof_metadata():
 report_path=BASE+'/evidence/proof/REPORT.json';report=load(report_path)
 require(report.get('schema')=='MOVING_FRONTIER_GLOW_NATIVE_PROOF_V1' and report.get('status')=='PASS','ACTUAL_PROOF_NOT_PASS')
 source=report.get('sourceCommit')
 require(re.fullmatch('[0-9a-f]{40}',source or '') and git('merge-base',PARENT,source).decode().strip()==PARENT,'INVALID_RENDER_SOURCE_COMMIT')
 bindings=report.get('sourceBindings');require(isinstance(bindings,list) and bindings,'RENDER_BODY_BINDINGS_REQUIRED')
 bound=set()
 for item in bindings:
  relative=item.get('path');actual=record(relative);saved=H.HELPER.expected_body(source,relative)
  require(relative not in bound and all(actual[k]==item.get(k)==saved[k] for k in ['sha256','bytes']),
   'RENDER_SOURCE_BODY_CHANGED: '+str(relative));bound.add(relative)
 fixture=load(BASE+'/fixtures/RUNTIME_FIXTURE.json')
 required={BASE+'/fixtures/SCENE_PLAN.json',BASE+'/fixtures/RUNTIME_FIXTURE.json',
  PARENT_BASE+'/fixtures/SCENE_PLAN.json',*(ENGINE+'/'+p for p in fixture['runtimeModuleFiles'])}
 require(required<=bound,'RENDER_REQUIRED_PRIVATE_INPUT_CLOSURE_NOT_BOUND')
 require((report.get('totalFrames'),report.get('durationSeconds'),report.get('fps'),report.get('width'),report.get('height'))
  ==(150,5,30,1080,1920),'RENDER_FORMAT')
 require(report.get('audio') is False and report.get('finalPromotion') is False and report.get('permanentGateExecuted') is False,
  'CANDIDATE_SCOPE_OR_SILENT_VIDEO_CHANGED')
 rows=report.get('frames')
 require(isinstance(rows,list) and len(rows)==150 and all(r.get('frame')==i and r.get('glError')==0
  and r.get('sourceCommit')==source for i,r in enumerate(rows)),'RENDER_FRAME_ROWS_UNBOUND_OR_GL_FAILURE')
 video=record(BASE+'/public-review/'+MP4)
 require(report.get('video',{}).get('file')==MP4 and all(report['video'].get(k)==video[k] for k in ['sha256','bytes']),
  'ACTUAL_ORIGINAL_MP4_REPORT_BINDING')
 private_scene=record(BASE+'/fixtures/SCENE_PLAN.json')
 require(report.get('scene',{}).get('public') is False and
  all(report['scene'].get(k)==private_scene[k] for k in ['sha256','bytes']),'PRIVATE_SCENE_REPORT_BINDING')
 audit_path=BASE+'/evidence/CANDIDATE_AUDIT.json';audit=load(audit_path)
 require(audit.get('schema')=='MOVING_FRONTIER_GLOW_CANDIDATE_TECHNICAL_AUDIT_V1' and audit.get('status')=='PASS'
  and audit.get('decodedFrames')==150 and audit.get('candidateMp4Sha256')==video['sha256']
  and audit.get('sourceCommit')==source and audit.get('renderReportSha256')==record(report_path)['sha256'],
  'ACTUAL_FULL_DECODE_BINDING_MISSING')
 baseline_path=BASE+'/evidence/baseline_audit/REPORT.json';baseline=load(baseline_path)
 require(baseline.get('status')=='PASS' and baseline.get('inputSha256')==BASELINE_SHA
  and baseline.get('freshDecodedRelevantFrames')==150 and baseline.get('everyRelevantFrameMatchesPreservedRgbAudit') is True
  and baseline.get('inputUnchanged') is True and baseline.get('reencoded') is False,'BASELINE_150_RGB_PTS_REGRESSION_REQUIRED')
 return {'render_source_commit':source,'render_source_bodies':bindings,'render_report':record(report_path),
  'encoded_audit':record(audit_path),'baseline_actual_decode':record(baseline_path),'video':video,
  'public_review':public_files(),'actual_150_output_and_150_baseline_frames_decoded':True,
  'technical_pass_is_user_approval':False}

def documents(stage,excluded):
 protected=protection();paths=candidate_paths(excluded)
 fixture=load(BASE+'/fixtures/RUNTIME_FIXTURE.json')
 require(fixture.get('videoFilename')==MP4 and fixture.get('totalFrames')==150 and fixture.get('fps')==30,'RUNTIME_FIXTURE_FORMAT')
 declared=[ENGINE+'/'+p for p in fixture['runtimeModuleFiles']]
 for relative in declared:H.protected_record(PARENT,relative)
 H.NEW_MODULES=declared
 H.NEW_TESTS=[p for p in paths if Path(p).suffix=='.mjs' and (Path(p).stem.startswith('test_') or Path(p).name.endswith('.test.mjs'))]
 graph=H.import_graph(paths);assets=P.runtime_assets(graph)
 for relative in graph['browser_runtime_modules']:H.protected_record(PARENT,relative)
 deps_path=ENGINE+'/recovery/planner-night-run-v1/manifests/DEPENDENCY_MANIFEST.json'
 deps=load(deps_path);H.protected_record(PARENT,deps_path);installed=H.HELPER.toolchain(deps)
 helpers=[PARENT_BASE+'/build_candidate_manifest.py',ENGINE+'/recovery/event-v1-v3-visual-detail/build_candidate_manifest.py',
  ENGINE+'/recovery/event-v1-candidate-v2/validate_manifests.py','tools/v4_recovery_gate.py']
 source=sorted(set(graph['reachable_modules']+helpers+[p for p in paths if Path(p).suffix in {'.mjs','.py','.md','.txt','.sh','.lock'}]))
 fixtures=[p for p in paths if '/fixtures/' in p];data=[p for p in paths if '/data/' in p]
 evidence=sorted(set(paths)-set(source)-set(fixtures)-set(data))
 inputs=input_binding();scene=locked_scene();proof=proof_metadata() if stage=='candidate' else None
 common={'schema':1,'scope':SCOPE,'development_branch':BRANCH,'inventory_stage':stage,
  'status':'USER_VIDEO_REVIEW_REQUIRED' if stage=='candidate' else 'PROOF_RENDER_PENDING',
  'protection':protected,'required_temp_only_files':[],'event_final':False,'user_video_approved':False,
  'permanent_gate_executed':False,'postsave_report_exclusions':sorted(excluded),
  'all_secret_phase_receipts_excluded_from_recursive_hashes':True}
 def make(**fields):return {**common,**fields}
 return {
  'SOURCE_MANIFEST.json':make(entries=[record(p) for p in source],new_engine_modules=[],inherited_engine_modules=[record(p) for p in declared],focused_tests=[record(p) for p in H.NEW_TESTS]),
  'FIXTURE_MANIFEST.json':make(entries=[record(p) for p in fixtures],glow_only_scene_contract=scene,native_input_bodies=assets['native_input_bodies']),
  'DATA_MANIFEST.json':make(entries=[record(p) for p in data],**inputs,new_terrain_data=False,new_gis_geometry=False),
  'EVIDENCE_MANIFEST.json':make(entries=[record(p) for p in evidence],proof=proof,public_allowed_bodies=['MP4','five existing/new comparison PNG','SHA256SUMS'],public_scene_json=False),
  'RUNTIME_ASSET_MANIFEST.json':make(**assets),
  'DEPENDENCY_MANIFEST.json':make(parent=record(deps_path),dependencies=deps['dependencies'],interpreters=deps['interpreters'],setup=deps['setup'],dependency_locks=[H.verify_record(r) for r in deps['dependency_locks']],parser_provider=deps['parser_provider'],observed_toolchain=installed,additional_runtime_dependencies=[]),
  'IMPORT_MANIFEST.json':make(**graph),
  'BUILD_INPUT_MANIFEST.json':make(reused_hash_asset_ast_readers=[H.protected_record(PARENT,p) for p in helpers],terrain_regenerated=False,old_engine_modules_modified=False),
  'REPRODUCTION_MANIFEST.json':make(instructions=record(BASE+'/REPRODUCTION.md'),setup_recipe=deps['setup'],proof_argv=['node',BASE+'/render_proof.mjs','--source-commit=FULL_SAVED_SOURCE_COMMIT'],audit_argv=['/usr/bin/python3','-B',BASE+'/audit_candidate.py'],proof=proof,required_cache_or_tmp_inputs=False,final_gate_executed=False),
 }

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--stage',choices=['inputs','candidate'],default='inputs')
 parser.add_argument('--write-manifests',action='store_true')
 parser.add_argument('--inspect-only',action='store_true')
 parser.add_argument('--require-persisted',action='store_true')
 args=parser.parse_args()
 require(not args.inspect_only or not(args.write_manifests or args.require_persisted),'INSPECT_ONLY_CONFLICT')
 excluded=exclusions();docs=documents(args.stage,excluded);rows=H.inventory_of(docs,[],[])
 for relative,expected in list(rows.items()):
  actual=H.HELPER.record(relative);require(all(actual[k]==expected[k] for k in ['sha256','bytes']),'INPUT_CHANGED_DURING_INVENTORY: '+relative)
 bodies={name:encode(doc) for name,doc in docs.items()}
 for name,body in bodies.items():
  relative=BASE+'/manifests/'+name;rows[relative]={'path':relative,'sha256':sha(body),'bytes':len(body)}
 inventory=sorted(rows.values(),key=lambda r:r['path'])
 bodies['HASH_MANIFEST.json']=encode({'schema':1,'scope':SCOPE,'inventory_stage':args.stage,'required_files':inventory,
  'required_temp_only_files':[],'event_final':False,'user_video_approved':False,'permanent_gate_executed':False,
  'postsave_report_exclusions':sorted(excluded),'all_secret_phase_receipts_excluded_from_recursive_hashes':True,
  'self_hash_policy':'HASH_MANIFEST.json and manifests/SHA256SUMS excluded recursively; HEAD/index body verification still required.'})
 bodies['SHA256SUMS']=''.join(r['sha256']+'  '+r['path']+'\n' for r in inventory).encode()
 target=REPO/BASE/'manifests'
 if args.write_manifests:
  target.mkdir(parents=True,exist_ok=True)
  for name,body in bodies.items():(target/name).write_bytes(body)
 if not args.inspect_only:
  for name,body in bodies.items():require((target/name).read_bytes()==body,'MANIFEST_STALE_OR_CHANGED: '+name)
 persisted=sorted(set(rows)|{BASE+'/manifests/'+name for name in bodies})
 if args.require_persisted:
  for relative in persisted:H.verify_persisted(relative)
 print(json.dumps({'scope':SCOPE,'inventory_status':'PASS','inventory_stage':args.stage,'required_files':len(persisted),
  'reachable_import_modules':len(docs['IMPORT_MANIFEST.json']['reachable_modules']),
  'runtime_routes':len(docs['RUNTIME_ASSET_MANIFEST.json']['runtime_routes']),
  'original_tracked_paths':docs['SOURCE_MANIFEST.json']['protection']['original_tracked_paths'],
  'changed_original_paths':[],'new_engine_modules':0,'required_temp_only_files':0,
  'head_and_index_compared':args.require_persisted,'permanent_gate_executed':False,'public_files':7 if args.stage=='candidate' else 0},indent=2))

if __name__=='__main__':
 try:main()
 except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:raise SystemExit(str(error)) from None
