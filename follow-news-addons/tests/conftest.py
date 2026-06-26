import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def official():
    """The hyphenated fetch-competitor-official.py loaded as a module."""
    return _load("fetch_competitor_official", "fetch-competitor-official.py")


@pytest.fixture(scope="session")
def kol():
    """The hyphenated fetch-competitor-kol.py loaded as a module."""
    return _load("fetch_competitor_kol", "fetch-competitor-kol.py")


@pytest.fixture(scope="session")
def tagging():
    import competitor_tagging
    return competitor_tagging


@pytest.fixture(scope="session")
def topic():
    """The hyphenated topic-feedback.py loaded as a module."""
    return _load("topic_feedback", "topic-feedback.py")


@pytest.fixture
def sample_profiles():
    return [
        {"name": "通义灵码", "aliases": ["通义灵码", "Lingma"], "category": "coding",
         "enabled": True, "official_sources": {}},
        {"name": "Kimi", "aliases": ["Kimi", "月之暗面"], "category": "general_agent",
         "enabled": True, "official_sources": {}},
    ]
