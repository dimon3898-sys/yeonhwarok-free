# syntax=docker/dockerfile:1
# Five explicitly staged files only. The immutable parent retains every approved
# renderer, fixture, dependency and original source-contract byte unchanged.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:82a4d9086edc2345cd3f00430ff4c354ee3fbaedcef5f0b927a0d5f9c5e16a37
USER root
WORKDIR /opt/world-engine-startup-diagnostics
COPY startup.py records.py service.py healthcheck.py DIAGNOSTIC_FILES.json ./
RUN /usr/bin/python3 -c "import hashlib,json,pathlib; p=pathlib.Path('.'); m=json.loads((p/'DIAGNOSTIC_FILES.json').read_text()); assert set(m['files'])=={'startup.py','records.py','service.py','healthcheck.py'}; assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['files'].items())" \
    && chmod 0755 /opt/world-engine-startup-diagnostics \
    && chmod 0444 startup.py records.py service.py healthcheck.py DIAGNOSTIC_FILES.json
LABEL world-engine.diagnostics.version="1" \
      world-engine.diagnostics.parent-digest="sha256:82a4d9086edc2345cd3f00430ff4c354ee3fbaedcef5f0b927a0d5f9c5e16a37" \
      org.opencontainers.image.revision="2f9158ba2df2a9f58362fb0b17118b8dc19f705a"
ENV WORLD_ENGINE_STARTUP_MODE=normal
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "/opt/world-engine-startup-diagnostics/startup.py"]
CMD []
HEALTHCHECK --interval=5s --timeout=3s --start-period=300s --retries=3 \
  CMD ["/usr/bin/python3", "/opt/world-engine-startup-diagnostics/healthcheck.py"]
