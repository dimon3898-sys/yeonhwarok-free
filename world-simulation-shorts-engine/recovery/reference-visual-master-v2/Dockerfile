# syntax=docker/dockerfile:1
# Additive opt-in scene lane. No old startup service or parent file is changed.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae
USER root
COPY reference/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/reference-visual-master-v2/
RUN test ! -e /opt/world-engine-reference-v2 \
    && ln -s /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/reference-visual-master-v2 /opt/world-engine-reference-v2 \
    && test ! -e /var/lib/world-engine-private/engine/job-reference-v2-v1 \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/job-reference-v2-v1 \
    && find /opt/world-engine-reference-v2/ -maxdepth 1 -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-reference-v2/prepare_ref2.py --verify-extension
LABEL world-engine.reference-v2.version="2" \
      world-engine.reference-v2.parent-digest="sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae"
# No ENTRYPOINT, CMD, HEALTHCHECK, public port or production environment override.
