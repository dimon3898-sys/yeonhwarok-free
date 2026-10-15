# syntax=docker/dockerfile:1
# Additive opt-in quality lane; inherited startup never automatically renders.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8aba498e295b45a9cbfa29eeacd6f7779ff3d2ce4482c92215176be1540ff71a
USER root
COPY quality/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/visual-quality-upgrade-v1/
RUN test ! -e /opt/world-engine-visual-quality \
    && ln -s /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/visual-quality-upgrade-v1 /opt/world-engine-visual-quality \
    && test ! -e /var/lib/world-engine-private/engine/job-quality-v1 \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/job-quality-v1 \
    && find /opt/world-engine-visual-quality/ -maxdepth 1 -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-visual-quality/prepare_quality.py --verify-extension
LABEL world-engine.visual-quality.version="1" \
      world-engine.visual-quality.parent-digest="sha256:8aba498e295b45a9cbfa29eeacd6f7779ff3d2ce4482c92215176be1540ff71a"
# No ENTRYPOINT, CMD, HEALTHCHECK, port or renderer environment changes.
