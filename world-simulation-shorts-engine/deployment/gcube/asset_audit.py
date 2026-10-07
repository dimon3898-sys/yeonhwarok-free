"""Read-only deployed dependency manifest, excluding user data and secrets."""
import hashlib
import json
import os
from pathlib import Path
from engine.assets import APP_ROOT, V3_ROOT, asset_registry


def audit_assets():
    paths = {Path(row['path']): 'registered_asset' for row in asset_registry()}
    for name in ('SOURCES.json',):
        source = APP_ROOT / 'assets/flat' / name
        rows = json.loads(source.read_text())
        for row in rows if isinstance(rows, list) else rows['assets']:
            paths[APP_ROOT / row['file']] = 'flat_registered_asset'
    # Imported modules include embedded shaders and procedural cargo-ship,
    # vehicle, marker, LUT/film curve and route materials, not external models.
    for folder in (APP_ROOT/'web', V3_ROOT/'src'):
        for file in folder.glob('*.js'):
            paths[file] = 'renderer_shader_or_model_source'
    for file in (APP_ROOT/'web').glob('render*.html'):
        paths[file] = 'renderer_entry_page'
    for file in (V3_ROOT/'node_modules/three/build/three.module.js',
                 V3_ROOT/'node_modules/playwright/package.json',
                 APP_ROOT/'engine/rhythm_sound.py', APP_ROOT/'engine/sfx_library.py',
                 APP_ROOT/'engine/audio.py', APP_ROOT/'engine/audio_stability.py',
                 APP_ROOT/'tools/scene_frame_contract.mjs', APP_ROOT/'tools/render_production_stable_scene.mjs'):
        paths[file] = 'runtime_dependency'
    records = []
    for file, category in sorted(paths.items()):
        present = file.is_file()
        readable = present and os.access(file, os.R_OK)
        size = file.stat().st_size if present else 0
        records.append(dict(path=str(file.relative_to(APP_ROOT.parent)), referenced=True,
                            category=category, exists=present, readable=readable, size=size,
                            non_zero=size>0,
                            sha256=hashlib.sha256(file.read_bytes()).hexdigest() if readable and size else None))
    return dict(passed=all(row['readable'] and row['non_zero'] for row in records), assets=records,
                generated_assets=dict(ship='procedural makeShip',aircraft='procedural createAircraftV3',
                                      route='procedural TubeGeometry/shader',LUT='embedded film curve',
                                      SFX='original procedural catalog; variants generated on demand'),
                scope='Actual filesystem read/nonzero/source SHA; no GPU pixel proof')


if __name__ == '__main__':
    result = audit_assets()
    print(json.dumps(result))
    raise SystemExit(0 if result['passed'] else 1)
