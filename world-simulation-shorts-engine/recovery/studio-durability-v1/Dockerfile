# syntax=docker/dockerfile:1
# Additive wrapper only. The inherited renderer, GPU launcher and private
# filesystem policy are not modified. Never install into the parent Python.
# Official linux/amd64 Python builder, manifest/config SHA verified read-only.
# It supplies wheels only; its Python interpreter is not copied into runtime.
FROM docker.io/library/python@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d AS durability-wheels
COPY extension/requirements.txt /durability-requirements.txt
RUN python -m pip install --no-cache-dir --no-compile --only-binary=:all: \
    --target /durability-deps --requirement /durability-requirements.txt
RUN python - <<'PY'
import hashlib, importlib.metadata, json, pathlib, sys
root = pathlib.Path('/durability-deps')
assert sys.version_info[:2] == (3, 12)
installed = {d.metadata['Name'].lower(): d.version
             for d in importlib.metadata.distributions(path=[str(root)])}
assert installed.get('cryptography') == '50.0.0'
files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(root.rglob('*')) if p.is_file()}
report = {
    'schema': 'WORLD_ENGINE_STUDIO_DURABILITY_DEPENDENCIES_V1',
    'builderImage': 'docker.io/library/python@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d',
    'builderPythonVersion': sys.version.split()[0],
    'pythonABI': '3.12',
    'sourceRequirementsSha256': hashlib.sha256(pathlib.Path('/durability-requirements.txt').read_bytes()).hexdigest(),
    'installedDistributions': installed,
    'files': files,
    'scope': 'NEW_ISOLATED_VENV_ONLY',
}
pathlib.Path('/durability-dependencies.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
PY
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
USER root
RUN test ! -e /opt/world-engine-studio-durability \
    && test ! -L /opt/world-engine-studio-durability \
    && test ! -e /opt/world-engine-studio-durability-venv
COPY extension/ /opt/world-engine-studio-durability/
# The frozen native GDAL Python has no pip. Keep it intact: create a venv
# without ensurepip and copy only ABI-compatible wheels from the builder.
RUN /usr/bin/python3 -m venv --system-site-packages --without-pip /opt/world-engine-studio-durability-venv \
    && /usr/bin/python3 -c 'import sys; assert sys.version_info[:2] == (3,12)'
COPY --from=durability-wheels /durability-deps/ /opt/world-engine-studio-durability-venv/lib/python3.12/site-packages/
COPY --from=durability-wheels /durability-dependencies.json /opt/world-engine-studio-durability-venv/DEPENDENCIES.json
RUN find /opt/world-engine-studio-durability -type f -exec chmod 0444 {} \; \
    && /opt/world-engine-studio-durability-venv/bin/python -B \
       /opt/world-engine-studio-durability/manifest.py --verify
LABEL world-engine.studio-durability.version="1" \
      world-engine.studio-durability.dependency-builder-digest="sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d" \
      world-engine.studio-durability.parent-digest="sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/opt/world-engine-studio-durability-venv/bin/python", "-B", "-c", "import urllib.request; r=urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/healthz',timeout=3); raise SystemExit(0 if r.status==200 else 1)"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/world-engine-studio-durability-venv/bin/python", "-B", "/opt/world-engine-studio-durability/bootstrap.py"]
CMD []
