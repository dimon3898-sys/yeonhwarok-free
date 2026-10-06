"""Versioned 12-second timing/audio polish; never starts a render itself."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import sys

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from engine.assets import sha256_file,validate_assets,renderer_version
from engine.backends import quality_settings
from engine.rendering import scene_cache_key
from engine.rhythm import apply_rhythm_policy,validate_rhythm_plan
from engine.rhythm_sound import catalog
from engine.schema import validate_plan
from engine.storage import ProjectStore,atomic_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=str(APP/'projects-production-default-v1/project_f185ebb678ea/versions/v003/scene_plan.json'))
    parser.add_argument('--projects',default=str(APP/'projects-rhythm-master-v1'))
    parser.add_argument('--evidence',required=True)
    args=parser.parse_args();source=Path(args.source).resolve();evidence=Path(args.evidence).resolve()
    if evidence.exists():raise FileExistsError('Evidence exists; preserve it and use a new directory')
    original=json.loads(source.read_text());digest=sha256_file(source)
    if original['duration']!=12 or len(original['scenes'])!=5:raise ValueError('Use the preserved five-scene 12-second Production sample')
    working=deepcopy(original)
    working['options'].update(tts=False,subtitles=False,bgm=True,sfx=True)
    working['request'].update(tts=False,subtitles=False,bgm=True,sfx=True)
    plan=apply_rhythm_policy(working,preserve_earth_pixels=True)
    plan['rhythm_policy']['sfx_library_content_sha256']=catalog()['library_content_sha256']
    metadata=plan.setdefault('metadata',{})
    metadata['rhythm_sample_render_authorization']=dict(maximum_duration=15,renderable_scene_ids=[s['scene_id'] for s in plan['scenes'] if s.get('rhythm_visual')])
    metadata['approved_rhythm_source']=dict(path=str(source),sha256=digest,project_id=original['project_id'],version=original['version'])
    metadata.pop('estimates',None)
    gate=validate_plan(plan)
    evidence.mkdir(parents=True);atomic_json(evidence/'CANDIDATE_GATE.json',gate,True)
    if not gate['passed']:raise ValueError(json.dumps(gate['errors'],ensure_ascii=False))
    # Check the incoming Earth scene uses the exact previous visual cache key.
    earth=plan['scenes'][-1];old_earth=original['scenes'][-1]
    source_results=json.loads((source.parent/'renders/scene_results.json').read_text())
    saved=next(s for s in source_results['scenes'] if s['scene_id']==earth['scene_id'])
    assets=validate_assets(plan)
    if not assets['passed']:raise ValueError(json.dumps(assets['errors']))
    from engine.assets import asset_registry
    original_ids={a['id'] for a in asset_registry()}
    earth_assets={**assets,'assets':[a for a in assets['assets'] if a['id'] in original_ids]}
    settings=quality_settings(earth['render_quality'],earth)
    key=scene_cache_key(earth,earth_assets,settings,renderer_version(earth),saved['render_context'])
    if key!=saved['cache_key'] or not (APP/'cache/scenes'/key/'cache.json').is_file():
        raise ValueError('EARTH_CACHE_NOT_REUSABLE: do not start an expensive replacement render')
    proof=dict(source=str(source),source_sha256=digest,source_unchanged=sha256_file(source)==digest,
        duration=plan['duration'],no_75s_render=True,no_master_render=True,whole_video_speedup=False,
        earth_renderer_unchanged=renderer_version(earth)==renderer_version(old_earth),
        earth_cached_key=key,earth_cached_movie_sha256=saved['video_sha256'],
        renderable_scene_ids=metadata['rhythm_sample_render_authorization']['renderable_scene_ids'],
        rhythm_metrics=validate_rhythm_plan(plan)['metrics'],render_started=False)
    atomic_json(evidence/'PRESERVED_EARTH_CACHE_PROOF.json',proof,True)
    result=ProjectStore(args.projects).create(plan['request'],plan)
    proof.update(project_id=result['project']['id'],version=result['version'],
        plan=str(ProjectStore(args.projects).version_path(result['project']['id'],result['version'])/'scene_plan.json'))
    atomic_json(evidence/'PROJECT_CREATED.json',proof,True)
    print(json.dumps(proof,ensure_ascii=False))


if __name__=='__main__':main()
