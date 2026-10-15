"""Registry protocol fixtures only: no real credentials, network, Docker or push."""

import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
import unittest
from unittest.mock import patch
from email.message import Message

import registry_guard as rg


TAG = "rtx4080s-2f9158b-123456789-1"
ENV = {"GITHUB_ACTOR": "github-actions[bot]", "GH_TOKEN": "fixture-secret-never-log"}
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
OCI_INDEX = "application/vnd.oci.image.index.v1+json"
OCI_CONFIG = "application/vnd.oci.image.config.v1+json"


def raw(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def response(document, status=200, headers=None):
    return rg.Response(status, headers or {}, raw(document))


def token_response(token="opaque-fixture-token"):
    return response({"token": token})


def jwt(actions=("pull", "push"), repository=rg.REPOSITORY):
    payload = raw({"access": [{"type": "repository", "name": repository,
                                "actions": list(actions)}]})
    return "e30." + base64.urlsafe_b64encode(payload).decode().rstrip("=") + ".c2ln"


def manifest_response(body, content_type=OCI_MANIFEST):
    return rg.Response(200, {"Content-Type": content_type,
                             "Docker-Content-Digest": digest(body)}, body)


def image_fixture(config_changes=None, manifest_changes=None):
    config = {"architecture": "amd64", "os": "linux",
              "config": {"Env": ["SECRET=fixture-config-secret"]}}
    config.update(config_changes or {})
    config_body = raw(config)
    manifest = {"schemaVersion": 2, "mediaType": OCI_MANIFEST,
                "config": {"mediaType": OCI_CONFIG, "digest": digest(config_body),
                           "size": len(config_body)}, "layers": []}
    manifest.update(manifest_changes or {})
    body = raw(manifest)
    return body, config_body


class QueueTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, limit):
        self.calls.append((url, dict(headers), limit))
        if not self.responses:
            raise AssertionError("unplanned fixture request")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class RegistryGuardTests(unittest.TestCase):
    def guard(self, *responses, environ=None):
        transport = QueueTransport(*responses)
        return rg.RegistryGuard(transport=transport, environ=ENV if environ is None else environ), transport

    def assert_block(self, reason, operation):
        with self.assertRaises(rg.GuardError) as caught:
            operation()
        self.assertEqual(reason, str(caught.exception))

    def test_safe_tag_and_canonical_digest(self):
        self.assertEqual(TAG, rg.validate_tag(TAG))
        self.assertEqual("sha256:" + "a" * 64, rg.validate_digest("sha256:" + "a" * 64))

    def test_tag_boundaries_are_ascii_and_fixed_prefix(self):
        for value in (TAG + "\n", TAG + "/x", "other-2f9158b-1-1", "rtx4080s-2f9158b-0-1",
                      "rtx4080s-2f9158b-1-01", "rtx4080s-2f9158b-١-1", ":" + TAG,
                      "rtx4080s-2f9158b-" + "1" * 128 + "-1", None):
            with self.subTest(value=value):
                self.assert_block("INVALID_TAG", lambda: rg.validate_tag(value))

    def test_digest_boundaries(self):
        for value in ("sha256:" + "a" * 63, "sha256:" + "A" * 64,
                      "sha256:" + "a" * 64 + "\n", "sha512:" + "a" * 64,
                      "sha256:" + "g" * 64, "repo@sha256:" + "a" * 64, None):
            with self.subTest(value=value):
                self.assert_block("INVALID_DIGEST", lambda: rg.validate_digest(value))

    def test_invalid_inputs_do_not_authenticate(self):
        guard, transport = self.guard()
        self.assert_block("INVALID_TAG", lambda: guard.check_tag("bad"))
        self.assert_block("INVALID_DIGEST", lambda: guard.inspect_digest("bad"))
        self.assertEqual([], transport.calls)

    def test_credentials_missing_or_header_unsafe(self):
        cases = [({}, "GITHUB_ACTOR_REQUIRED_OR_INVALID"),
                 ({"GITHUB_ACTOR": "a:b", "GH_TOKEN": "fixture"}, "GITHUB_ACTOR_REQUIRED_OR_INVALID"),
                 ({"GITHUB_ACTOR": "actor\n", "GH_TOKEN": "fixture"}, "GITHUB_ACTOR_REQUIRED_OR_INVALID"),
                 ({"GITHUB_ACTOR": "actor"}, "GH_TOKEN_REQUIRED_OR_INVALID"),
                 ({"GITHUB_ACTOR": "actor", "GH_TOKEN": "fixture\r\n"}, "GH_TOKEN_REQUIRED_OR_INVALID"),
                 ({"GITHUB_ACTOR": "actor", "GH_TOKEN": "a" * (rg.MAX_TOKEN_BYTES + 1)}, "GH_TOKEN_REQUIRED_OR_INVALID")]
        for environ, reason in cases:
            with self.subTest(reason=reason):
                guard, transport = self.guard(environ=environ)
                self.assert_block(reason, lambda: guard.check_tag(TAG))
                self.assertEqual([], transport.calls)

    def test_authoritative_404_allows_opaque_token_without_push_claim(self):
        guard, transport = self.guard(token_response(), response({"errors": [{"code": "MANIFEST_UNKNOWN"}]}, 404))
        result = guard.check_tag(TAG)
        self.assertTrue(result["tagAvailable"])
        self.assertFalse(result["tagReserved"])
        self.assertFalse(result["writeVerified"])
        self.assertEqual("UNVERIFIED", result["issuedAccess"]["status"])
        self.assertIsNone(result["issuedAccess"]["push"])
        self.assertEqual(2, len(transport.calls))
        token_url, headers, _ = transport.calls[0]
        self.assertTrue(token_url.startswith("https://ghcr.io/token?"))
        self.assertIn("pull%2Cpush", token_url)
        self.assertIn("dimon3898-sys%2Fworld-simulation-shorts-engine", token_url)
        self.assertEqual("identity", headers["Accept-Encoding"])
        self.assertEqual("Basic " + base64.b64encode((ENV["GITHUB_ACTOR"] + ":" + ENV["GH_TOKEN"]).encode()).decode(), headers["Authorization"])
        self.assertEqual("Bearer opaque-fixture-token", transport.calls[1][1]["Authorization"])
        self.assertNotIn(ENV["GH_TOKEN"], json.dumps(result))

    def test_issued_jwt_pull_push_observation_is_not_write_success(self):
        issued = jwt()
        guard, _ = self.guard(token_response(issued), response({"errors": [{"code": "MANIFEST_UNKNOWN"}]}, 404))
        result = guard.check_tag(TAG)
        self.assertEqual("OBSERVED_IN_ISSUED_TOKEN", result["issuedAccess"]["status"])
        self.assertTrue(result["issuedAccess"]["pull"])
        self.assertTrue(result["issuedAccess"]["push"])
        self.assertFalse(result["issuedAccess"]["pushVerified"])
        self.assertNotIn(issued, json.dumps(result))

    def test_issued_jwt_missing_push_blocks_before_manifest(self):
        guard, transport = self.guard(token_response(jwt(("pull",))))
        self.assert_block("ISSUED_PULL_PUSH_NOT_GRANTED", lambda: guard.check_tag(TAG))
        self.assertEqual(1, len(transport.calls))

    def test_issued_jwt_wrong_repository_blocks(self):
        guard, _ = self.guard(token_response(jwt(repository="someone/else")))
        self.assert_block("ISSUED_ACCESS_UNVERIFIED", lambda: guard.check_tag(TAG))

    def test_malformed_jwt_blocks(self):
        for value in ("abc.not-json.sig", "abc..sig", "abc.eyJhY2Nlc3MiOiBbXX0.sig"):
            with self.subTest(value=value):
                guard, _ = self.guard(token_response(value))
                with self.assertRaises(rg.GuardError):
                    guard.check_tag(TAG)

    def test_auth_denial_redirect_and_server_error_block_once(self):
        for status in (301, 307, 401, 403, 404, 500):
            with self.subTest(status=status):
                guard, transport = self.guard(response({"message": ENV["GH_TOKEN"]}, status))
                self.assert_block("TOKEN_HTTP_NOT_200", lambda: guard.check_tag(TAG))
                self.assertEqual(1, len(transport.calls))

    def test_token_conflicts_duplicates_and_controls_block(self):
        fixtures = [response({"token": "a", "access_token": "b"}),
                    rg.Response(200, {}, b'{"token":"a","token":"b"}'),
                    response({"token": "a\n"}), response({"token": "é"}),
                    response({"token": ""}), response({"token": 123})]
        for item in fixtures:
            with self.subTest(body=item.body):
                guard, _ = self.guard(item)
                with self.assertRaises(rg.GuardError):
                    guard.check_tag(TAG)

    def test_oversized_auth_and_json_complexity_block(self):
        guard, _ = self.guard(rg.Response(200, {}, b"x" * (rg.MAX_TOKEN_RESPONSE_BYTES + 1)))
        self.assert_block("RESPONSE_TOO_LARGE", lambda: guard.check_tag(TAG))
        for body in (b'{"token":NaN}', b'[]', b'\xff', b'{"a":' + b'[' * 34 + b'0' + b']' * 34 + b'}'):
            with self.subTest(body=body[:30]):
                self.assert_block("INVALID_JSON_RESPONSE", lambda: rg._json_object(body))

    def test_existing_manifest_blocks_even_when_json_is_invalid(self):
        guard, _ = self.guard(token_response(), rg.Response(200, {}, b"existing"))
        self.assert_block("TAG_ALREADY_EXISTS", lambda: guard.check_tag(TAG))

    def test_manifest_denial_redirect_and_server_error_cannot_mean_unused(self):
        for status in (301, 302, 307, 401, 403, 429, 500):
            with self.subTest(status=status):
                guard, transport = self.guard(token_response(), response({"errors": [{"code": "MANIFEST_UNKNOWN"}]}, status))
                self.assert_block("TAG_ABSENCE_NOT_VERIFIED", lambda: guard.check_tag(TAG))
                self.assertEqual(2, len(transport.calls))

    def test_404_requires_only_manifest_unknown_errors(self):
        for document in ({"errors": []}, {}, {"errors": "MANIFEST_UNKNOWN"},
                         {"errors": [{"code": "NAME_UNKNOWN"}]},
                         {"errors": [{"code": "MANIFEST_UNKNOWN"}, {"code": "DENIED"}]},
                         {"errors": [{"code": "MANIFEST_UNKNOWN"}, "bad"]}):
            with self.subTest(document=document):
                guard, _ = self.guard(token_response(), response(document, 404))
                self.assert_block("TAG_ABSENCE_NOT_MANIFEST_UNKNOWN", lambda: guard.check_tag(TAG))

    def test_404_non_json_and_duplicate_codes_block(self):
        for body in (b"not found", b'{"errors":[],"errors":[{"code":"MANIFEST_UNKNOWN"}]}'):
            guard, _ = self.guard(token_response(), rg.Response(404, {}, body))
            self.assert_block("INVALID_JSON_RESPONSE", lambda: guard.check_tag(TAG))

    def test_network_error_is_redacted_and_not_retried(self):
        guard, transport = self.guard(RuntimeError("secret=" + ENV["GH_TOKEN"]))
        self.assert_block("NETWORK_OR_TLS_FAILURE", lambda: guard.check_tag(TAG))
        self.assertEqual(1, len(transport.calls))
        self.assertEqual("INTERNAL_GUARD_ERROR", str(rg.GuardError("secret=" + ENV["GH_TOKEN"])))

    def test_single_manifest_and_config_bytes_verified(self):
        body, config = image_fixture()
        guard, transport = self.guard(token_response(), manifest_response(body), rg.Response(200, {}, config))
        result = guard.inspect_digest(digest(body))
        self.assertEqual(rg.IMAGE + "@" + digest(body), result["imageReference"])
        self.assertEqual(digest(config), result["configDigest"])
        self.assertEqual("linux/amd64", result["platform"])
        self.assertTrue(result["manifestAndConfigBytesVerified"])
        self.assertFalse(result["layerContentsVerified"])
        self.assertFalse(result["writeVerified"])
        self.assertNotIn("fixture-config-secret", json.dumps(result))
        self.assertEqual(3, len(transport.calls))

    def index_fixture(self, extra=None):
        body, config = image_fixture()
        selected = {"mediaType": OCI_MANIFEST, "digest": digest(body), "size": len(body),
                    "platform": {"os": "linux", "architecture": "amd64"}}
        attestation = {"mediaType": OCI_MANIFEST, "digest": "sha256:" + "a" * 64,
                       "size": 123, "platform": {"os": "unknown", "architecture": "unknown"},
                       "annotations": {"vnd.docker.reference.type": "attestation-manifest"}}
        index = {"schemaVersion": 2, "mediaType": OCI_INDEX,
                 "manifests": [selected, attestation] + (extra or [])}
        return raw(index), body, config, selected

    def test_index_selects_image_and_does_not_fetch_attestation(self):
        index, body, config, _ = self.index_fixture()
        guard, transport = self.guard(token_response(), manifest_response(index, OCI_INDEX),
                                      manifest_response(body), rg.Response(200, {}, config))
        result = guard.inspect_digest(digest(index))
        self.assertEqual(digest(index), result["digest"])
        self.assertEqual(digest(body), result["imageManifestDigest"])
        self.assertEqual(4, len(transport.calls))
        self.assertFalse(any("sha256:" + "a" * 64 in call[0] for call in transport.calls))

    def test_duplicate_or_missing_amd64_candidate_blocks(self):
        index, _, _, selected = self.index_fixture()
        for descriptors in ([selected, dict(selected)], [dict(selected, platform={"os": "linux", "architecture": "arm64"})]):
            body = raw({"schemaVersion": 2, "mediaType": OCI_INDEX, "manifests": descriptors})
            guard, _ = self.guard(token_response(), manifest_response(body, OCI_INDEX))
            self.assert_block("AMD64_IMAGE_NOT_UNIQUE", lambda: guard.inspect_digest(digest(body)))

    def test_attestation_annotation_cannot_hide_second_amd64_image(self):
        _, _, _, selected = self.index_fixture()
        hidden = dict(selected, annotations={"vnd.docker.reference.type": "attestation-manifest"})
        body = raw({"schemaVersion": 2, "mediaType": OCI_INDEX,
                    "manifests": [selected, hidden]})
        guard, _ = self.guard(token_response(), manifest_response(body, OCI_INDEX))
        self.assert_block("INVALID_ATTESTATION_PLATFORM", lambda: guard.inspect_digest(digest(body)))

    def test_docker_manifest_list_and_config_types_supported(self):
        body, config = image_fixture()
        document = json.loads(body)
        manifest_type = "application/vnd.docker.distribution.manifest.v2+json"
        index_type = "application/vnd.docker.distribution.manifest.list.v2+json"
        document["mediaType"] = manifest_type
        document["config"]["mediaType"] = "application/vnd.docker.container.image.v1+json"
        body = raw(document)
        index = raw({"schemaVersion": 2, "mediaType": index_type,
                     "manifests": [{"mediaType": manifest_type, "digest": digest(body),
                                    "size": len(body), "platform": {"os": "linux", "architecture": "amd64"}}]})
        guard, _ = self.guard(token_response(), manifest_response(index, index_type),
                              manifest_response(body, manifest_type), rg.Response(200, {}, config))
        self.assertEqual(digest(body), guard.inspect_digest(digest(index))["imageManifestDigest"])

    def test_nested_index_and_amd64_variant_block(self):
        _, _, _, selected = self.index_fixture()
        for descriptor, reason in ((dict(selected, mediaType=OCI_INDEX), "NESTED_AMD64_INDEX_UNSUPPORTED"),
                                   (dict(selected, platform={"os": "linux", "architecture": "amd64", "variant": "v3"}), "UNSUPPORTED_AMD64_VARIANT")):
            body = raw({"schemaVersion": 2, "mediaType": OCI_INDEX, "manifests": [descriptor]})
            guard, _ = self.guard(token_response(), manifest_response(body, OCI_INDEX))
            self.assert_block(reason, lambda: guard.inspect_digest(digest(body)))

    def test_index_count_and_platform_are_bounded(self):
        _, _, _, selected = self.index_fixture()
        for descriptors, reason in (([selected] * (rg.MAX_INDEX_DESCRIPTORS + 1), "INVALID_INDEX_DESCRIPTORS"),
                                    ([{k: v for k, v in selected.items() if k != "platform"}], "INDEX_PLATFORM_REQUIRED")):
            body = raw({"schemaVersion": 2, "mediaType": OCI_INDEX, "manifests": descriptors})
            guard, _ = self.guard(token_response(), manifest_response(body, OCI_INDEX))
            self.assert_block(reason, lambda: guard.inspect_digest(digest(body)))

    def test_remote_manifest_hash_and_header_must_agree(self):
        body, _ = image_fixture()
        for item, reason in ((manifest_response(body + b" "), "REMOTE_BODY_DIGEST_MISMATCH"),
                             (rg.Response(200, {"Content-Type": OCI_MANIFEST, "Docker-Content-Digest": "sha256:" + "b" * 64}, body), "REMOTE_DIGEST_HEADER_MISMATCH"),
                             (rg.Response(200, {"Content-Type": OCI_MANIFEST}, body), "REMOTE_DIGEST_HEADER_REQUIRED")):
            guard, _ = self.guard(token_response(), item)
            self.assert_block(reason, lambda: guard.inspect_digest(digest(body)))

    def test_manifest_status_and_compression_block(self):
        body, _ = image_fixture()
        for item, reason in ((rg.Response(404, {}, b""), "MANIFEST_HTTP_NOT_200"),
                             (rg.Response(307, {"Location": "https://ghcr.io/elsewhere"}, b""), "MANIFEST_HTTP_NOT_200"),
                             (rg.Response(200, {"Content-Encoding": "gzip"}, body), "UNSUPPORTED_CONTENT_ENCODING")):
            guard, _ = self.guard(token_response(), item)
            self.assert_block(reason, lambda: guard.inspect_digest(digest(body)))

    def test_manifest_media_type_and_schema_are_strict(self):
        for changes, content_type, reason in (({"schemaVersion": True}, OCI_MANIFEST, "INVALID_MANIFEST_SCHEMA"),
                                            ({"mediaType": OCI_INDEX}, OCI_MANIFEST, "INVALID_MANIFEST_SCHEMA"),
                                            ({}, "text/html", "UNSUPPORTED_MANIFEST_MEDIA_TYPE")):
            body, _ = image_fixture(manifest_changes=changes)
            guard, _ = self.guard(token_response(), manifest_response(body, content_type))
            self.assert_block(reason, lambda: guard.inspect_digest(digest(body)))

    def test_config_digest_size_and_platform_are_verified(self):
        body, config = image_fixture()
        guard, _ = self.guard(token_response(), manifest_response(body), rg.Response(200, {}, config + b" "))
        self.assert_block("REMOTE_BODY_DIGEST_MISMATCH", lambda: guard.inspect_digest(digest(body)))
        for changes in ({"architecture": "arm64"}, {"os": "windows"}, {"variant": "v3"}):
            body, config = image_fixture(config_changes=changes)
            guard, _ = self.guard(token_response(), manifest_response(body), rg.Response(200, {}, config))
            self.assert_block("CONFIG_PLATFORM_MISMATCH", lambda: guard.inspect_digest(digest(body)))
        body, config = image_fixture()
        document = json.loads(body)
        document["config"]["size"] += 1
        body = raw(document)
        guard, _ = self.guard(token_response(), manifest_response(body), rg.Response(200, {}, config))
        self.assert_block("REMOTE_BODY_SIZE_MISMATCH", lambda: guard.inspect_digest(digest(body)))

    def test_child_manifest_descriptor_size_is_verified(self):
        index, body, config, _ = self.index_fixture()
        document = json.loads(index)
        document["manifests"][0]["size"] += 1
        index = raw(document)
        guard, _ = self.guard(token_response(), manifest_response(index, OCI_INDEX), manifest_response(body))
        self.assert_block("REMOTE_BODY_SIZE_MISMATCH", lambda: guard.inspect_digest(digest(index)))

    def test_descriptor_limits_and_invalid_types_block(self):
        for change, reason in (({"size": True}, "INVALID_DESCRIPTOR_SIZE"),
                               ({"size": 0}, "INVALID_DESCRIPTOR_SIZE"),
                               ({"size": rg.MAX_CONFIG_BYTES + 1}, "DESCRIPTOR_TOO_LARGE"),
                               ({"mediaType": "bad"}, "INVALID_DESCRIPTOR_MEDIA_TYPE"),
                               ({"mediaType": []}, "INVALID_DESCRIPTOR_MEDIA_TYPE"),
                               ({"digest": "sha256:bad"}, "INVALID_DIGEST")):
            body, _ = image_fixture()
            document = json.loads(body)
            document["config"].update(change)
            body = raw(document)
            guard, _ = self.guard(token_response(), manifest_response(body))
            self.assert_block(reason, lambda: guard.inspect_digest(digest(body)))

    def test_layer_descriptors_checked_without_downloading(self):
        layer = {"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                 "digest": "sha256:" + "d" * 64, "size": 12345,
                 "urls": ["https://untrusted.example/never-request"]}
        body, config = image_fixture(manifest_changes={"layers": [layer]})
        guard, transport = self.guard(token_response(), manifest_response(body), rg.Response(200, {}, config))
        self.assertTrue(guard.inspect_digest(digest(body))["remotePresenceVerified"])
        self.assertEqual(3, len(transport.calls))
        body, _ = image_fixture(manifest_changes={"layers": [dict(layer, size=-1)]})
        guard, _ = self.guard(token_response(), manifest_response(body))
        self.assert_block("INVALID_DESCRIPTOR_SIZE", lambda: guard.inspect_digest(digest(body)))

    def test_approved_blob_redirect_strips_all_authentication(self):
        for host in ("pkg-containers.githubusercontent.com", "ghcr.io"):
            body, config = image_fixture()
            signed_url = "https://" + host + "/blob?sig=fixture-signed-secret"
            guard, transport = self.guard(token_response(), manifest_response(body),
                                          rg.Response(307, {"Location": signed_url}, b""),
                                          rg.Response(200, {}, config))
            result = guard.inspect_digest(digest(body))
            self.assertEqual(signed_url, transport.calls[-1][0])
            self.assertNotIn("Authorization", transport.calls[-1][1])
            self.assertNotIn(signed_url, json.dumps(result))
            self.assertNotIn("fixture-signed-secret", json.dumps(result))

    def test_unsafe_blob_redirect_hosts_schemes_credentials_and_ports_block(self):
        targets = ("http://ghcr.io/blob", "https://evil.example/blob", "https://ghcr.io.evil.example/blob",
                   "https://user@ghcr.io/blob", "https://ghcr.io:444/blob", "https://ghcr.io/blob#fragment",
                   "/relative/blob", "https://ghcr.io/blob\n", None)
        for target in targets:
            with self.subTest(target=target):
                body, _ = image_fixture()
                guard, transport = self.guard(token_response(), manifest_response(body), rg.Response(307, {"Location": target}, b""))
                with self.assertRaises(rg.GuardError):
                    guard.inspect_digest(digest(body))
                self.assertEqual(3, len(transport.calls))

    def test_second_blob_redirect_and_blob_denial_block(self):
        body, _ = image_fixture()
        guard, transport = self.guard(token_response(), manifest_response(body),
                                      rg.Response(307, {"Location": "https://pkg-containers.githubusercontent.com/blob"}, b""),
                                      rg.Response(307, {"Location": "https://ghcr.io/again"}, b""))
        self.assert_block("CONFIG_HTTP_NOT_200", lambda: guard.inspect_digest(digest(body)))
        self.assertEqual(4, len(transport.calls))
        guard, _ = self.guard(token_response(), manifest_response(body), rg.Response(403, {}, b""))
        self.assert_block("CONFIG_HTTP_NOT_200", lambda: guard.inspect_digest(digest(body)))

    def test_duplicate_digest_headers_block(self):
        body, _ = image_fixture()
        headers = {"Content-Type": OCI_MANIFEST, "Docker-Content-Digest": digest(body),
                   "docker-content-digest": "sha256:" + "b" * 64}
        guard, _ = self.guard(token_response(), rg.Response(200, headers, body))
        self.assert_block("INVALID_RESPONSE_HEADER", lambda: guard.inspect_digest(digest(body)))

    def test_cli_safe_pass_and_block_exit_codes(self):
        guard, _ = self.guard(token_response(), response({"errors": [{"code": "MANIFEST_UNKNOWN"}]}, 404))
        out = io.StringIO()
        with patch.object(rg, "RegistryGuard", return_value=guard), redirect_stdout(out):
            self.assertEqual(0, rg.main(["check-tag", "--tag", TAG]))
        self.assertEqual("PASS", json.loads(out.getvalue())["status"])
        guard, _ = self.guard(RuntimeError("secret=" + ENV["GH_TOKEN"]))
        out = io.StringIO()
        with patch.object(rg, "RegistryGuard", return_value=guard), redirect_stdout(out):
            self.assertEqual(1, rg.main(["check-tag", "--tag", TAG]))
        self.assertEqual("NETWORK_OR_TLS_FAILURE", json.loads(out.getvalue())["reason"])
        self.assertNotIn(ENV["GH_TOKEN"], out.getvalue())


