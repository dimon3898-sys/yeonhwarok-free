# No renderer, GPU or dependency changes. Inherit exactly the published v005.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:aca64542277a971c6ce1c616308d8a263f7aca8ff94874971e298c88a4e38567
COPY observer.py server_diag.py test_observer.py test_server_diag.py /opt/world-engine/proxy-diag/
USER engine
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import json,urllib.request; o=urllib.request.build_opener(urllib.request.ProxyHandler({})); r=o.open('http://127.0.0.1:8000/healthz',timeout=3); v=json.load(r); assert v['diagnostic_mode']=='PROXY_ONLY' and v['engine_ready'] is False"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "python", "/opt/world-engine/proxy-diag/server_diag.py"]
CMD []
