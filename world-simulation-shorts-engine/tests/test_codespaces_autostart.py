"""Phone-only Codespaces sync regressions using isolated local Git repositories.

No production repository, access file, server or renderer is touched. A real
temporary bare remote supplies commits; only its repository allowlist check is
patched. Production origin validation is covered separately without fetching.
"""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deployment import codespaces_autostart as autostart
from deployment.security import SecurityError


@unittest.skipUnless(shutil.which("git"), "Git is required for isolated sync tests")
class LocalGitFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wss-codespaces-sync-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.publisher = self.root / "publisher"
        self.repo = self.root / "checkout"
        self.git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0",
                        "GIT_CONFIG_GLOBAL": os.devnull,
                        "GIT_CONFIG_SYSTEM": os.devnull}
        self.git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.publisher))
        self.configure(self.publisher)
        self.write(self.publisher, ".gitignore", "projects/\ncache/\ndeployment/runtime/\n")
        self.write(self.publisher, "README.md", "Preserved original project\n")
        self.write(self.publisher, "data/approved.txt", "GIS and original assets preserved\n")
        self.write(self.publisher, "deployment/start_codespace.py", "# Initial startup fixture\n")
        self.commit(self.publisher, "initial main")
        self.git(self.publisher, "push", "origin", "main")
        self.git(self.root, "clone", str(self.remote), str(self.repo))
        self.configure(self.repo)
        self.write(self.repo, "projects/project_fixture/renders/checkpoint.json",
                   '{"complete":false,"completed_scenes":4}\n')
        self.write(self.repo, "projects/project_fixture/final/master_v3.mp4",
                   b"SYNTHETIC_PRESERVED_MASTER_NOT_VIDEO\x00\x01")
        self.write(self.repo, "cache/scene_fixture.mp4", b"SYNTHETIC_CACHE_NOT_VIDEO\x02\x03")
        self.write(self.repo, "deployment/runtime/test-state/status.json", '{"status":"interrupted"}\n')
        self.original_commit = self.head()

    def git(self, cwd, *args):
        result = subprocess.run(["git", *args], cwd=cwd, env=self.git_env,
                                text=True, capture_output=True, check=True, timeout=10)
        return result.stdout.strip()

    def configure(self, repo):
        self.git(repo, "config", "user.name", "Synthetic Codespaces Fixture")
        self.git(repo, "config", "user.email", "fixture@example.invalid")
        self.git(repo, "config", "commit.gpgsign", "false")

    @staticmethod
    def write(repo, relative, value):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode() if isinstance(value, str) else value)
        return path

    def commit(self, repo, message, *, force_paths=()):
        self.git(repo, "add", "--all")
        for relative in force_paths:
            self.git(repo, "add", "--force", "--", relative)
        self.git(repo, "commit", "-m", message)
        return self.git(repo, "rev-parse", "HEAD")

    def upstream(self, relative="deployment/start_codespace.py", value="# Fresh startup fixture\n",
                 *, force=False):
        self.write(self.publisher, relative, value)
        commit = self.commit(self.publisher, "upstream fixture change",
                             force_paths=[relative] if force else [])
        self.git(self.publisher, "push", "origin", "main")
        return commit

    def head(self):
        return self.git(self.repo, "rev-parse", "HEAD")

    @staticmethod
    def tree(repo):
        """Exact working-tree bytes and link targets, excluding Git bookkeeping."""
        result = {}
        for path in repo.rglob("*"):
            relative = path.relative_to(repo)
            if relative.parts[0] == ".git":
                continue
            if path.is_symlink():
                result[str(relative)] = ("symlink", os.readlink(path))
            elif path.is_file():
                result[str(relative)] = ("file", path.read_bytes())
            elif path.is_dir():
                result[str(relative)] = ("directory", None)
        return result

    def protected(self):
        return {name: value for name, value in self.tree(self.repo).items()
                if name.split("/", 1)[0] in {"projects", "cache"} or
                name.startswith("deployment/runtime/")}

    def sync(self, **kwargs):
        # Local bare URLs are accepted only inside this explicitly isolated test.
        with patch.object(autostart, "validate_repository", return_value=None):
            return autostart.synchronize_main(self.repo, **kwargs)

    def assert_sync_rejected_without_file_loss(self, code):
        before, commit = self.tree(self.repo), self.head()
        with self.assertRaises(SecurityError) as error:
            self.sync()
        self.assertEqual(error.exception.code, code)
        self.assertEqual(self.head(), commit)
        self.assertEqual(self.tree(self.repo), before)


