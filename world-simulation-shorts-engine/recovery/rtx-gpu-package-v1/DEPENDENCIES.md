# Dependency contract

The new image is not built. Its digest is null. Actual image ABI/browser checks
remain separate from checks in this executor.

The official GDAL 3.10.3 Ubuntu 24.04 linux/amd64 base and official Node 24.19.0
builder are fixed by immutable digests in Dockerfile. The native base supplies
coherent /usr/bin/python3, GDAL bindings, NumPy and Pillow. Its verified stored
package metadata records Python 3.12.3, NumPy 1.26.4 and Pillow 10.2.0; native
imports still require runtime verification. No old-image Python or Debian
browser/native libraries are copied.

The unchanged cinematic package lock installs Playwright 1.62.1 with dev
dependencies included, browser download disabled and install scripts disabled.
MCR manifest access returned proxy tunnel HTTP403. The selected fallback is
official Google Chrome 155.0.8059.79, from an exact DEB URL with SHA-256
b7726070ca707965e9a17b38e4f15ba283bf6f65c339626c092862af7b19badc.
The downloaded DEB's exact bytes/SHA and Version/Architecture control fields
were verified. Browser execution and its final-image shared libraries remain
unverified. It is exposed as /usr/bin/chromium for the existing argument wrapper. The
preserved SwiftShader runner's original Chromium154 contract is unchanged.

native-packages.lock pins Ubuntu-native netCDF4.9.2, HDF5 and browser/graphics
runtime roots and FFmpeg6.1.1 from signature-verified Noble metadata. The trusted Ubuntu keyring
came from a verified official GDAL base layer. Package index lengths and SHA-256
hashes were checked against signed releases. APT signature verification remains
enabled; missing retired pins fail. Transitive APT packages are resolved by APT
and must be recorded during an actual build audit.

verify_dependencies.py checks explicit versions, Python ABI and native module
origins, GDAL context APIs, actual libnetcdf memory-read symbols, FFmpeg/ffprobe
and the CPU libx264 encoder. It executes
unchanged ASTRA parsers on small synthetic Float32 PixelIsPoint TIFF, signed CF
NetCDF/NetCDF4, PNG and neutral NPZ fixtures. Missing checks fail. It never opens
a browser page, accesses a GPU or downloads source datasets.

Focused checks in this executor: 27 tests passed, including five real native
CPU probes. This executor uses Python3.13.5/GDAL3.10.3, not the intended Ubuntu
image. Docker pull failed during vfs layer registration because its disk was
full; no dependency container ran. Verified sysroot imports establish the
base's Python3.12.3/NumPy1.26.4/Pillow10.2.0/GDAL3.10.3 combination and context
APIs. The pinned Ubuntu netCDF4.9.2/HDF5 library closure also passed an unchanged
ASTRA NETCDF4 signed Int16 CF parser probe: raw values, axes, nodata mask and SHA
were verified, with all loaded shared libraries inside the verified sysroot.
Final-image browser/encoder and complete dependency-contract checks remain
pending.
See evidence/DEPENDENCY_SOURCES.json for source receipts.

Build only from a freshly verified staged context. In this cloud environment,
pass the combined public CA bundle through the BuildKit proxy_ca secret.
Session credentials and CA files must not become image layers. No image build,
push or GPU deployment has been performed.

Docker normalizes only newly copied /opt/rtx-package files to readable/traversable
permissions. The original private working-file modes and bytes are unchanged;
source copies stay root-owned and engine-readable. Runtime diagnostics retain
their separate private permissions.
