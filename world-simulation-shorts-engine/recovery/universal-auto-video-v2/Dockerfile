# syntax=docker/dockerfile:1
# Additive long-video orchestration over the exact frozen Reference Visual V2.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5
USER root
COPY universal/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-auto-video-v2/
RUN /usr/bin/python3 -B /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-auto-video-v2/universal_files.py --check-supplemental-absent
COPY supplemental/ /opt/rtx-package/repo/
RUN test ! -e /opt/world-engine-universal-v2 \
    && ln -s /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-auto-video-v2 /opt/world-engine-universal-v2 \
    && test ! -e /var/lib/world-engine-private/engine/universal-video-v2 \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/universal-video-v2 \
    && find /opt/world-engine-universal-v2/ -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-universal-v2/universal_files.py --verify-extension
LABEL world-engine.universal-v2.version="2" \
      world-engine.universal-v2.parent-digest="sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5"
# Existing ENTRYPOINT, CMD, HEALTHCHECK, camera/renderer and ports are inherited.
