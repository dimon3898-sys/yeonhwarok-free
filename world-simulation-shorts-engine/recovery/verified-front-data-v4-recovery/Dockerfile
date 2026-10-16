# syntax=docker/dockerfile:1
# A new opt-in namespace; the immutable parent runtime and startup are inherited.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb
USER root
RUN test ! -e /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery \
    && test ! -L /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery \
    && test ! -e /opt/world-engine-front-v4 && test ! -L /opt/world-engine-front-v4 \
    && test ! -e /var/lib/world-engine-private/engine/verified-front-v4
COPY front/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/
RUN ln -s /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery /opt/world-engine-front-v4 \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/verified-front-v4 \
    && find /opt/world-engine-front-v4/ -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-front-v4/source_manifest_recovery.py --verify-extension
LABEL world-engine.front-v4.version="4" \
      world-engine.front-v4.parent-digest="sha256:10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb"
# ENTRYPOINT, CMD, HEALTHCHECK, ports, all 272 parent files and renderer are unchanged.
