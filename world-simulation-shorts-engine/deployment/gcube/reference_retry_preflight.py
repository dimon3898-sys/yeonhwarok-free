"""Real encoded-file checkpoint/retry fixture with a controlled backend failure.

The backend transports existing synthetic MP4s; it never renders with a GPU/CPU
map backend. This isolates reuse, output attempts and final pipeline behavior.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch
from engine.assets import APP_ROOT
from engine.backends import CPULocalBackend
from engine.failures import RenderProcessError
from engine.pipeline_stability import render_project
from engine.storage import ProjectStore
from engine.qa_planner import configure_qa_schema

def run(media):
    configure_qa_schema()
    media=Path(media);source_plan=json.loads((media/'plan.json').read_text());poses=json.loads((media/'poses.json').read_text())['pose_records']
    calls=[];partial=[];fail=True
    with tempfile.TemporaryDirectory(prefix='real-mp4-retry-') as folder:
        root=Path(folder);store=ProjectStore(root/'projects');data=store.create(source_plan['request'],copy.deepcopy(source_plan));plan=data['plan'];pid=data['project']['id']
        store.approve(pid,'v001',plan['plan_hash']);project=store.version_path(pid,'v001')
        def backend(_self,command,cwd,progress):
            output=Path(command[command.index('--output')+1]);audit=Path(command[command.index('--audit')+1]);scene=json.loads(Path(command[command.index('--scene-json')+1]).read_text());sid=scene['scene_id'];calls.append(sid)
            if sid=='S002' and fail:
                output.write_bytes(b'controlled partial; retain this exact file')
                partial.append(output)
                raise RenderProcessError(returncode=1,duration=.01,stderr=['WORLD_ENGINE_RENDER_FAILURE '+json.dumps(dict(code='FRAME_AUDIT_FAILED',frame_index=0,failed_invariants=['CONTROLLED_TEST_FAILURE']))])
            shutil.copyfile(media/sid/'scene.mp4',output)
            audit.write_text(json.dumps([r for r in poses if r['scene_id']==sid]))
            output.with_suffix('.manifest.json').write_text(json.dumps(dict(complete=True,fixture_only=True,no_gpu_render=True)))
        with patch('engine.rendering.APP_ROOT',root/'cache-runtime'),patch.object(CPULocalBackend,'run',backend):
            try:render_project(project,plan,'http://127.0.0.1:8001')
            except RenderProcessError:pass
            else:raise AssertionError('Expected S002 controlled failure did not occur')
            assert calls==['S001','S002']
            checkpoint=json.loads((project/'renders/checkpoint.json').read_text());assert checkpoint['completed_scenes']==1
            results=json.loads((project/'renders/scene_results.json').read_text());first=Path(results['scenes'][0]['movie']);before=hashlib.sha256(first.read_bytes()).hexdigest()
            failed_hash=hashlib.sha256(partial[0].read_bytes()).hexdigest();fail=False;calls.clear()
            result=render_project(project,plan,'http://127.0.0.1:8001')
            assert calls==[s['scene_id'] for s in source_plan['scenes'][1:]],calls
            assert hashlib.sha256(first.read_bytes()).hexdigest()==before
            assert hashlib.sha256(partial[0].read_bytes()).hexdigest()==failed_hash
            assert result['scenes'][0]['reused'] is True
            assert Path(result['scenes'][1]['movie'])!=partial[0]
            assert result['qc']['passed'],result['qc']['failures']
            assert json.loads((project/'renders/checkpoint.json').read_text())['complete'] is True
        report=dict(passed=True,S001_byte_preserved=True,failed_partial_preserved=True,new_S002_attempt=True,retry_calls=calls,qc_passed=result['qc']['passed'],scope='Controlled S002 backend failure; real synthetic scene MP4s, real audio/concat/QC; no GPU/map draw claim')
        print(json.dumps(report));return report
if __name__=='__main__':
    import sys
    run(sys.argv[1])
