#!/usr/bin/env bash
# Dependency setup for a clean development checkout; never renders or tunes V4.
set -euo pipefail
v4_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
v4_cache="${V4_NPM_CACHE:-$v4_repo/.git/v4-npm-cache}"
git -C "$v4_repo" lfs version
git -C "$v4_repo" lfs install --local
git -C "$v4_repo" lfs pull --include="world-simulation-shorts-engine/library/flat/terrain/NE1_HR_LC_SR_W_DR.tif,world-simulation-shorts-engine/web/dem/glo30/height.f32" --exclude=""
node -e 'if(process.version!=="v24.19.0") throw Error("V4 requires recorded Node v24.19.0; install that version before setup")'
chromium --version | rg -q 'Chromium 154\.0\.8037\.57'
/usr/bin/python3 -B - <<'PY'
import sys
from osgeo import gdal
import numpy, PIL
required = {'python': '3.13.5', 'gdal': '3.10.3', 'numpy': '2.2.4', 'pillow': '11.1.0'}
actual = {'python': '.'.join(map(str, sys.version_info[:3])), 'gdal': gdal.VersionInfo('RELEASE_NAME'), 'numpy': numpy.__version__, 'pillow': PIL.__version__}
if actual != required:
    raise SystemExit(f'Recorded CPU raster dependencies required: {required}; found {actual}')
print('Recorded browser/raster dependency versions: PASS')
PY
npm --prefix "$v4_repo/cinematic-world-map" ci --ignore-scripts --no-audit --no-fund --cache "$v4_cache"
node --input-type=module - "$v4_repo" <<'JS'
import {readFileSync} from 'node:fs';
const packageRoot = process.argv[2] + '/cinematic-world-map/node_modules/';
for (const [name, version] of [['three','0.170.0'],['playwright','1.62.1'],['playwright-core','1.62.1']]) {
  if (JSON.parse(readFileSync(packageRoot+name+'/package.json','utf8')).version !== version) throw Error(name+' version mismatch');
}
console.log('Locked npm dependency versions: PASS');
JS
