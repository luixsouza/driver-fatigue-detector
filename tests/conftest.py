"""Fixtures compartilhados de pytest."""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"


@pytest.fixture(scope="session")
def test_video_path() -> Path:
    path = ASSETS_DIR / "test_sonolency.mp4"
    if not path.exists():
        pytest.skip(f"Vídeo de teste não encontrado: {path}")
    return path