class SynchronizeMainTests(LocalGitFixture):
    def test_fast_forward_updates_startup_and_preserves_data_projects_cache_checkpoints(self):
        before_protected = self.protected()
        approved = (self.repo / "data/approved.txt").read_bytes()
        target = self.upstream()
        result = self.sync()
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["before_commit"], self.original_commit)
        self.assertEqual(result["after_commit"], target)
        self.assertEqual(self.head(), target)
        self.assertEqual((self.repo / "deployment/start_codespace.py").read_text(), "# Fresh startup fixture\n")
        self.assertEqual((self.repo / "data/approved.txt").read_bytes(), approved)
        self.assertEqual(self.protected(), before_protected)

    def test_repeat_startup_without_upstream_changes_is_idempotent(self):
        self.upstream()
        self.sync()
        before, commit = self.tree(self.repo), self.head()
        result = self.sync()
        self.assertEqual(result["status"], "up_to_date")
        self.assertEqual(result["before_commit"], commit)
        self.assertEqual(result["after_commit"], commit)
        self.assertEqual(self.tree(self.repo), before)

    def test_dirty_tracked_file_is_not_overwritten(self):
        self.upstream()
        self.write(self.repo, "deployment/start_codespace.py", "# Local tracked work must survive\n")
        self.assert_sync_rejected_without_file_loss("GIT_DIRTY")

    def test_staged_tracked_change_is_not_autostashed_or_overwritten(self):
        self.upstream()
        self.write(self.repo, "README.md", "Local staged notes\n")
        self.git(self.repo, "add", "README.md")
        self.assert_sync_rejected_without_file_loss("GIT_DIRTY")
        self.assertEqual(self.git(self.repo, "diff", "--cached", "--name-only"), "README.md")

    def test_diverged_main_history_and_local_commit_are_preserved(self):
        self.write(self.repo, "local_notes.md", "Local committed work\n")
        local = self.commit(self.repo, "local fixture commit")
        self.upstream()
        self.assert_sync_rejected_without_file_loss("GIT_DIVERGED")
        self.assertEqual(self.head(), local)
        self.assertEqual((self.repo / "local_notes.md").read_text(), "Local committed work\n")

    def test_local_ahead_commits_are_never_replaced(self):
        self.write(self.repo, "local_notes.md", "Local-only commit\n")
        local = self.commit(self.repo, "local-only fixture commit")
        before = self.tree(self.repo)
        self.assert_sync_rejected_without_file_loss("GIT_DIVERGED")
        self.assertEqual(self.head(), local)
        self.assertEqual(self.tree(self.repo), before)

    def test_detached_head_is_not_moved(self):
        self.upstream()
        self.git(self.repo, "checkout", "--detach", self.original_commit)
        self.assert_sync_rejected_without_file_loss("GIT_DETACHED")

    def test_attached_nonmain_branch_is_not_moved_or_switched(self):
        self.upstream()
        self.git(self.repo, "checkout", "-b", "preserved-local-branch")
        self.assert_sync_rejected_without_file_loss("GIT_BRANCH")
        self.assertEqual(self.git(self.repo, "symbolic-ref", "--short", "HEAD"),
                         "preserved-local-branch")

    def test_untracked_added_target_collision_is_preserved(self):
        self.write(self.repo, "new_asset.bin", b"LOCAL_UNTRACKED_ASSET")
        self.upstream("new_asset.bin", b"UPSTREAM_NEW_ASSET")
        self.assert_sync_rejected_without_file_loss("GIT_LOCAL_COLLISION")

    def test_ignored_added_target_collision_is_blocked_before_merge(self):
        self.write(self.repo, "projects/new_master.mp4", b"LOCAL_IGNORED_MASTER")
        self.upstream("projects/new_master.mp4", b"UPSTREAM_IGNORED_TARGET", force=True)
        self.assert_sync_rejected_without_file_loss("GIT_LOCAL_COLLISION")

    def test_ignored_directory_to_file_collision_preserves_nested_outputs(self):
        self.write(self.repo, "projects/preserved/session/final.mp4", b"LOCAL_NESTED_FINAL")
        self.upstream("projects/preserved", b"UPSTREAM_FILE_COLLIDES_WITH_DIRECTORY", force=True)
        self.assert_sync_rejected_without_file_loss("GIT_LOCAL_COLLISION")

    def test_symlink_ancestor_added_target_never_writes_outside_checkout(self):
        outside = self.root / "outside-preserved"
        outside.mkdir()
        (outside / "original.bin").write_bytes(b"EXTERNAL_FIXTURE_DATA")
        (self.repo / "assets").mkdir()
        (self.repo / "assets/linked").symlink_to(outside, target_is_directory=True)
        self.upstream("assets/linked/new.bin", b"UPSTREAM_NEW_ASSET")
        outside_before = self.tree(outside)
        self.assert_sync_rejected_without_file_loss("GIT_LOCAL_COLLISION")
        self.assertEqual(self.tree(outside), outside_before)
        self.assertFalse((outside / "new.bin").exists())

    def test_fetch_failure_does_not_modify_checkout_or_existing_outputs(self):
        self.remote.rename(self.root / "remote-unavailable.git")
        self.assert_sync_rejected_without_file_loss("GIT_FETCH_FAILED")

    def test_fetch_timeout_does_not_modify_checkout_or_existing_outputs(self):
        original = subprocess.run
        calls = []
        def bounded(command, *args, **kwargs):
            if isinstance(command, (list, tuple)) and "fetch" in command:
                calls.append((list(command), kwargs))
                raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 45))
            return original(command, *args, **kwargs)
        with patch.object(autostart.subprocess, "run", side_effect=bounded):
            self.assert_sync_rejected_without_file_loss("GIT_TIMEOUT")
        self.assertEqual(len(calls), 1)
        self.assertGreater(calls[0][1]["timeout"], 0)
        self.assertLessEqual(calls[0][1]["timeout"], 45)

    def test_git_update_is_bounded_noninteractive_fast_forward_without_destructive_commands(self):
        self.upstream()
        original, calls = subprocess.run, []
        def observe(command, *args, **kwargs):
            if isinstance(command, (list, tuple)) and command and Path(str(command[0])).name == "git":
                calls.append((list(command), kwargs))
            return original(command, *args, **kwargs)
        with patch.object(autostart.subprocess, "run", side_effect=observe):
            self.sync(timeout=3)
        fetch = [entry for entry in calls if "fetch" in entry[0]]
        merge = [entry for entry in calls if "merge" in entry[0]]
        self.assertEqual(len(fetch), 1)
        self.assertEqual(len(merge), 1)
        for command, kwargs in calls:
            self.assertGreater(kwargs["timeout"], 0)
            self.assertLessEqual(kwargs["timeout"], 45)
            self.assertFalse(kwargs.get("shell", False))
            self.assertEqual(kwargs.get("env", {}).get("GIT_TERMINAL_PROMPT"), "0")
            for forbidden in ("reset", "stash", "clean", "--force", "--autostash"):
                self.assertNotIn(forbidden, command)
        self.assertIn("--ff-only", merge[0][0])
        self.assertIn("--no-autostash", merge[0][0])
        self.assertLessEqual(fetch[0][1]["timeout"], 3)
        self.assertLessEqual(merge[0][1]["timeout"], 3)
        self.assertIn("--refmap=", fetch[0][0])
        self.assertIn("--no-write-fetch-head", fetch[0][0])
        targets = [arg for arg in fetch[0][0]
                   if arg.startswith("refs/heads/main:refs/world-engine/autostart/")]
        self.assertEqual(len(targets), 1)
        for command, _ in calls:
            self.assertFalse(any("FETCH_HEAD" in arg for arg in command))

    def test_concurrent_branch_change_after_fetch_is_not_overwritten(self):
        self.upstream()
        before, commit = self.tree(self.repo), self.head()
        original, changed = subprocess.run, []
        def change_branch(command, *args, **kwargs):
            result = original(command, *args, **kwargs)
            if isinstance(command, (list, tuple)) and "fetch" in command:
                original(["git", "checkout", "-b", "concurrent-fixture-branch"],
                         cwd=self.repo, env=self.git_env, capture_output=True,
                         text=True, check=True, timeout=10)
                changed.append(True)
            return result
        with patch.object(autostart.subprocess, "run", side_effect=change_branch):
            with self.assertRaises(SecurityError) as error:
                self.sync()
        self.assertEqual(error.exception.code, "GIT_CHANGED")
        self.assertEqual(changed, [True])
        self.assertEqual(self.head(), commit)
        self.assertEqual(self.tree(self.repo), before)
        self.assertEqual(self.git(self.repo, "symbolic-ref", "--short", "HEAD"),
                         "concurrent-fixture-branch")

    def test_concurrent_fetch_head_interference_cannot_select_wrong_commit(self):
        target = self.upstream()
        self.git(self.publisher, "checkout", "-b", "side-fixture")
        self.write(self.publisher, "wrong_side_only.txt", "This side branch must not be merged\n")
        wrong = self.commit(self.publisher, "side branch fixture commit")
        self.git(self.publisher, "push", "origin", "side-fixture")
        self.git(self.repo, "fetch", "origin", "refs/heads/side-fixture:refs/remotes/origin/side-fixture")
        original, injected = subprocess.run, []
        def interfere(command, *args, **kwargs):
            result = original(command, *args, **kwargs)
            if isinstance(command, (list, tuple)) and "fetch" in command:
                (self.repo / ".git/FETCH_HEAD").write_text(wrong + "\t\tfixture concurrent fetch\n")
                injected.append(True)
            return result
        with patch.object(autostart.subprocess, "run", side_effect=interfere):
            result = self.sync()
        self.assertEqual(injected, [True])
        self.assertEqual(result["after_commit"], target)
        self.assertEqual(self.head(), target)
        self.assertFalse((self.repo / "wrong_side_only.txt").exists())

    def test_before_update_callback_runs_immediately_before_fast_forward(self):
        self.upstream()
        original, order = subprocess.run, []
        def before_update():
            self.assertEqual(self.head(), self.original_commit)
            order.append("before_update")
        def observe(command, *args, **kwargs):
            if isinstance(command, (list, tuple)) and "merge" in command:
                order.append("merge")
            return original(command, *args, **kwargs)
        with patch.object(autostart.subprocess, "run", side_effect=observe):
            self.sync(before_update=before_update)
        self.assertEqual(order, ["before_update", "merge"])

    def test_before_update_safety_failure_blocks_merge_without_file_loss(self):
        self.upstream()
        before, commit = self.tree(self.repo), self.head()
        original, merges = subprocess.run, []
        def denied():
            raise SecurityError("ACTIVE_WORKER", "Synthetic worker guard.")
        def observe(command, *args, **kwargs):
            if isinstance(command, (list, tuple)) and "merge" in command:
                merges.append(list(command))
            return original(command, *args, **kwargs)
        with patch.object(autostart.subprocess, "run", side_effect=observe):
            with self.assertRaises(SecurityError) as error:
                self.sync(before_update=denied)
        self.assertEqual(error.exception.code, "ACTIVE_WORKER")
        self.assertEqual(merges, [])
        self.assertEqual(self.head(), commit)
        self.assertEqual(self.tree(self.repo), before)


