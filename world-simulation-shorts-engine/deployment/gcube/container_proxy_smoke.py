"""Fresh-image HTTP proxy/owner smoke plus >=60s lifetime; no video requests.

Run on the CI host against its own explicitly CPU-comparison container. Its
owner code is read from the CI-private env file and never printed or stored in
the returned proof. NVIDIA admission is tested separately and never faked here.
"""
import http.client
import json
from pathlib import Path
import subprocess
import sys
import time


# This test-only TCP relay is started inside the smoke container, just as an
# Istio sidecar forwards to the loopback listener. It preserves all HTTP bytes;
# no application peer/origin checks are disabled or patched for this test.
LOOPBACK_RELAY = '''
import selectors, socket, socketserver
class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=5) as upstream:
                upstream.settimeout(None)
                with selectors.DefaultSelector() as selector:
                    selector.register(self.request, selectors.EVENT_READ, upstream)
                    selector.register(upstream, selectors.EVENT_READ, self.request)
                    while True:
                        events = selector.select(10)
                        if not events: return
                        for key, _ in events:
                            data = key.fileobj.recv(65536)
                            if not data: return
                            key.data.sendall(data)
        except OSError:
            return
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
with Server(("0.0.0.0", 18011), Relay) as server:
    server.serve_forever()
'''


def main():
    env_file, name, endpoint_port = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    owner = next(line.partition("=")[2] for line in env_file.read_text().splitlines()
                 if line.startswith("WORLD_ENGINE_OWNER_CODE="))
    service = "3f2de722.service.gcube.ai:24999"
    origin = "https://" + service
    base = {"Host": "localhost:8000", "X-Forwarded-Host": service,
            "X-Forwarded-Proto": "https", "X-Forwarded-Port": "24999",
            "X-Forwarded-For": "203.0.113.8, 10.42.0.2, 127.0.0.6",
            "X-Envoy-External-Address": "203.0.113.8",
            "Forwarded": 'for=203.0.113.8;proto=https;host="' + service + '", for=10.42.0.2;proto=http'}
    cookie = None
    subprocess.run(["docker", "exec", "--detach", name, "python", "-c", LOOPBACK_RELAY], check=True)

    def call(method, path, data=None, headers=None):
        values = dict(base)
        if cookie: values["Cookie"] = cookie
        if method == "POST": values["Origin"] = origin
        values.update(headers or {})
        payload = json.dumps(data).encode() if data is not None else None
        if payload is not None: values["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", endpoint_port, timeout=5)
        connection.request(method, path, body=payload, headers=values)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        assert "Access-Control-Allow-Origin" not in result[1]
        assert owner.encode() not in result[2]
        return result

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            status, _, body = call("GET", "/api/health")
            record = json.loads(body)
            if status == 200 and record.get("engine_ready") is True: break
        except (OSError, http.client.HTTPException, ValueError):
            pass
        time.sleep(.5)
    else:
        raise AssertionError("PROXY_CONTAINER_NOT_READY")
    ready_at = time.monotonic()
    assert record["gpu"]["render_mode"] == "cpu" and record["gpu"]["gpu_rendering_verified"] is False
    for path in ("/api/projects", "/api/gcube/proxy", "/gcube/gpu.json"):
        assert call("GET", path)[0] == 401
    for password in (None, "wrong"):
        assert call("POST", "/auth/login", {"password": password})[0] == 401
    assert call("GET", "/api/health")[0] == 200
    status, headers, body = call("POST", "/auth/login", {"password": owner})
    assert status == 200 and json.loads(body)["authenticated"] is True
    assert all(flag in headers["Set-Cookie"] for flag in ("Secure", "HttpOnly", "SameSite=Strict"))
    cookie = headers["Set-Cookie"].split(";", 1)[0]
    for xff in ("203.0.113.8", "203.0.113.8, 10.42.0.2", "203.0.113.8, 10.42.0.2, 127.0.0.6"):
        status, _, body = call("GET", "/api/gcube/proxy", headers={"X-Forwarded-For": xff})
        record = json.loads(body)
        assert status == 200 and record["xff_entry_count"] == len(xff.split(","))
        assert record["forwarded_host"] == service and record["effective_origin"] == origin
        assert b"203.0.113.8" not in body and cookie.encode() not in body
    assert call("GET", "/auth/session")[0] == 200
    assert call("GET", "/api/projects")[0] == 200
    status, _, body = call("GET", "/gcube/gpu.json")
    record = json.loads(body)
    assert status == 200 and record["gpu_rendering_verified"] is False
    assert record["diagnostics"]["webgl"]["software_renderer"] is True
    attacks = ({"Origin": "https://attacker.example"}, {"X-Forwarded-Host": "attacker.example"},
               {"X-Forwarded-For": "203.0.113.8, malformed"}, {"X-Forwarded-Port": "31042"},
               {"Forwarded": "for=203.0.113.8;proto=http"}, {"Host": "attacker.example"})
    routes = ("/auth/login", "/auth/logout", "/api/projects", "/api/assets",
              "/api/projects/project_abcdef123456/approve", "/api/projects/project_abcdef123456/render",
              "/api/projects/project_abcdef123456/revise", "/api/projects/project_abcdef123456/resume")
    for path in routes:
        for attack in attacks:
            assert call("POST", path, {}, headers=attack)[0] in (400, 403)
    assert call("GET", "/gcube/gpu")[0] == 200
    subprocess.run(["docker", "exec", name, "python", "-c",
        "from pathlib import Path; assert any(r.split()[1]=='00000000:1F40' and r.split()[3]=='0A' for r in Path('/proc/net/tcp').read_text().splitlines()[1:])"], check=True)
    while time.monotonic() - ready_at < 61:
        running = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", name],
                                  capture_output=True, text=True, check=True)
        assert running.stdout.strip() == "true"
        assert call("GET", "/auth/session")[0] == 200
        time.sleep(min(2, max(.01, 61 - (time.monotonic() - ready_at))))
    print(json.dumps({"proxy_owner_http": "PASS", "blocked_mutation_requests": len(routes) * len(attacks),
                      "server_alive_seconds_after_ready": round(time.monotonic() - ready_at, 3),
                      "bound": "0.0.0.0:8000", "render_requested": False,
                      "test_runtime": "explicit CPU comparison; not NVIDIA GPU validation"}))


if __name__ == "__main__":
    main()
