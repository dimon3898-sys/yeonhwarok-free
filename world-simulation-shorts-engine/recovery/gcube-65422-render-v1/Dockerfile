# syntax=docker/dockerfile:1
# Bounded report parsing only; renderer, startup, entrypoint and health inherit.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:e7245bdd73c99eff806effdfd1f5ba6765fcffdc2d64fbdb52c360e79148dff3
USER root
COPY storage.py STORAGE_FILES.json /opt/world-engine-storage-fix/
COPY RESULT_FILES.json /opt/world-engine-diagnostic-result/
COPY RENDER_FILES.json /opt/world-engine-65422-render/
RUN /usr/bin/python3 -c "import hashlib,json,pathlib; p=pathlib.Path('/opt/world-engine-storage-fix'); m=json.loads((p/'STORAGE_FILES.json').read_text()); assert set(m['files'])=={'storage.py','launch.py'}; assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['files'].items())" \
    && chmod 0444 /opt/world-engine-storage-fix/storage.py /opt/world-engine-storage-fix/STORAGE_FILES.json /opt/world-engine-diagnostic-result/RESULT_FILES.json /opt/world-engine-65422-render/RENDER_FILES.json \
    && chmod 0755 /opt/world-engine-65422-render
LABEL world-engine.render-export.version="1" \
      world-engine.render-export.parent-digest="sha256:e7245bdd73c99eff806effdfd1f5ba6765fcffdc2d64fbdb52c360e79148dff3"
