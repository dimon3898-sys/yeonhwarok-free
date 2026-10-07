"""Preparation-only Suez20 image check. Never launches Chromium or FFmpeg."""
from pathlib import Path
import copy
import json
import subprocess
import tempfile
from unittest.mock import patch

from engine.backends import CPULocalBackend
from engine.failures import safe_tail
from engine.planner import generate_plan
from engine.rendering import render_project
from engine.storage import ProjectStore


class Prepared(Exception):
    pass


def main():
    request = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=20,
                   quality='HIGH', pace='FAST_PLUS', tts=False, subtitles=False, bgm=True, sfx=True)
    plan = generate_plan(request)
    if not plan['gate']['passed']:
        raise RuntimeError('RECONSTRUCTED_PLAN_GATE_FAILED')
    commands, events = [], []
    def capture(self, command, cwd, progress):
        commands.append(command)
        raise Prepared()
    with tempfile.TemporaryDirectory(prefix='world-preparation-only-') as directory:
        store = ProjectStore(Path(directory)/'projects')
        data = store.create(request, copy.deepcopy(plan))
        pid, plan = data['project']['id'], data['plan']
        store.approve(pid, 'v001', plan['plan_hash'])
        with patch('engine.rendering.create_audio', return_value={'file':'NOT_CREATED', 'narration_cues':[]}), \
             patch('engine.rendering.create_subtitles', return_value={}), \
             patch.object(CPULocalBackend, 'run', capture):
            try:
                render_project(store.version_path(pid, 'v001'), plan, 'http://127.0.0.1:8001', events.append)
            except Prepared:
                pass
        if len(commands) != 1 or events[-1].get('scene_id') != 'S001':
            raise RuntimeError('COLD_SCENE_PREPARATION_NOT_OBSERVED')
        command = commands[0]
        tool = Path(command[1])
        source = tool.read_text()
        marker = 'const started=Date.now();'
        if source.count(marker) != 1:
            raise RuntimeError('PREPARATION_BOUNDARY_CHANGED')
        prefix = source.split(marker, 1)[0]
        if 'chromium.launch' in prefix or "spawn('ffmpeg'" in prefix:
            raise RuntimeError('PREPARATION_BOUNDARY_UNSAFE')
        prefix = prefix.replace('fileURLToPath(import.meta.url)', json.dumps(str(tool)))
        prefix = 'process.argv.splice(1,0,' + json.dumps(str(tool)) + ');\n' + prefix
        result = subprocess.run(['node','--input-type=module','-e',prefix,'--',*command[2:]],
                                cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=90)
        evidence = dict(scope='Reconstructed Suez20 preparation/source hashing only; not actual gcube job or rendered pixels',
                        passed=result.returncode == 0, scene_id='S001', tool=tool.name,
                        return_code=result.returncode, stderr_tail=safe_tail(result.stderr.splitlines()),
                        browser_launched=False, ffmpeg_launched=False, video_created=False)
        print(json.dumps(evidence, ensure_ascii=False))
        return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
