"""Local ASGI/mock-HTTPS relay tests. No allocation, renderer, or provider calls."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import unittest

import httpx

APP = Path(__file__).resolve().parents[2]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from deployment.one_url.portal import COOKIE, LIFETIME, MAX_UPLOAD, Portal

PASSWORD = "controlled-owner-password-2026"
KEY = "controlled-session-signing-key-2026-fixture"
ORIGIN = "https://world.example.test"
BACKEND = "https://engine.example.test"
PID = "project_abcdef123456"


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks, self.closed = chunks, False

    async def __aiter__(self):
        for value in self.chunks:
            await asyncio.sleep(0)
            yield value

    async def aclose(self):
        self.closed = True


class BackendFixture:
    def __init__(self):
        self.allocations, self.active, self.peak = 0, 0, 0
        self.requests, self.streams = [], []
        self.fail_ensure = False
        self.redirect = None
        self.next_401 = False

    async def ensure(self):
        self.allocations += 1
        self.active += 1
        self.peak = max(self.active, self.peak)
        try:
            await asyncio.sleep(.01)
            if self.fail_ensure:
                raise RuntimeError("private path/token must never become a response")
            return BACKEND
        finally:
            self.active -= 1

    async def request(self, request):
        self.requests.append(request)
        if request.url.path == "/auth/login":
            assert json.loads(request.content) == {"password": PASSWORD}
            return httpx.Response(200, json={"authenticated": True}, headers={"Set-Cookie": "world_owner_session=private-backend-cookie; Path=/; Secure; HttpOnly; SameSite=Strict"})
        if request.headers.get("Cookie") != "world_owner_session=private-backend-cookie":
            return httpx.Response(401, json={"error": "backend cookie required"})
        if self.next_401:
            self.next_401 = False
            return httpx.Response(401, json={"error": "backend session expired"})
        if self.redirect:
            return httpx.Response(302, headers={"Location": self.redirect})
        status, headers = 200, {"Content-Type": "text/html", "Set-Cookie": "must-not-reach-browser=secret"}
        parts = [b"<html>World Engine</html>"]
        if request.url.path.startswith(("/download/", "/media/")):
            headers.update({"Content-Type": "video/mp4", "Content-Disposition": 'attachment; filename="final.mp4"', "Accept-Ranges": "bytes"})
            if request.headers.get("Range"):
                parts, status = [b"23", b"45"], 206
                headers.update({"Content-Range": "bytes 2-5/10", "Content-Length": "4"})
            else:
                parts = [b"01234", b"56789"]
                headers["Content-Length"] = "10"
        elif request.url.path.startswith("/api/"):
            headers["Content-Type"] = "application/json"
            parts = [json.dumps({"projects": []}).encode()]
        elif request.url.path == "/static/app.js":
            headers["Content-Type"] = "text/javascript"
            parts = [b"console.log('fixture')"]
        stream = Chunks(parts)
        self.streams.append(stream)
        return httpx.Response(status, headers=headers, stream=stream)


class PortalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = BackendFixture()
        self.upstream = httpx.AsyncClient(transport=httpx.MockTransport(self.backend.request))
        self.now = [1_000_000.0]
        self.portal = Portal(origin=ORIGIN, owner_password=PASSWORD, session_key=KEY,
                             backend=self.backend, client=self.upstream, clock=lambda: self.now[0])
        self.front = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.portal), base_url=ORIGIN, follow_redirects=False)

    async def asyncTearDown(self):
        await self.front.aclose()
        await self.upstream.aclose()

    async def login(self):
        response = await self.front.post("/auth/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/")
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=strict", response.headers["set-cookie"])
        self.assertIn(f"Max-Age={LIFETIME}", response.headers["set-cookie"])
        self.assertNotIn(PASSWORD, response.text + response.headers["set-cookie"])
        return response

    async def test_health_and_unauthenticated_routes_never_allocate(self):
        self.assertEqual((await self.front.get("/")).status_code, 303)
        login = await self.front.get("/auth/login")
        self.assertEqual(login.status_code, 200)
        self.assertIn("World Engine", login.text)
        self.assertNotIn("GitHub", login.text)
        self.assertNotIn("파일", login.text)
        self.assertEqual((await self.front.get("/api/health")).json()["ok"], True)
        self.assertEqual((await self.front.get("/auth/session")).json(), {"authenticated": False})
        for path in ("/api/projects", f"/download/{PID}/v001/final/final.mp4", "/static/app.js"):
            self.assertEqual((await self.front.get(path)).status_code, 401)
        self.assertEqual((await self.front.post("/api/projects", json={}, headers={"Origin": ORIGIN})).status_code, 401)
        self.assertEqual(self.backend.allocations, 0)
        self.assertEqual(self.backend.requests, [])

    async def test_owner_login_is_local_and_form_submission_redirects(self):
        await self.login()
        self.assertEqual(self.backend.allocations, 0)
        self.assertTrue((await self.front.get("/auth/session")).json()["authenticated"])
        response = await self.front.post("/auth/login", data={"password": PASSWORD}, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.backend.requests, [])

    async def test_host_and_post_origin_are_checked_before_allocation(self):
        await self.login()
        for origin in (None, "null", "https://attacker.example.test", ORIGIN + "/"):
            headers = {"Origin": origin} if origin is not None else {}
            response = await self.front.post("/api/projects", json={}, headers=headers)
            self.assertEqual(response.status_code, 403)
        hostile = await self.front.get("/api/projects", headers={"Host": "attacker.example.test", "X-Forwarded-Host": "world.example.test", "X-Forwarded-Proto": "https"})
        self.assertEqual(hostile.status_code, 400)
        duplicate = await self.front.post("/api/projects", json={}, headers=[("Origin", ORIGIN), ("Origin", "https://attacker.example.test")])
        self.assertEqual(duplicate.status_code, 403)
        self.assertEqual(self.backend.allocations, 0)

    async def test_authenticated_ui_proxy_strips_browser_credentials_and_proxy_headers(self):
        await self.login()
        response = await self.front.get("/", headers={"Authorization": "Bearer browser-sensitive", "X-Forwarded-Host": "evil.example", "X-Forwarded-Proto": "http", "Forwarded": "host=evil.example"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("World Engine", response.text)
        self.assertEqual(self.backend.allocations, 1)
        self.assertEqual(len(self.backend.requests), 2)
        proxied = self.backend.requests[-1]
        self.assertEqual(proxied.headers["Host"], "engine.example.test")
        self.assertEqual(proxied.headers["Origin"], BACKEND)
        self.assertEqual(proxied.headers["X-Forwarded-Host"], "engine.example.test")
        self.assertEqual(proxied.headers["X-Forwarded-Proto"], "https")
        self.assertNotIn("authorization", proxied.headers)
        self.assertNotIn("forwarded", proxied.headers)
        self.assertNotIn(COOKIE, proxied.headers["cookie"])
        self.assertNotIn("set-cookie", response.headers)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("access-control-allow-origin", response.headers)
        static = await self.front.get("/static/app.js")
        self.assertEqual(static.status_code, 200)
        self.assertEqual(self.backend.allocations, 1)

    async def test_authenticated_api_payload_and_queries_preserved(self):
        await self.login()
        body = {"topic": "서울에서 뉴욕까지", "duration": 20, "quality": "HIGH", "tts": False}
        response = await self.front.post("/api/projects", json=body, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(self.backend.requests[-1].content), body)
        response = await self.front.get(f"/api/projects/{PID}/status?version=v002")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.backend.requests[-1].url.query, b"version=v002")

    async def test_ranged_download_stream_and_head(self):
        await self.login()
        path = f"/download/{PID}/v001/final/final.mp4"
        response = await self.front.get(path, headers={"Range": "bytes=2-5"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"2345")
        self.assertEqual(response.headers["content-range"], "bytes 2-5/10")
        self.assertEqual(response.headers["content-length"], "4")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertTrue(self.backend.streams[-1].closed)
        head = await self.front.head(path)
        self.assertEqual(head.content, b"")
        self.assertEqual(head.headers["content-length"], "10")
        self.assertTrue(self.backend.streams[-1].closed)
        before = len(self.backend.requests)
        bad = await self.front.get(path, headers={"Range": "bytes=1-2,4-5"})
        self.assertEqual(bad.status_code, 416)
        self.assertEqual(len(self.backend.requests), before)

    async def test_concurrent_requests_share_serialized_allocation_and_login(self):
        await self.login()
        results = await asyncio.gather(*(self.front.get("/api/projects") for _ in range(8)))
        self.assertTrue(all(response.status_code == 200 for response in results))
        self.assertEqual(self.backend.allocations, 1)
        self.assertEqual(self.backend.peak, 1)
        self.assertEqual(sum(request.url.path == "/auth/login" for request in self.backend.requests), 1)
        self.now[0] += 31
        await asyncio.gather(*(self.front.get("/api/projects") for _ in range(4)))
        self.assertEqual(self.backend.allocations, 2)
        self.assertEqual(self.backend.peak, 1)

    async def test_private_renderer_arbitrary_paths_queries_and_external_redirects_blocked(self):
        await self.login()
        for path in ("/render.html", "/vendor/three/build/three.js", "/v3-src/renderer.js", "/bridge/renderer_v3.js", "/static/../engine/planner.py", "/static/%2e%2e/engine/planner.py", "/download/project_abcdef123456/v001/%252e%252e/private.txt", "/api/projects?url=https%3A%2F%2Fevil.example", f"/api/projects/{PID}?version=../../etc"):
            response = await self.front.get(path)
            self.assertIn(response.status_code, {400, 404})
        self.assertEqual(self.backend.allocations, 0)
        self.backend.redirect = "https://attacker.example.test/steal"
        response = await self.front.get("/")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("location", response.headers)
        self.backend.redirect = BACKEND + "/index.html"
        response = await self.front.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/index.html")

    async def test_upload_size_is_checked_before_ensure(self):
        await self.login()
        path = "/api/assets?filename=owned.mp4&kind=clip&license=user_owned"
        response = await self.front.post(path, content=b"x", headers={"Origin": ORIGIN, "Content-Type": "video/mp4", "Content-Length": str(MAX_UPLOAD + 1)})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.backend.allocations, 0)
        response = await self.front.post(path, content=b"owned-video", headers={"Origin": ORIGIN, "Content-Type": "video/mp4"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.backend.requests[-1].content, b"owned-video")
        self.assertEqual(self.backend.requests[-1].headers["content-length"], "11")

    async def test_signed_session_tamper_expiry_and_logout(self):
        await self.login()
        token = self.front.cookies.get(COOKIE)
        self.front.cookies.clear()
        altered = token[:-1] + ("0" if token[-1] != "0" else "1")
        response = await self.front.get("/api/projects", headers={"Cookie": f"{COOKIE}={altered}"})
        self.assertEqual(response.status_code, 401)
        self.front.cookies.set(COOKIE, token, domain="world.example.test", path="/")
        self.now[0] += LIFETIME + 1
        self.assertEqual((await self.front.get("/api/projects")).status_code, 401)
        await self.login()
        token = self.front.cookies.get(COOKIE)
        response = await self.front.post("/auth/logout", json={}, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/auth/login")
        response = await self.front.get("/api/projects", headers={"Cookie": f"{COOKIE}={token}"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.backend.allocations, 0)

    async def test_bad_password_rate_limit_and_backend_failure_privacy(self):
        for _ in range(8):
            response = await self.front.post("/auth/login", json={"password": "incorrect"}, headers={"Origin": ORIGIN})
            self.assertEqual(response.status_code, 401)
        response = await self.front.post("/auth/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.backend.allocations, 0)
        self.now[0] += 61
        await self.login()
        self.backend.fail_ensure = True
        response = await self.front.get("/api/projects")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private path", response.text)
        self.assertNotIn(PASSWORD, response.text)

    async def test_safe_read_reauths_backend_without_changing_front_session(self):
        await self.login()
        self.backend.next_401 = True
        response = await self.front.get("/api/projects")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum(request.url.path == "/auth/login" for request in self.backend.requests), 2)
        self.assertNotIn("set-cookie", response.headers)

    async def test_failed_mutation_is_not_replayed_and_clears_backend_auth(self):
        await self.login()
        self.backend.next_401 = True
        response = await self.front.post("/api/projects", json={"topic": "fixture"}, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(sum(request.url.path == "/api/projects" for request in self.backend.requests), 1)
        self.assertIsNone(self.portal._backend_cookie)
        response = await self.front.get("/api/projects")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum(request.url.path == "/auth/login" for request in self.backend.requests), 2)

    async def test_durable_revocation_rejects_logout_replay_after_front_restart(self):
        class Store:
            def __init__(self):
                self.values = {}
                self.fail = False

            async def contains(self, sid):
                return sid in self.values

            async def revoke(self, sid, expires):
                if self.fail:
                    raise RuntimeError("private durable store path")
                self.values[sid] = expires

        store = Store()
        self.portal.revocation_store = store
        await self.login()
        token = self.front.cookies.get(COOKIE)
        store.fail = True
        failed = await self.front.post("/auth/logout", json={}, headers={"Origin": ORIGIN})
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn("set-cookie", failed.headers)
        self.assertNotIn("private", failed.text)
        store.fail = False
        self.assertEqual((await self.front.post("/auth/logout", json={}, headers={"Origin": ORIGIN})).status_code, 303)
        self.assertEqual(len(store.values), 1)
        restarted = Portal(origin=ORIGIN, owner_password=PASSWORD, session_key=KEY,
                           backend=self.backend, client=self.upstream, clock=lambda: self.now[0], revocation_store=store)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url=ORIGIN) as front:
            replay = {"Cookie": f"{COOKIE}={token}"}
            self.assertEqual((await front.get("/api/projects", headers=replay)).status_code, 401)
            self.assertEqual((await front.get("/auth/session", headers=replay)).json(), {"authenticated": False})
        self.assertEqual(self.backend.allocations, 0)

    async def test_backend_login_redirect_on_safe_ui_read_reauthenticates_once(self):
        await self.login()
        original = self.backend.request
        calls = [0]

        async def expired_root(request):
            if request.url.path == "/" and calls[0] == 0:
                calls[0] += 1
                return httpx.Response(303, headers={"Location": "/auth/login"})
            return await original(request)

        self.upstream._transport = httpx.MockTransport(expired_root)
        response = await self.front.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("World Engine", response.text)
        self.assertEqual(sum(request.url.path == "/auth/login" for request in self.backend.requests), 2)

    async def test_disconnect_before_first_chunk_closes_upstream(self):
        token = self.portal._new_token()
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                 "http_version": "1.1", "scheme": "https", "method": "GET", "path": "/",
                 "raw_path": b"/", "query_string": b"", "server": ("world.example.test", 443),
                 "client": ("127.0.0.1", 1234),
                 "headers": [(b"host", b"world.example.test"), (b"cookie", f"{COOKIE}={token}".encode())]}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def disconnected_send(_message):
            raise OSError("downstream disconnected")

        from starlette.requests import ClientDisconnect
        with self.assertRaises(ClientDisconnect):
            await self.portal(scope, receive, disconnected_send)
        self.assertTrue(self.backend.streams[-1].closed)

    def test_invalid_configuration_and_local_test_origin(self):
        for bad_origin in ("http://public.example.test", "https://world.example.test/path", "https://name:password@world.example.test", "https://world.example.test?bad"):
            with self.assertRaises(ValueError):
                Portal(origin=bad_origin, owner_password=PASSWORD, session_key=KEY, backend=self.backend, client=self.upstream)
        with self.assertRaises(ValueError):
            Portal(origin=ORIGIN, owner_password="short", session_key=KEY, backend=self.backend, client=self.upstream)
        with self.assertRaises(ValueError):
            Portal(origin=ORIGIN, owner_password=PASSWORD, session_key="short", backend=self.backend, client=self.upstream)
        local = Portal(origin="http://127.0.0.1:7860", owner_password=PASSWORD, session_key=KEY, backend=self.backend, client=self.upstream)
        self.assertEqual(local.origin, "http://127.0.0.1:7860")
        with self.assertRaises(ValueError):
            Portal(origin=ORIGIN, owner_password=PASSWORD, session_key=KEY, backend=self.backend, client=self.upstream, allow_local_backend=True)

    async def test_local_http_backend_requires_explicit_loopback_front_configuration(self):
        class LocalBackend(BackendFixture):
            def ensure(self):
                self.allocations += 1
                return "http://127.0.0.1:8096"

        backend = LocalBackend()
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(backend.request))
        try:
            portal = Portal(origin="https://localhost:7860", owner_password=PASSWORD, session_key=KEY, backend=backend, client=upstream, allow_local_backend=True)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal), base_url="https://localhost:7860") as front:
                self.assertEqual((await front.post("/auth/login", json={"password": PASSWORD}, headers={"Origin": "https://localhost:7860"})).status_code, 303)
                response = await front.get("/api/projects")
                self.assertEqual(response.status_code, 200)
                request = backend.requests[-1]
                self.assertEqual(request.headers["Host"], "127.0.0.1:8096")
                self.assertEqual(request.headers["Origin"], "http://127.0.0.1:8096")
                self.assertNotIn("x-forwarded-host", request.headers)
                self.assertNotIn("x-forwarded-proto", request.headers)
            rejected = Portal(origin=ORIGIN, owner_password=PASSWORD, session_key=KEY, backend=backend, client=upstream)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=rejected), base_url=ORIGIN) as front:
                await front.post("/auth/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
                self.assertEqual((await front.get("/api/projects")).status_code, 503)
        finally:
            await upstream.aclose()


if __name__ == "__main__":
    unittest.main()