class HTTPTransportTests(unittest.TestCase):
    class Stream(io.BytesIO):
        def __init__(self, body, headers=None, code=200):
            super().__init__(body)
            self.code = code
            self.headers = Message()
            for name, value in (headers or {}).items():
                self.headers[name] = value

    def test_transport_one_request_fixed_timeout_and_bounded_read(self):
        stream = self.Stream(b"fixture", {"Content-Length": "7"})
        with patch.object(rg, "build_opener") as build:
            build.return_value.open.return_value = stream
            result = rg._http_get("https://ghcr.io/token", {"Accept-Encoding": "identity"}, 7)
        self.assertEqual(b"fixture", result.body)
        self.assertEqual(1, build.return_value.open.call_count)
        self.assertEqual(rg.TIMEOUT_SECONDS, build.return_value.open.call_args.kwargs["timeout"])
        self.assertIsInstance(build.call_args.args[0], rg._NoRedirect)
        self.assertTrue(stream.closed)

    def test_transport_oversize_length_and_body_fail(self):
        for stream in (self.Stream(b"fixture", {"Content-Length": "8"}),
                       self.Stream(b"fixture", {"Content-Length": "7,7"}), self.Stream(b"fixture!")):
            with patch.object(rg, "build_opener") as build:
                build.return_value.open.return_value = stream
                with self.assertRaises(rg.GuardError):
                    rg._http_get("https://ghcr.io/token", {}, 7)
                self.assertEqual(1, build.return_value.open.call_count)

    def test_transport_failure_does_not_emit_exception_url(self):
        with patch.object(rg, "build_opener") as build:
            build.return_value.open.side_effect = RuntimeError("https://host/?secret=do-not-emit")
            with self.assertRaises(rg.GuardError) as caught:
                rg._http_get("https://ghcr.io/token", {}, 7)
        self.assertEqual("NETWORK_OR_TLS_FAILURE", str(caught.exception))
        self.assertEqual(1, build.return_value.open.call_count)


if __name__ == "__main__":
    unittest.main()
