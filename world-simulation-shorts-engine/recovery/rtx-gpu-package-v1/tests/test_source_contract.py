"""Source-contract and isolated-context checks using only synthetic local files."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "stage_package.py"
SPEC = importlib.util.spec_from_file_location("rtx_source_contract_under_test", MODULE_PATH)
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)

FIRST_COMMIT = "a" * 40
SECOND_COMMIT = "b" * 40


def sha256(body):
    return hashlib.sha256(body).hexdigest()


class SourceContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rtx-contract-test-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "checkout"
        self.repo.mkdir()
        self.source_path = "world-simulation-shorts-engine/web/renderer.mjs"
        self.source_body = b"export const rendering = 'preserved';\n"
        self.write_source(self.source_path, self.source_body)
        self.contract = {
            "schema": "RTX_GPU_SOURCE_CONTRACT_V1",
            "files": [self.record(self.source_path, self.source_body)],
        }
        self.overlay_path = stage.PACKAGE + "/gpu_launcher.py"
        self.overlay_body = b"print('explicit synthetic launcher')\n"
        self.write_source(self.overlay_path, self.overlay_body)
        self.destination = self.base / "context"

    def write_source(self, path, body):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return target

    def record(self, path, body, commits=None):
        return {"repoPath": path, "sha256": sha256(body), "bytes": len(body),
                "sourceCommits": commits or [FIRST_COMMIT]}

    def changed_contract(self, **fields):
        contract = copy.deepcopy(self.contract)
        contract.update(fields)
        return contract

    def stage_synthetic(self, **kwargs):
        return stage.stage_context(self.repo, self.contract, self.destination,
                                   package_files=[self.overlay_path], check_git=False, **kwargs)

    def read_receipt(self):
        return json.loads((self.destination / "STAGING_RECEIPT.json").read_text())

    def write_receipt(self, receipt):
        (self.destination / "STAGING_RECEIPT.json").write_text(json.dumps(receipt))

    def assert_context_absent(self, destination=None):
        destination = destination or self.destination
        self.assertFalse(destination.exists())
        self.assertEqual(list(destination.parent.glob("." + destination.name + "-*")), [])

    def test_valid_explicit_contract_and_bound_runtime_route(self):
        contract = self.changed_contract(runtimeRoutes=[{"url": "/renderer.mjs",
                                                          "repoPath": self.source_path}])
        records = stage.validate_contract(contract)
        self.assertEqual(records, contract["files"])
        with mock.patch.object(stage, "git_read", side_effect=AssertionError("Git is forbidden")):
            result = stage.verify_contract(self.repo, contract, check_git=False)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["files"], 1)
        self.assertEqual(result["bytes"], len(self.source_body))
        self.assertFalse(result["gitBlobVerification"])
        self.assertEqual(result["networkRequests"], 0)

    def test_schema_and_nonempty_explicit_file_list_are_required(self):
        for contract in (None, [], {}, self.changed_contract(schema="OTHER"),
                         self.changed_contract(files=[]), self.changed_contract(files={}),
                         self.changed_contract(files=[None])):
            with self.subTest(contract=contract), self.assertRaises(stage.ContractError):
                stage.validate_contract(contract)

    def test_traversal_absolute_and_noncanonical_source_paths_are_rejected(self):
        paths = ("../escape", "/absolute", "a/../escape", "a/./b", "a//b",
                 "a\\b", "a\x00b", "", ".git/config", "nested/.git/config")
        for path in paths:
            with self.subTest(path=path):
                contract = copy.deepcopy(self.contract)
                contract["files"][0]["repoPath"] = path
                with self.assertRaises(stage.ContractError):
                    stage.validate_contract(contract)

    def test_original_sources_cannot_use_new_package_overlay_prefix(self):
        contract = self.changed_contract(files=[self.record(self.overlay_path, self.overlay_body)])
        with self.assertRaisesRegex(stage.ContractError, "OVERLAY_SOURCE_PATH"):
            stage.validate_contract(contract)

    def test_duplicate_source_paths_reject_matching_and_conflicting_hashes(self):
        for conflicting in (False, True):
            with self.subTest(conflicting=conflicting):
                duplicate = copy.deepcopy(self.contract["files"][0])
                if conflicting:
                    duplicate["sha256"] = "f" * 64
                    duplicate["sourceCommits"] = [SECOND_COMMIT]
                contract = self.changed_contract(files=[self.contract["files"][0], duplicate])
                with self.assertRaisesRegex(stage.ContractError, "DUPLICATE"):
                    stage.validate_contract(contract)

    def test_source_size_and_digest_must_have_valid_types_and_bounds(self):
        invalid = (("bytes", True), ("bytes", -1), ("bytes", 1.5),
                   ("bytes", stage.MAX_FILE_BYTES + 1), ("sha256", "F" * 64),
                   ("sha256", "a" * 63), ("sha256", "z" * 64),
                   ("sha256", int("1" * 64)))
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                contract = copy.deepcopy(self.contract)
                contract["files"][0][field] = value
                with self.assertRaises(stage.ContractError):
                    stage.validate_contract(contract)

    def test_total_declared_bytes_are_bounded(self):
        records = [dict(self.contract["files"][0], repoPath="large/" + str(i),
                        bytes=stage.MAX_FILE_BYTES) for i in range(5)]
        with self.assertRaisesRegex(stage.ContractError, "BYTE_LIMIT"):
            stage.validate_contract(self.changed_contract(files=records))

    def test_source_commits_require_unique_full_hex_strings(self):
        invalid = (None, [], FIRST_COMMIT, ["a" * 39], ["A" * 40],
                   [FIRST_COMMIT, FIRST_COMMIT], [False], [[FIRST_COMMIT]], [{}])
        for commits in invalid:
            with self.subTest(commits=commits):
                contract = copy.deepcopy(self.contract)
                contract["files"][0]["sourceCommits"] = commits
                with self.assertRaises(stage.ContractError):
                    stage.validate_contract(contract)

    def test_runtime_routes_must_resolve_to_explicit_source_records(self):
        invalid = (None, {}, [None], [{"url": "relative", "repoPath": self.source_path}],
                   [{"url": "/missing", "repoPath": "missing.mjs"}],
                   [{"url": "/same", "repoPath": self.source_path}] * 2)
        for routes in invalid:
            with self.subTest(routes=routes), self.assertRaises(stage.ContractError):
                stage.validate_contract(self.changed_contract(runtimeRoutes=routes))

    def test_runtime_route_traversal_and_query_aliases_are_rejected(self):
        for url in ("/../renderer", "/a/./renderer", "/renderer?x=1", "/renderer#x",
                    "/renderer\\x", "/renderer\x00x"):
            with self.subTest(url=url), self.assertRaises(stage.ContractError):
                stage.validate_contract(self.changed_contract(runtimeRoutes=[{
                    "url": url, "repoPath": self.source_path}]))

    def test_manifest_authorities_cannot_disagree_with_selected_sources(self):
        valid = {self.source_path: sha256(self.source_body)}
        stage.validate_contract(self.changed_contract(manifestSha256=valid))
        for authorities in (None, [], {self.source_path: "f" * 64}, {"absent": "f" * 64}):
            with self.subTest(authorities=authorities), self.assertRaises(stage.ContractError):
                stage.validate_contract(self.changed_contract(manifestSha256=authorities))

    def test_ancestry_requires_full_hex_commit_strings(self):
        valid = {"ancestor": FIRST_COMMIT, "descendant": SECOND_COMMIT}
        stage.validate_contract(self.changed_contract(ancestry=[valid]))
        for ancestry in (None, {}, [None], [{"ancestor": "short", "descendant": SECOND_COMMIT}],
                         [{"ancestor": int("1" * 40), "descendant": SECOND_COMMIT}]):
            with self.subTest(ancestry=ancestry), self.assertRaises(stage.ContractError):
                stage.validate_contract(self.changed_contract(ancestry=ancestry))

    def test_runtime_policy_requires_a_dictionary_and_explicit_entrypoint_list(self):
        for policy in (None, [], "hardware", {"activeEntrypoints": None},
                       {"activeEntrypoints": self.overlay_path}):
            with self.subTest(policy=policy), self.assertRaises(stage.ContractError):
                stage.validate_contract(self.changed_contract(runtimePolicy=policy))

    def test_source_hash_mismatch_is_rejected_even_with_equal_length(self):
        changed = b"X" + self.source_body[1:]
        self.write_source(self.source_path, changed)
        with self.assertRaisesRegex(stage.ContractError, "SOURCE_HASH_MISMATCH"):
            stage.verify_contract(self.repo, self.contract, check_git=False)

    def test_missing_or_length_changed_sources_are_rejected(self):
        target = self.repo / self.source_path
        target.write_bytes(self.source_body + b"extra")
        with self.assertRaisesRegex(stage.ContractError, "SOURCE_SIZE_MISMATCH"):
            stage.verify_contract(self.repo, self.contract, check_git=False)
        target.unlink()
        with self.assertRaises(stage.ContractError):
            stage.verify_contract(self.repo, self.contract, check_git=False)

    def test_file_symlinks_are_rejected_even_when_target_bytes_match(self):
        target = self.repo / self.source_path
        target.unlink()
        real_file = self.write_source("real.mjs", self.source_body)
        target.symlink_to(real_file)
        with self.assertRaisesRegex(stage.ContractError, "SOURCE_SYMLINK_FORBIDDEN"):
            stage.verify_contract(self.repo, self.contract, check_git=False)

    def test_directory_symlink_components_are_rejected(self):
        real_file = self.write_source("real/renderer.mjs", self.source_body)
        (self.repo / "alias").symlink_to(real_file.parent, target_is_directory=True)
        contract = self.changed_contract(files=[self.record("alias/renderer.mjs", self.source_body)])
        with self.assertRaisesRegex(stage.ContractError, "SOURCE_SYMLINK_FORBIDDEN"):
            stage.verify_contract(self.repo, contract, check_git=False)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO support required")
    def test_fifo_is_rejected_without_a_blocking_open(self):
        fifo_path = "fifo-input"
        os.mkfifo(self.repo / fifo_path)
        contract = self.changed_contract(files=[self.record(fifo_path, b"")])
        original_open = os.open

        def nonblocking_open(path, flags, *args, **kwargs):
            # Assert before opening so a regression cannot hang this test suite.
            self.assertTrue(flags & os.O_NONBLOCK, "FIFO inspection must never block")
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(stage.os, "open", side_effect=nonblocking_open):
            with self.assertRaisesRegex(stage.ContractError, "REGULAR_SOURCE_REQUIRED"):
                stage.verify_contract(self.repo, contract, check_git=False)

    def test_git_verification_checks_ancestry_and_every_declared_source_commit(self):
        contract = copy.deepcopy(self.contract)
        contract["files"][0]["sourceCommits"] = [FIRST_COMMIT, SECOND_COMMIT]
        contract["ancestry"] = [{"ancestor": FIRST_COMMIT, "descendant": SECOND_COMMIT}]

        def local_objects(repo, arguments):
            self.assertEqual(repo, self.repo)
            if arguments[0] == "merge-base":
                return b""
            if arguments[1] == "-s":
                return str(len(self.source_body)).encode() + b"\n"
            return self.source_body

        with mock.patch.object(stage, "git_read", side_effect=local_objects) as git:
            result = stage.verify_contract(self.repo, contract)
        self.assertTrue(result["gitBlobVerification"])
        self.assertEqual(git.call_args_list, [
            mock.call(self.repo, ["merge-base", "--is-ancestor", FIRST_COMMIT, SECOND_COMMIT]),
            mock.call(self.repo, ["cat-file", "-s", FIRST_COMMIT + ":" + self.source_path]),
            mock.call(self.repo, ["cat-file", "blob", FIRST_COMMIT + ":" + self.source_path]),
            mock.call(self.repo, ["cat-file", "-s", SECOND_COMMIT + ":" + self.source_path]),
            mock.call(self.repo, ["cat-file", "blob", SECOND_COMMIT + ":" + self.source_path]),
        ])

    def test_git_blob_conflict_in_any_source_commit_rejects_all_staging(self):
        contract = copy.deepcopy(self.contract)
        contract["files"][0]["sourceCommits"] = [FIRST_COMMIT, SECOND_COMMIT]
        wrong = b"X" + self.source_body[1:]
        size = str(len(self.source_body)).encode()
        with mock.patch.object(stage, "git_read", side_effect=[size, self.source_body, size, wrong]):
            with self.assertRaisesRegex(stage.ContractError, "PINNED_GIT_BLOB_MISMATCH"):
                stage.stage_context(self.repo, contract, self.destination)
        self.assert_context_absent()

    def test_git_blob_length_mismatch_is_rejected(self):
        with mock.patch.object(stage, "git_read", return_value=str(len(self.source_body) + 5).encode()) as git:
            with self.assertRaisesRegex(stage.ContractError, "PINNED_GIT_BLOB"):
                stage.verify_contract(self.repo, self.contract)
        git.assert_called_once_with(self.repo, ["cat-file", "-s", FIRST_COMMIT + ":" + self.source_path])

    def test_failed_git_ancestry_does_not_publish_or_create_context_parent(self):
        contract = self.changed_contract(ancestry=[{"ancestor": FIRST_COMMIT,
                                                   "descendant": SECOND_COMMIT}])
        destination = self.base / "not-created" / "context"
        with mock.patch.object(stage, "git_read", side_effect=stage.ContractError("ANCESTRY_FAILED")) as git:
            with self.assertRaisesRegex(stage.ContractError, "ANCESTRY_FAILED"):
                stage.stage_context(self.repo, contract, destination)
        git.assert_called_once_with(self.repo, ["merge-base", "--is-ancestor", FIRST_COMMIT, SECOND_COMMIT])
        self.assertFalse(destination.parent.exists())

    def test_staging_requires_destination_outside_checkout_and_its_ancestors(self):
        for destination in (self.repo, self.repo / "context", self.base):
            with self.subTest(destination=destination), self.assertRaisesRegex(
                    stage.ContractError, "OUTSIDE_CHECKOUT"):
                stage.stage_context(self.repo, self.contract, destination, check_git=False)
        self.assertFalse((self.repo / "context").exists())

    def test_existing_destination_is_never_overwritten_even_if_empty(self):
        self.destination.mkdir()
        with self.assertRaisesRegex(stage.ContractError, "NEW_EMPTY_CONTEXT_DESTINATION"):
            self.stage_synthetic()
        self.assertEqual(list(self.destination.iterdir()), [])
        self.destination.rmdir()
        self.destination.write_bytes(b"existing user bytes")
        with self.assertRaises(stage.ContractError):
            self.stage_synthetic()
        self.assertEqual(self.destination.read_bytes(), b"existing user bytes")

    def test_destination_symlink_and_parent_symlink_aliases_are_rejected(self):
        self.destination.symlink_to(self.base / "absent-context")
        with self.assertRaisesRegex(stage.ContractError, "CONTEXT_SYMLINK_FORBIDDEN"):
            self.stage_synthetic()
        self.destination.unlink()
        alias = self.base / "checkout-alias"
        alias.symlink_to(self.repo, target_is_directory=True)
        with self.assertRaisesRegex(stage.ContractError, "CONTEXT_SYMLINK_FORBIDDEN"):
            stage.stage_context(self.repo, self.contract, alias / "context", check_git=False)
        self.assertFalse((self.repo / "context").exists())

    def test_staging_copies_only_explicit_sources_and_overlay_files(self):
        self.write_source("private/not-selected.txt", b"unselected bytes")
        self.write_source(".git/config", b"synthetic metadata never copied")
        self.write_source(stage.PACKAGE + "/not-selected.py", b"unselected package bytes")
        receipt = self.stage_synthetic()
        staged_repo = self.destination / "repo"
        paths = {str(path.relative_to(staged_repo)) for path in staged_repo.rglob("*") if path.is_file()}
        self.assertEqual(paths, {self.source_path, self.overlay_path})
        self.assertEqual((staged_repo / self.source_path).read_bytes(), self.source_body)
        self.assertEqual((staged_repo / self.overlay_path).read_bytes(), self.overlay_body)
        self.assertEqual({r["repoPath"] for r in receipt["files"]}, paths)
        self.assertEqual([r["repoPath"] for r in receipt["packageOverlay"]], [self.overlay_path])
        self.assertFalse(receipt["gpuExecuted"])
        self.assertFalse(receipt["deployed"])
        self.assertEqual(receipt["networkRequests"], 0)
        self.assertEqual((self.repo / self.source_path).read_bytes(), self.source_body)

    def test_overlay_prefix_traversal_and_duplicates_are_rejected(self):
        for overlay in ([self.source_path], [stage.PACKAGE + "/../escape.py"],
                        [self.overlay_path, self.overlay_path]):
            with self.subTest(overlay=overlay), self.assertRaises(stage.ContractError):
                stage.stage_context(self.repo, self.contract, self.destination,
                                    package_files=overlay, check_git=False)
            self.assert_context_absent()

    def test_declared_hardware_entrypoint_requires_explicit_overlay(self):
        contract = self.changed_contract(runtimePolicy={"activeEntrypoints": [
            self.overlay_path, stage.PACKAGE + "/hardware_render.mjs"]})
        with self.assertRaisesRegex(stage.ContractError, "ACTIVE_ENTRYPOINT_OVERLAY"):
            stage.stage_context(self.repo, contract, self.destination,
                                package_files=[self.overlay_path], check_git=False)
        self.assert_context_absent()

    def test_bad_source_or_missing_overlay_does_not_create_empty_context(self):
        destination = self.base / "not-created" / "context"
        invalid = copy.deepcopy(self.contract)
        invalid["files"][0]["sha256"] = "f" * 64
        with self.assertRaises(stage.ContractError):
            stage.stage_context(self.repo, invalid, destination, check_git=False)
        self.assertFalse(destination.parent.exists())
        with self.assertRaises(stage.ContractError):
            stage.stage_context(self.repo, self.contract, destination,
                                package_files=[stage.PACKAGE + "/missing.py"], check_git=False)
        self.assertFalse(destination.parent.exists())

    def test_total_staged_byte_limit_includes_package_overlay(self):
        destination = self.base / "not-created" / "context"
        limit = len(self.source_body) + len(self.overlay_body) - 1
        self.assertLess(len(self.source_body), limit)
        with mock.patch.object(stage, "MAX_TOTAL_BYTES", limit):
            with self.assertRaisesRegex(stage.ContractError, "BYTE_LIMIT"):
                stage.stage_context(self.repo, self.contract, destination,
                                    package_files=[self.overlay_path], check_git=False)
        self.assertFalse(destination.parent.exists())

    def test_source_change_after_verification_leaves_no_partial_context(self):
        original_verify = stage.verify_contract

        def verify_then_change(repo, contract, **kwargs):
            result = original_verify(repo, contract, **kwargs)
            self.write_source(self.source_path, b"X" + self.source_body[1:])
            return result

        with mock.patch.object(stage, "verify_contract", side_effect=verify_then_change):
            with self.assertRaisesRegex(stage.ContractError, "SOURCE_CHANGED_DURING_STAGING"):
                self.stage_synthetic()
        self.assert_context_absent()

    def test_destination_appearing_during_staging_is_preserved(self):
        original_mkdtemp = tempfile.mkdtemp

        def racing_destination(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            self.destination.mkdir()
            (self.destination / "external.txt").write_bytes(b"keep concurrent owner bytes")
            return path

        with mock.patch.object(stage.tempfile, "mkdtemp", side_effect=racing_destination):
            with self.assertRaisesRegex(stage.ContractError, "CONTEXT_DESTINATION_APPEARED"):
                self.stage_synthetic()
        self.assertEqual((self.destination / "external.txt").read_bytes(), b"keep concurrent owner bytes")
        self.assertEqual(list(self.base.glob(".context-*")), [])

    def test_empty_destination_created_at_publication_is_never_replaced(self):
        original_publish = stage._publish_new_directory
        observed_inode = []

        def racing_publication(*args, **kwargs):
            self.destination.mkdir()
            observed_inode.append(self.destination.stat().st_ino)
            return original_publish(*args, **kwargs)

        with mock.patch.object(stage, "_publish_new_directory", side_effect=racing_publication):
            with self.assertRaises(stage.ContractError):
                self.stage_synthetic()
        self.assertEqual(self.destination.stat().st_ino, observed_inode[0])
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual(list(self.base.glob(".context-*")), [])

    def test_staged_context_roundtrip_is_offline_and_requires_git_receipt_by_default(self):
        self.stage_synthetic()
        with mock.patch.object(stage, "git_read", side_effect=AssertionError("No staged Git queries")):
            result = stage.verify_staged_context(self.destination, require_git_receipt=False)
            with self.assertRaisesRegex(stage.ContractError, "PINNED_SOURCE_VERIFICATION_RECEIPT"):
                stage.verify_staged_context(self.destination)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["files"], 2)
        self.assertEqual(result["gitQueries"], 0)
        self.assertEqual(result["networkRequests"], 0)
        self.assertFalse(result["gpuExecuted"])

    def test_verified_git_receipt_supports_default_staged_context_check(self):
        def local_blob(repo, arguments):
            return str(len(self.source_body)).encode() if arguments[1] == "-s" else self.source_body

        with mock.patch.object(stage, "git_read", side_effect=local_blob):
            stage.stage_context(self.repo, self.contract, self.destination,
                                package_files=[self.overlay_path])
        with mock.patch.object(stage, "git_read", side_effect=AssertionError("No staged Git queries")):
            result = stage.verify_staged_context(self.destination)
        self.assertEqual(result["status"], "PASS")

    def test_staged_original_bytes_and_overlay_bytes_are_both_verified(self):
        self.stage_synthetic()
        for path, body in ((self.source_path, self.source_body), (self.overlay_path, self.overlay_body)):
            with self.subTest(path=path):
                target = self.destination / "repo" / path
                target.write_bytes(b"X" + body[1:])
                with self.assertRaises(stage.ContractError):
                    stage.verify_staged_context(self.destination, require_git_receipt=False)
                target.write_bytes(body)

    def test_missing_staged_file_is_rejected(self):
        self.stage_synthetic()
        (self.destination / "repo" / self.overlay_path).unlink()
        with self.assertRaises(stage.ContractError):
            stage.verify_staged_context(self.destination, require_git_receipt=False)

    def test_staged_contract_hash_is_bound_to_receipt(self):
        self.stage_synthetic()
        target = self.destination / "source_contract.json"
        contract = json.loads(target.read_text())
        contract["runtimeRoutes"] = [{"url": "/different", "repoPath": self.source_path}]
        target.write_text(json.dumps(contract))
        with self.assertRaisesRegex(stage.ContractError, "STAGING_RECEIPT_CONTRADICTION"):
            stage.verify_staged_context(self.destination, require_git_receipt=False)

    def test_receipt_file_inventory_cannot_omit_duplicate_or_rebind_files(self):
        self.stage_synthetic()
        original = self.read_receipt()
        inventories = (original["files"][:-1], original["files"] + [original["files"][0]],
                       [original["files"][0], original["files"][0]],
                       [dict(original["files"][0], sha256="f" * 64), original["files"][1]])
        for inventory in inventories:
            with self.subTest(inventory=inventory):
                receipt = copy.deepcopy(original)
                receipt["files"] = inventory
                self.write_receipt(receipt)
                with self.assertRaisesRegex(stage.ContractError, "STAGED_FILE_INVENTORY"):
                    stage.verify_staged_context(self.destination, require_git_receipt=False)

    def test_receipt_cannot_claim_success_after_failed_or_remote_actions(self):
        self.stage_synthetic()
        original = self.read_receipt()
        for field, value in (("status", "FAIL"), ("gpuExecuted", True),
                             ("deployed", True), ("networkRequests", 1)):
            with self.subTest(field=field):
                receipt = copy.deepcopy(original)
                receipt[field] = value
                self.write_receipt(receipt)
                with self.assertRaisesRegex(stage.ContractError, "STAGING_RECEIPT_CONTRADICTION"):
                    stage.verify_staged_context(self.destination, require_git_receipt=False)

    def test_staged_overlay_receipt_rejects_outside_prefix_and_duplicate_paths(self):
        self.stage_synthetic()
        original = self.read_receipt()
        outside = dict(original["packageOverlay"][0], repoPath="outside-package.py")
        for overlays in ([outside], original["packageOverlay"] * 2):
            with self.subTest(overlays=overlays):
                receipt = copy.deepcopy(original)
                receipt["packageOverlay"] = overlays
                self.write_receipt(receipt)
                with self.assertRaisesRegex(stage.ContractError, "PACKAGE_OVERLAY_IDENTITY"):
                    stage.verify_staged_context(self.destination, require_git_receipt=False)

    def test_staged_symlink_cannot_replace_verified_overlay(self):
        self.stage_synthetic()
        target = self.destination / "repo" / self.overlay_path
        target.unlink()
        target.symlink_to(self.repo / self.overlay_path)
        with self.assertRaisesRegex(stage.ContractError, "SOURCE_SYMLINK_FORBIDDEN"):
            stage.verify_staged_context(self.destination, require_git_receipt=False)


if __name__ == "__main__":
    unittest.main()
