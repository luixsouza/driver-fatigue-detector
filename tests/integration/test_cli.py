import subprocess
import sys


class TestCli:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "run" in result.stdout or "--source" in result.stdout

    def test_invalid_source_kind_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "run",
             "--source", "banana:0", "--headless"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0

    def test_file_source_accepted_in_parser(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "run", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "--source" in result.stdout
        assert "--sinks" in result.stdout
        assert "--record" in result.stdout
