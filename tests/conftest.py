"""Fixtures compartilhados de pytest."""
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def test_video_path() -> Path:
    path = FIXTURES_DIR / "test_sonolency.mp4"
    if not path.exists():
        pytest.skip(f"Vídeo de teste não encontrado: {path}")
    return path
