#!/usr/bin/env python3
"""Loopback-only fake-job fixture. No real GPU, Dropbox or paid operation."""
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_server import FakeController, studio


class MobileFakeController(FakeController):
    def status(self, job_id):
        value = super().status(job_id)
        value.update(testOnly=True, actualGpuExecuted=False, uniqueStartCount=len(self.starts))
        return value

    def revise(self, job_id, revision):
        if 'camera' in revision.get('prompt', '').lower():
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            import studio_contracts
            raise studio_contracts.StudioContractError('STUDIO_VISUAL_REVISION_UNSUPPORTED',
                '시간 구간 수정은 효과음 ON/OFF·음량을 지원합니다. 카메라 수정은 검증된 새 Scene JSON이 필요합니다.',
                ['sfx.enabled', 'sfx.gain'], 422)
        result = super().revise(job_id, revision)
        result['impact'] = {'affectedSceneIds': ['scene_04', 'scene_05'], 'adjacentSceneIds': ['scene_06'],
            'audioRequestedSamples': [1200000, 1680000], 'audioChangedSampleIntervals': [[1676800, 1687200]],
            'audioImpact': {'sampleRate': 48000, 'comparison': 'CONSERVATIVE_AUTHORED_CUE_SUPPORT', 'actualPcmCompared': False},
            'requiresGpu': False}
        return result


def main():
    with tempfile.TemporaryDirectory(prefix='studio-mobile-fixture-') as folder:
        root = Path(folder)
        owner = root / 'owner'; owner.write_text(os.environ['WORLD_ENGINE_STUDIO_TEST_OWNER']); owner.chmod(0o600)
        export = root / 'export'; export.mkdir(mode=0o700)
        (export / 'proof.mp4').write_bytes(b'CPU_UI_TEST_NOT_A_REAL_VIDEO_OR_GPU_RESULT')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        config = studio.StudioConfig(root/'state', owner, origin, export, '127.0.0.1', port, True)
        app = studio.StudioApplication(config, MobileFakeController(export))
        server = studio.StudioHTTPServer(('127.0.0.1', port), studio.make_handler(app))
        def shutdown(*_): threading.Thread(target=server.shutdown, daemon=True).start()
        signal.signal(signal.SIGTERM, shutdown); signal.signal(signal.SIGINT, shutdown)
        print(json.dumps({'origin': origin, 'testOnly': True, 'gpuRenderingVerified': False}), flush=True)
        try: server.serve_forever()
        finally: server.server_close()


if __name__ == '__main__': main()
