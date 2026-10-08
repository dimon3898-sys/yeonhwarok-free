"""Real unequal frame-count H264 concat, including lossless packet proof."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from engine.reference_concat import concat


class FrameClockConcat(unittest.TestCase):
    def test_variable_beats_preserve_every_packet_and_30fps(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);movies=[]
            for n in (64,88,93,115):
                movie=root/(str(n)+'.mp4')
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                    'testsrc2=size=160x240:rate=30','-frames:v',str(n),
                    '-c:v','libx264','-pix_fmt','yuv420p',str(movie)],check=True)
                movies.append(movie)
            target=root/'joined.mp4'
            concat(movies,target,dict(output_width=160,output_height=240,fps=30))
            report=json.loads(target.with_suffix('.frame-clock.json').read_text())
            self.assertEqual(report['frames'],360)
            self.assertEqual(report['source_frame_counts'],[64,88,93,115])
            self.assertTrue(report['packet_payloads_unchanged'])
            self.assertTrue(report['pts_sequential'])
            text=target.with_suffix('.concat.txt').read_text()
            self.assertEqual(text.count('duration '),4)
            self.assertIn('duration 2.133333333333333',text)

    def test_invalid_input_clock_is_rejected(self):
        stream=dict(codec_type='video',codec_name='h264',pix_fmt='yuv420p',width=160,height=240,
                    avg_frame_rate='30/1',time_base='1/15360',nb_frames='2')
        with tempfile.TemporaryDirectory() as folder,patch('engine.reference_concat.probe_video',return_value=dict(streams=[stream])),patch('engine.reference_concat.packet_clock',return_value=[dict(pts=0),dict(pts=513)]):
            with self.assertRaisesRegex(RuntimeError,'CONCAT_INPUT_FRAME_CLOCK_INVALID'):
                concat([Path(folder)/'scene.mp4'],Path(folder)/'joined.mp4',dict(output_width=160,output_height=240,fps=30))
