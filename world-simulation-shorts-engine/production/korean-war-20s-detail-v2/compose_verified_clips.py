"""Pass two completed ten-second files to the existing frame-verifying composer.

No renderer, no automatic retry, and no change to either original input file.
The caller must match the actual job/capture receipts to PART_01 and PART_02.
"""
import argparse
import importlib.util
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--part-1', required=True, type=Path)
parser.add_argument('--part-2', required=True, type=Path)
parser.add_argument('--destination', required=True, type=Path)
a = parser.parse_args()
here = Path(__file__).resolve().parent
source = here.parents[1] / 'recovery/universal-auto-video-v2/compose.py'
spec = importlib.util.spec_from_file_location('world_engine_existing_compose', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
plan = json.loads((here/'evidence/local/COMPOSE_PLAN.json').read_bytes())
assert not a.destination.exists(), 'NEW_DESTINATION_REQUIRED'
segments = []
for number, file in enumerate((a.part_1, a.part_2), 1):
    assert file.is_absolute() and file.is_file() and not file.is_symlink(), 'EXISTING_ABSOLUTE_REGULAR_MP4_REQUIRED'
    segments.append({'sceneId':f'clip-{number:02d}', 'startFrame':(number-1)*300,
                     'endFrame':number*300, 'path':str(file), 'sha256':module.digest_file(file)})
result = module.compose_segments(plan, segments, a.destination)
print(json.dumps(result, ensure_ascii=False, indent=2))