class RepositoryValidationTests(LocalGitFixture):
    def test_exact_trusted_github_repository_passes_without_fetch(self):
        before, commit = self.tree(self.repo), self.head()
        for remote in ("https://github.com/dimon3898-sys/yeonhwarok-free.git",
                       "https://github.com/dimon3898-sys/yeonhwarok-free",
                       "ssh://git@github.com/dimon3898-sys/yeonhwarok-free.git",
                       "ssh://git@github.com/dimon3898-sys/yeonhwarok-free",
                       "git@github.com:dimon3898-sys/yeonhwarok-free.git"):
            self.git(self.repo, "remote", "set-url", "origin", remote)
            with self.subTest(remote=remote):
                autostart.validate_repository(self.repo)
        self.assertEqual(self.head(), commit)
        self.assertEqual(self.tree(self.repo), before)

    def test_foreign_origin_lookalikes_and_local_remote_are_rejected(self):
        for remote in (str(self.remote), "https://github.com/other-owner/yeonhwarok-free.git",
                       "https://github.com/dimon3898-sys/other-repository.git",
                       "https://github.com.evil.invalid/dimon3898-sys/yeonhwarok-free.git",
                       "https://evil.invalid/dimon3898-sys/yeonhwarok-free.git",
                       "git@evil.invalid:dimon3898-sys/yeonhwarok-free.git",
                       "https://github.com/dimon3898-sys/yeonhwarok-free.git?ref=evil",
                       "https://github.com/dimon3898-sys/yeonhwarok-free.git#evil",
                       "ssh://git@github.com/dimon3898-sys/yeonhwarok-free.git?ref=evil"):
            self.git(self.repo, "remote", "set-url", "origin", remote)
            with self.subTest(remote=remote), self.assertRaises(SecurityError):
                autostart.validate_repository(self.repo)

    def test_no_origin_and_nonrepository_are_rejected(self):
        self.git(self.repo, "remote", "remove", "origin")
        with self.assertRaises(SecurityError):
            autostart.validate_repository(self.repo)
        plain = self.root / "not-a-repository"
        plain.mkdir()
        with self.assertRaises(SecurityError):
            autostart.validate_repository(plain)

    def test_malformed_remote_url_returns_typed_error_without_native_detail(self):
        for remote in ("https://github.com:invalid/dimon3898-sys/yeonhwarok-free.git",
                       "https://github.com:65536/dimon3898-sys/yeonhwarok-free.git",
                       "https://[github.com/dimon3898-sys/yeonhwarok-free.git"):
            self.git(self.repo, "remote", "set-url", "origin", remote)
            with self.subTest(remote=remote):
                with self.assertRaises(SecurityError) as error:
                    autostart.validate_repository(self.repo)
                self.assertEqual(error.exception.code, "AUTOSTART_WRONG_REPOSITORY")
                self.assertNotIn(remote, str(error.exception))


