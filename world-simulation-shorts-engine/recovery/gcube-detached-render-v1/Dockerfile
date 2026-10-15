# syntax=docker/dockerfile:1
# Explicit CLI only. All approved startup, rendering, GPU admission and health
# behavior is inherited; building this layer never starts a render job.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1a0a953d36ed0269a0c99267dd2d2d9e92ac6c50ffb7808e78bfbde24e7e2842
USER root
COPY job_manager.py job_store.py inspect_existing.py verify_artifacts.py JOB_FILES.json /opt/world-engine-detached-render/
RUN /usr/bin/python3 -c "import hashlib,json,pathlib; p=pathlib.Path('/opt/world-engine-detached-render'); m=json.loads((p/'JOB_FILES.json').read_text()); assert set(m['files'])=={'job_manager.py','job_store.py','inspect_existing.py','verify_artifacts.py'}; assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['files'].items())" \
    && test ! -e /var/lib/world-engine-private/engine/job-control-v1 \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/job-control-v1 \
    && chmod 0755 /opt/world-engine-detached-render \
    && chmod 0444 /opt/world-engine-detached-render/*.py /opt/world-engine-detached-render/JOB_FILES.json
LABEL world-engine.detached-render.version="1" \
      world-engine.detached-render.parent-digest="sha256:1a0a953d36ed0269a0c99267dd2d2d9e92ac6c50ffb7808e78bfbde24e7e2842"
# No ENTRYPOINT, CMD, healthcheck, public port or renderer environment change.
