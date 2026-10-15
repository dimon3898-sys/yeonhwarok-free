# syntax=docker/dockerfile:1
# The approved RTX image is inherited. Only two startup diagnostic modules and
# the read-only existing-result helper are new; no renderer or dependency build.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:119873aa8515622c3508e934247bd4a18e85d080e3f33696e66acc1bae874825
USER root
COPY startup.py DIAGNOSTIC_FILES.json /opt/world-engine-startup-diagnostics/
COPY launch.py STORAGE_FILES.json /opt/world-engine-storage-fix/
COPY recover_existing.py RESULT_FILES.json /opt/world-engine-diagnostic-result/
RUN /usr/bin/python3 -c "import hashlib,json,pathlib; roots=[pathlib.Path('/opt/world-engine-startup-diagnostics'),pathlib.Path('/opt/world-engine-storage-fix')]; names=['DIAGNOSTIC_FILES.json','STORAGE_FILES.json']; assert all(all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in json.loads((p/m).read_text())['files'].items()) for p,m in zip(roots,names)); p=pathlib.Path('/opt/world-engine-diagnostic-result'); m=json.loads((p/'RESULT_FILES.json').read_text()); assert hashlib.sha256((p/'recover_existing.py').read_bytes()).hexdigest()==m['helperSha256']" \
    && chmod 0755 /opt/world-engine-diagnostic-result \
    && chmod 0444 /opt/world-engine-startup-diagnostics/startup.py /opt/world-engine-startup-diagnostics/DIAGNOSTIC_FILES.json \
      /opt/world-engine-storage-fix/launch.py /opt/world-engine-storage-fix/STORAGE_FILES.json \
      /opt/world-engine-diagnostic-result/recover_existing.py /opt/world-engine-diagnostic-result/RESULT_FILES.json
LABEL world-engine.result.version="1" \
      world-engine.result.parent-digest="sha256:119873aa8515622c3508e934247bd4a18e85d080e3f33696e66acc1bae874825"
# ENTRYPOINT, default normal mode, UID bootstrap and healthcheck are inherited.
