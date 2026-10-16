# syntax=docker/dockerfile:1
# The frozen parent repository and all 373 strict files remain byte-identical.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:4f2daf520eed2331a1b6ea0d3644e6f7d65854e7d4f3368d43af5f96d1ff6ab4
USER root
RUN test ! -e /opt/world-engine-production-studio && test ! -L /opt/world-engine-production-studio \
    && test ! -e /var/lib/world-engine-private/engine/production-studio-mvp-v1
COPY studio/ /opt/world-engine-production-studio/
RUN find /opt/world-engine-production-studio -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-production-studio/studio_manifest.py --verify \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine/production-studio-mvp-v1
LABEL world-engine.studio.version="1" \
      world-engine.studio.parent-digest="sha256:4f2daf520eed2331a1b6ea0d3644e6f7d65854e7d4f3368d43af5f96d1ff6ab4"
# New wrapper starts the unchanged original launch.py child (health/GPU port8000).
# Inherited HEALTHCHECK is unchanged. gCube must explicitly expose port8080.
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "-B", "/opt/world-engine-production-studio/bootstrap.py"]
CMD []
