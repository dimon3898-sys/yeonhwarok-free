"""Device-group tests do not establish real NVIDIA/WebGL compatibility."""
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deployment.gcube.gpu_access import collect_device_groups


def node(name, gid=44, mode=stat.S_IFCHR | 0o660):
    item = SimpleNamespace(name=name)
    item.stat = lambda *, follow_symlinks: SimpleNamespace(st_mode=mode, st_gid=gid)
    return item


class Entries:
    def __init__(self, values):
        self.values = values
    def __enter__(self):
        return iter(self.values)
    def __exit__(self, *args):
        return False


class GraphicsDeviceGroups(unittest.TestCase):
    def scan(self, listing):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        (base / "nvidia-caps").mkdir()
        (base / "dri").mkdir()
        def scandir(folder):
            key = "." if Path(folder) == base else Path(folder).name
            return Entries(listing.get(key, []))
        with patch("deployment.gcube.gpu_access.os.scandir", side_effect=scandir):
            return collect_device_groups(base)

    def test_only_fixed_gpu_names_and_device_groups_are_retained(self):
        self.assertEqual(self.scan({
            ".": [node("nvidia0"), node("nvidiactl"), node("nvidia-modeset"),
                  node("nvidia-uvm", 46), node("nvidia-uvm-tools", 46)],
            "nvidia-caps": [node("nvidia-cap1", 47)],
            "dri": [node("card0", 44), node("renderD128", 109)],
        }), [44, 46, 47, 109])

    def test_root_group_regular_files_links_and_unrelated_names_are_excluded(self):
        self.assertEqual(self.scan({
            ".": [node("nvidia0", 0), node("nvidiactl", 55, stat.S_IFREG | 0o660),
                  node("nvidia1", 56, stat.S_IFLNK | 0o777), node("random", 57),
                  node("nvidia-secret", 58), node("nvidia2", 59, stat.S_IFCHR | 0o600)],
            "nvidia-caps": [node("secret", 61)],
            "dri": [node("arbitrary", 62)],
        }), [])

    def test_groups_are_deduplicated_sorted_and_no_mutation_is_performed(self):
        with patch("os.chmod") as chmod, patch("os.chown") as chown, patch("os.setgroups") as setgroups:
            self.assertEqual(self.scan({".": [node("nvidia0", 109), node("nvidia1", 44),
                                               node("nvidiactl", 109)]}), [44, 109])
            chmod.assert_not_called()
            chown.assert_not_called()
            setgroups.assert_not_called()

    def test_real_regular_gpu_named_files_do_not_grant_groups(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "nvidia0").write_text("not a GPU")
            self.assertEqual(collect_device_groups(base), [])

    def test_symlink_directory_is_not_followed(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            actual = base / "actual"
            actual.mkdir()
            (base / "dri").symlink_to(actual, target_is_directory=True)
            (base / "nvidia-caps").symlink_to(actual, target_is_directory=True)
            with patch("deployment.gcube.gpu_access.os.scandir", return_value=Entries([])) as scan:
                self.assertEqual(collect_device_groups(base), [])
                scan.assert_called_once_with(base)

    def test_missing_and_symlink_roots_are_empty_invalid_roots_rejected(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.assertEqual(collect_device_groups(base / "missing"), [])
            (base / "link").symlink_to(base, target_is_directory=True)
            self.assertEqual(collect_device_groups(base / "link"), [])
        for value in ("relative", "/dev/../etc"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "GPU_DEVICE_ROOT_INVALID"):
                collect_device_groups(value)

    def test_scan_is_bounded_and_access_failures_do_not_add_groups(self):
        listing = [node("unrelated") for _ in range(256)] + [node("nvidia0", 44)]
        self.assertEqual(self.scan({".": listing}), [])
        with TemporaryDirectory() as temporary:
            with patch("deployment.gcube.gpu_access.os.scandir", side_effect=PermissionError):
                self.assertEqual(collect_device_groups(temporary), [])


if __name__ == "__main__":
    unittest.main()
