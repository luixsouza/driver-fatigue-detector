from pathlib import Path

from driver_fatigue.infrastructure.video_sources.file import FileVideoSource


class TestFileVideoSource:
    def test_reads_sequential_frames(self, test_video_path: Path):
        src = FileVideoSource(path=test_video_path)
        try:
            f0 = src.read()
            f1 = src.read()
            assert f0 is not None and f1 is not None
            assert f0.index == 0 and f1.index == 1
            assert f0.image.shape[2] == 3
        finally:
            src.release()

    def test_returns_none_at_end(self, test_video_path: Path):
        src = FileVideoSource(path=test_video_path)
        try:
            count = 0
            while True:
                f = src.read()
                if f is None:
                    break
                count += 1
                if count > 10_000:
                    break
            assert count > 0
            assert src.read() is None
        finally:
            src.release()

    def test_loop_mode_rebobina(self, test_video_path: Path):
        src = FileVideoSource(path=test_video_path, loop=True)
        try:
            first = src.read()
            assert first is not None
            for _ in range(200):
                f = src.read()
                if f is None:
                    break
            after = src.read()
            assert after is not None
        finally:
            src.release()

    def test_release_is_idempotent(self, test_video_path: Path):
        src = FileVideoSource(path=test_video_path)
        src.release()
        src.release()