class AutomaticStartTests(unittest.TestCase):
    """Fresh-interpreter startup is mocked; all private state is in new fixtures."""
    def setUp(self):
        from deployment import start_codespace
        self.startup = start_codespace
        self.temp = tempfile.TemporaryDirectory(prefix="wss-autostart-launch-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "world-simulation-shorts-engine"
        self.state = self.app / "deployment/runtime/mobile"
        self.state.mkdir(parents=True)
        self.access = self.state / "owner-code.txt"
        self.code = "SYNTHETIC_OWNER_CODE_NOT_A_REAL_CREDENTIAL"
        self.access.write_text(self.code + "\n")
        self.access.chmod(0o600)
        self.args = SimpleNamespace(port=7860, internal_port=7861,
                                    state_root=self.state, refresh=False)
        self.sync_result = {"before_commit": "a" * 40, "after_commit": "b" * 40,
                            "status": "updated"}
        self.child_result = {"status": "started", "port": 7860, "pid": 123456,
                             "access_file": str(self.access)}
        def successful_sync(repo, *, before_update=None):
            if before_update is not None:
                before_update()
            return self.sync_result
        self.patches = [patch.object(autostart, "APP", self.app),
                        patch.object(autostart, "REPO", self.root),
                        patch.object(autostart, "synchronize_main", side_effect=successful_sync),
                        patch.object(self.startup, "_read_record", return_value=None),
                        patch.object(self.startup, "_owned_process", return_value=None),
                        patch.object(self.startup, "_assert_no_worker"),
                        patch.object(self.startup, "_assert_idle"),
                        patch.object(self.startup, "_healthy", return_value=True),
                        patch.object(self.startup, "_ports_free"),
                        patch.object(self.startup, "_stop_owned"),
                        patch.object(autostart.subprocess, "run", return_value=subprocess.CompletedProcess(
                            ["synthetic-child"], 0, json.dumps(self.child_result), ""))]
        self.mocks = [item.start() for item in self.patches]
        for item in self.patches:
            self.addCleanup(item.stop)
        self.sync_mock, self.child_mock = self.mocks[2], self.mocks[-1]
        self.health_mock, self.port_mock, self.stop_mock = self.mocks[7:10]

    def invoke(self):
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = autostart.automatic_start(self.args)
        return result, captured.getvalue()

    def records(self):
        return [(p.name, json.loads(p.read_text()))
                for p in self.state.rglob("*.json")]

    def assert_private_records_do_not_contain(self, value):
        self.assertNotIn(value, json.dumps(self.records()))

    def test_sync_then_fresh_interpreter_no_sync_child_bounded_and_owner_file_preserved(self):
        before = self.access.read_bytes()
        result, output = self.invoke()
        self.assertEqual(result, 0)
        self.sync_mock.assert_called_once()
        self.assertEqual(self.sync_mock.call_args.args, (self.root,))
        self.assertTrue(callable(self.sync_mock.call_args.kwargs["before_update"]))
        self.child_mock.assert_called_once()
        command = self.child_mock.call_args.args[0]
        kwargs = self.child_mock.call_args.kwargs
        self.assertEqual(command[0], autostart.sys.executable)
        self.assertEqual(command[1], str(self.app / "deployment/start_codespace.py"))
        self.assertEqual(command.count("--no-sync"), 1)
        for option, value in (("--state-root", str(self.state)), ("--port", "7860"),
                              ("--internal-port", "7861")):
            self.assertEqual(command[command.index(option) + 1], value)
        self.assertNotIn("--refresh", command)
        self.assertEqual(kwargs["cwd"], self.app)
        self.assertEqual(kwargs["timeout"], 60)
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs.get("shell", False))
        self.assertGreaterEqual(self.port_mock.call_count, 1)
        for call in self.port_mock.call_args_list:
            self.assertEqual(call.args, (self.args,))
            self.assertEqual(call.kwargs, {})
        self.assertEqual(self.access.read_bytes(), before)
        self.assertNotIn(self.code, output)
        self.assert_private_records_do_not_contain(self.code)
        report = json.loads((self.state / "startup-update.json").read_text())
        self.assertEqual(report["sync"], self.sync_result)
        self.assertTrue(report["server_ready"])
        self.assertEqual(report["new_render_requests"], 0)

    def test_refresh_flag_and_actual_parent_sync_before_child_order(self):
        order = []
        self.args.refresh = True
        def sync(repo, *, before_update=None):
            order.append("sync")
            if before_update:
                before_update()
            return self.sync_result
        self.sync_mock.side_effect = sync
        self.child_mock.side_effect = lambda *a, **k: order.append("child") or subprocess.CompletedProcess(
            a[0], 0, json.dumps(self.child_result), "")
        self.invoke()
        self.assertEqual(order, ["sync", "child"])
        self.assertEqual(self.child_mock.call_args.args[0].count("--refresh"), 1)

    def test_sync_failure_never_starts_child_and_records_only_fixed_error(self):
        self.sync_mock.side_effect = SecurityError("GIT_DIRTY", "Existing changes preserved.")
        before = self.access.read_bytes()
        captured = io.StringIO()
        with redirect_stdout(captured), self.assertRaises(SecurityError) as error:
            autostart.automatic_start(self.args)
        self.assertEqual(error.exception.code, "GIT_DIRTY")
        self.child_mock.assert_not_called()
        self.assertEqual(self.access.read_bytes(), before)
        self.assertEqual(captured.getvalue(), "")
        report = json.loads((self.state / "startup-update.json").read_text())
        self.assertFalse(report["server_ready"])
        self.assertEqual(report["error_code"], "GIT_DIRTY")

    def test_failed_child_native_logs_are_not_printed_or_recorded(self):
        private_log = "SYNTHETIC_PRIVATE_CHILD_LOG_WITH_" + self.code
        self.child_mock.return_value = subprocess.CompletedProcess(["synthetic-child"], 1,
                                                                   private_log, private_log)
        captured = io.StringIO()
        with redirect_stdout(captured), self.assertRaises(SecurityError) as error:
            autostart.automatic_start(self.args)
        self.assertEqual(error.exception.code, "SERVER_START_FAILED")
        self.assertNotIn(private_log, captured.getvalue())
        self.assertNotIn(private_log, str(error.exception))
        self.assert_private_records_do_not_contain(private_log)

    def test_child_timeout_is_finite_and_never_echoes_child_output(self):
        private_log = "SYNTHETIC_PRIVATE_TIMEOUT_" + self.code
        self.child_mock.side_effect = subprocess.TimeoutExpired(["synthetic-child"], 60,
                                                               output=private_log, stderr=private_log)
        captured = io.StringIO()
        with redirect_stdout(captured), self.assertRaises(SecurityError) as error:
            autostart.automatic_start(self.args)
        self.assertEqual(error.exception.code, "AUTOSTART_TIMEOUT")
        self.assertNotIn(private_log, captured.getvalue())
        self.assertNotIn(private_log, str(error.exception))
        self.assert_private_records_do_not_contain(private_log)

    def test_child_success_without_actual_health_does_not_claim_ready(self):
        self.health_mock.return_value = False
        with self.assertRaises(SecurityError) as error:
            self.invoke()
        self.assertEqual(error.exception.code, "SERVER_NOT_READY")
        report = json.loads((self.state / "startup-update.json").read_text())
        self.assertFalse(report["server_ready"])

    def test_non_runtime_state_root_is_rejected_before_git_or_child(self):
        self.args.state_root = self.root / "projects/protected-existing"
        with self.assertRaises(SecurityError) as error:
            self.invoke()
        self.assertEqual(error.exception.code, "UNSAFE_STATE_ROOT")
        self.sync_mock.assert_not_called()
        self.child_mock.assert_not_called()
        self.assertFalse(self.args.state_root.exists())

    def test_startup_history_symlink_is_rejected_before_git_child_or_report(self):
        outside = self.root / "private-history-outside"
        outside.mkdir()
        sentinel = outside / "preserved.json"
        sentinel.write_text('{"preserved":true}\n')
        (self.state / "startup-history").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(SecurityError):
            self.invoke()
        self.sync_mock.assert_not_called()
        self.child_mock.assert_not_called()
        self.assertEqual(sentinel.read_text(), '{"preserved":true}\n')
        self.assertEqual(list(outside.iterdir()), [sentinel])
        self.assertFalse((self.state / "startup-update.json").exists())

    def test_startup_history_nondirectory_is_preserved_and_rejected(self):
        history = self.state / "startup-history"
        history.write_bytes(b"PRESERVED_LOCAL_HISTORY_FILE")
        with self.assertRaises(SecurityError):
            self.invoke()
        self.sync_mock.assert_not_called()
        self.child_mock.assert_not_called()
        self.assertEqual(history.read_bytes(), b"PRESERVED_LOCAL_HISTORY_FILE")

    def test_idle_owned_gateway_is_stopped_before_worker_recheck_and_merge(self):
        owned, order = {"pid": 123456, "start_ticks": 456}, []
        self.mocks[3].return_value = owned["pid"]
        self.mocks[4].return_value = owned
        self.stop_mock.side_effect = lambda *a: order.append("stop_owned")
        self.mocks[5].side_effect = lambda *a: order.append("no_worker")
        def sync(repo, *, before_update):
            order.append("sync")
            before_update()
            order.append("merge")
            return self.sync_result
        self.sync_mock.side_effect = sync
        self.child_mock.side_effect = lambda *a, **k: order.append("child") or subprocess.CompletedProcess(
            a[0], 0, json.dumps(self.child_result), "")
        self.invoke()
        self.stop_mock.assert_called_once_with(owned, self.state, self.args)
        self.assertLess(order.index("stop_owned"), order.index("no_worker"))
        self.assertLess(order.index("no_worker"), order.index("merge"))
        self.assertLess(order.index("merge"), order.index("child"))

    def test_nonowned_port_guard_prevents_git_update_or_child(self):
        self.port_mock.side_effect = self.startup.StartupError("PORT_IN_USE", "Synthetic port guard.")
        merged = []
        def sync(repo, *, before_update):
            before_update()
            merged.append(True)
            return self.sync_result
        self.sync_mock.side_effect = sync
        with self.assertRaises(SecurityError) as error:
            self.invoke()
        self.assertEqual(error.exception.code, "PORT_IN_USE")
        self.port_mock.assert_called_once_with(self.args)
        self.assertEqual(merged, [])
        self.child_mock.assert_not_called()
        self.stop_mock.assert_not_called()

    def test_worker_guard_blocks_git_update_and_never_signals_nonowned_gateway(self):
        self.mocks[5].side_effect = self.startup.StartupError("ACTIVE_WORKER", "Synthetic worker guard.")
        merged = []
        def sync(repo, *, before_update):
            before_update()
            merged.append(True)
            return self.sync_result
        self.sync_mock.side_effect = sync
        with self.assertRaises(SecurityError) as error:
            self.invoke()
        self.assertEqual(error.exception.code, "ACTIVE_WORKER")
        self.assertEqual(merged, [])
        self.child_mock.assert_not_called()
        self.stop_mock.assert_not_called()


