"""Bootstrap preservation and scope boundaries; no render or provider call."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from deployment.gcube.start import (BootError, configure_image_paths, integer_option,
                                     link_image_path, seed_audio)


class BootstrapTests(unittest.TestCase):
    def test_initial_limit_is20_and_invalid_values_cannot_expand_it_accidentally(self):
        self.assertEqual(integer_option({}, 'WORLD_ENGINE_MAX_DURATION', 20, 5, 180), 20)
        for value in ('NaN', '20.0', '-1', '181', '20;echo'):
            with self.subTest(value=value), self.assertRaises(BootError):
                integer_option({'WORLD_ENGINE_MAX_DURATION': value}, 'WORLD_ENGINE_MAX_DURATION', 20, 5, 180)

    def test_library_copy_is_repeatable_but_conflicts_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);source = root/'src';destination = root/'dst'
            source.mkdir();(source/'pulse.wav').write_bytes(b'approved-original')
            seed_audio(source,destination);seed_audio(source,destination)
            (destination/'pulse.wav').write_bytes(b'prior-user-file')
            with self.assertRaisesRegex(BootError,'PERSISTED_AUDIO_CONFLICT'):
                seed_audio(source,destination)
            self.assertEqual((destination/'pulse.wav').read_bytes(),b'prior-user-file')

    def test_library_parent_symlink_cannot_write_outside_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'src';destination=root/'dst';outside=root/'other'
            (source/'sfx').mkdir(parents=True);destination.mkdir();outside.mkdir()
            (source/'sfx/pulse.wav').write_bytes(b'approved')
            (destination/'sfx').symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(BootError,'UNSAFE_PERSISTED_AUDIO'):
                seed_audio(source,destination)
            self.assertFalse((outside/'pulse.wav').exists())

    def test_writable_link_never_deletes_nonempty_prior_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'cache';target=root/'persisted'
            source.mkdir();target.mkdir();(source/'old.mp4').write_bytes(b'keep')
            with self.assertRaisesRegex(BootError,'IMAGE_WRITABLE_PATH_NOT_EMPTY'):
                link_image_path(source,target)
            self.assertEqual((source/'old.mp4').read_bytes(),b'keep')

    def test_namespace_and_audio_links_are_separate_from_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=root/'image';cache=root/'persisted-cache';audio=root/'persisted-audio'
            (app/'cache').mkdir(parents=True);(app/'assets/audio').mkdir(parents=True)
            (app/'assets/audio/license.json').write_bytes(b'approved');cache.mkdir();audio.mkdir()
            storage=SimpleNamespace(cache_root=cache,audio_root=audio)
            with self.assertRaisesRegex(BootError,'INVALID_RENDER_PROFILE'):
                configure_image_paths(app,storage,'gpu-'+('../'*21)+'x')
            namespace='gpu-'+'a'*64
            selected=configure_image_paths(app,storage,namespace)
            self.assertEqual((app/'cache').resolve(),selected.resolve())
            self.assertEqual((app/'assets/audio').resolve(),audio)
            self.assertEqual((app/'assets/image_audio_seed/license.json').read_bytes(),b'approved')
            self.assertFalse((audio/'license.json').exists())
            seed_audio(app/'assets/image_audio_seed', audio)
            self.assertEqual((audio/'license.json').read_bytes(),b'approved')

    def test_persisted_namespace_symlink_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=root/'image';cache=root/'cache';audio=root/'audio';outside=root/'outside'
            app.mkdir();cache.mkdir();audio.mkdir();outside.mkdir()
            namespace='gpu-'+'b'*64
            (cache/namespace).symlink_to(outside,target_is_directory=True)
            before=outside.stat()
            with self.assertRaisesRegex(BootError,'UNSAFE_PERSISTED_CACHE'):
                configure_image_paths(app,SimpleNamespace(cache_root=cache,audio_root=audio),namespace)
            self.assertEqual(outside.stat().st_uid,before.st_uid)
            self.assertFalse((app/'cache').exists())


if __name__=='__main__':
    unittest.main()
