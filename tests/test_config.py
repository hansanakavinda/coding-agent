"""Unit tests for ConfigManager and global configuration resolution."""

import os
from pathlib import Path
import pytest

from memory.config import ConfigManager


def test_config_save_and_load_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies saving and retrieving API key from config.json without env var."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cm = ConfigManager(config_dir=tmp_path)

    assert cm.get_api_key() is None

    cm.set_api_key("sk-or-v1-custom123")
    assert cm.get_api_key() == "sk-or-v1-custom123"

    # Verify persisted to file
    data = cm.load()
    assert data.get("openrouter_api_key") == "sk-or-v1-custom123"


def test_env_var_overrides_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that OPENROUTER_API_KEY env var takes precedence over config.json."""
    cm = ConfigManager(config_dir=tmp_path)
    cm.set_api_key("stored_in_file_key")

    monkeypatch.setenv("OPENROUTER_API_KEY", "override_env_key")
    assert cm.get_api_key() == "override_env_key"


def test_default_model_configuration(tmp_path: Path) -> None:
    """Verifies default model setting and fallback to openrouter/free."""
    cm = ConfigManager(config_dir=tmp_path)
    assert cm.get_default_model() == "openrouter/free"

    cm.set_default_model("meta-llama/llama-3.3-70b-instruct:free")
    assert cm.get_default_model() == "meta-llama/llama-3.3-70b-instruct:free"