class ExistingPostStartTests(unittest.TestCase):
    def test_existing_poststart_command_is_identical_without_rebuild(self):
        path = Path(__file__).resolve().parents[2] / ".devcontainer/devcontainer.json"
        command = json.loads(path.read_text())["postStartCommand"]
        self.assertEqual(command,
                         "python3 world-simulation-shorts-engine/deployment/start_codespace.py")

    def test_automatic_sync_only_for_exact_codespaces_true_and_not_no_sync(self):
        from deployment import start_codespace as startup
        for value in ("true", "false", "TRUE", "1", ""):
            with self.subTest(environment=value), patch.dict(os.environ, {"CODESPACES": value}), \
                    patch.object(autostart, "automatic_start", return_value=0) as automatic, \
                    patch.object(startup, "_runtime_preflight", side_effect=RuntimeError("stop-before-start")):
                if value == "true":
                    self.assertEqual(startup.main([]), 0)
                    automatic.assert_called_once()
                else:
                    with self.assertRaisesRegex(RuntimeError, "stop-before-start"):
                        startup.main([])
                    automatic.assert_not_called()
        with patch.dict(os.environ, {"CODESPACES": "true"}), \
                patch.object(autostart, "automatic_start", return_value=0) as automatic, \
                patch.object(startup, "_runtime_preflight", side_effect=RuntimeError("stop-before-start")):
            with self.assertRaisesRegex(RuntimeError, "stop-before-start"):
                startup.main(["--no-sync"])
            automatic.assert_not_called()
