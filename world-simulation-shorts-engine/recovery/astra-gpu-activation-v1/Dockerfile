# syntax=docker/dockerfile:1
# Separate opt-in source-material path. Original startup, health service, renderer
# and GPU admission remain inherited; this image never autostarts a render job.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5dc61e9ce0edfc175c4a38fa0a3f559e660761e604b65bb5edfb6704312610b7
USER root
COPY activation/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/astra-gpu-activation-v1/
COPY upload/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/astra-gpu-integration-v1/
RUN test ! -e /opt/world-engine-astra-activation \
    && ln -s /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/astra-gpu-activation-v1 /opt/world-engine-astra-activation \
    && test ! -e /var/lib/world-engine-private/engine/job-astra-v1 \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/job-astra-v1 \
    && find /opt/world-engine-astra-activation/ -maxdepth 1 -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-astra-activation/prepare_activation.py --verify-extension
LABEL world-engine.astra-activation.version="1" \
      world-engine.astra-activation.parent-digest="sha256:5dc61e9ce0edfc175c4a38fa0a3f559e660761e604b65bb5edfb6704312610b7"
# No ENTRYPOINT, CMD, healthcheck, public port or renderer environment changes.
