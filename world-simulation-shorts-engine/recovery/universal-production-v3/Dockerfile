# syntax=docker/dockerfile:1
# Add only the new production extension over the verified immutable V2 image.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5f17537fa8e5387de39ed8999e4c8d7ce2fe8a3593a71a5a3c1ae033f22dd014
USER root
RUN test ! -e /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-production-v3 \
    && test ! -L /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-production-v3 \
    && test ! -e /opt/world-engine-production-v3 \
    && test ! -L /opt/world-engine-production-v3 \
    && test ! -e /var/lib/world-engine-private/engine/universal-production-v3
COPY production/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-production-v3/
RUN ln -s /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-production-v3 /opt/world-engine-production-v3 \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/universal-production-v3 \
    && find /opt/world-engine-production-v3/ -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-production-v3/source_manifest.py --verify-extension
LABEL world-engine.production-v3.version="3" \
      world-engine.production-v3.parent-digest="sha256:5f17537fa8e5387de39ed8999e4c8d7ce2fe8a3593a71a5a3c1ae033f22dd014"
# The approved ENTRYPOINT, CMD, HEALTHCHECK, ports and existing runtime stay inherited.
