# syntax=docker/dockerfile:1
# Only a new storage adapter layer; every approved parent byte is inherited.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3e8611e32860f4ae4f01febda8c4567f069552b111d7628cf0836101bdda9297
USER root
WORKDIR /opt/world-engine-storage-fix
COPY storage.py launch.py STORAGE_FILES.json ./
RUN /usr/bin/python3 -c "import hashlib,json,pathlib; p=pathlib.Path('.'); m=json.loads((p/'STORAGE_FILES.json').read_text()); assert set(m['files'])=={'storage.py','launch.py'}; assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['files'].items())" \
    && install -d -m 0755 /var/lib/world-engine-private \
    && install -d -m 0700 -o 1000 -g 1000 /var/lib/world-engine-private/engine \
    && chmod 0755 /opt/world-engine-storage-fix \
    && chmod 0444 storage.py launch.py STORAGE_FILES.json
LABEL world-engine.storage.version="1" \
      world-engine.storage.parent-digest="sha256:3e8611e32860f4ae4f01febda8c4567f069552b111d7628cf0836101bdda9297"
# Parent diagnostic healthcheck and normal mode remain inherited.
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "/opt/world-engine-storage-fix/launch.py"]
CMD []
