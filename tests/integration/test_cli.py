import subprocess
import sys

import pytest


class TestCli:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "--source" in result.stdout or "run" in result.stdout

    def test_invalid_source_kind_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "run",
             "--source", "banana:0", "--headless"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0
