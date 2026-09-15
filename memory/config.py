"""Centralized user configuration management for Free Coding Agent."""

import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

DEFAULT_CONFIG_DIR = Path.home() / ".free-coding-agent"
CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_MODEL = "openrouter/free"


class ConfigManager:
    """Manages global user configuration in ~/.free-coding-agent/config.json."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure config directory exists with appropriate permissions."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        """Load configuration dictionary from disk."""
        if not self.config_file.exists():
            return {}
        try:
            return json.loads(self.config_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, data: dict[str, Any]) -> None:
        """Save configuration dictionary to disk."""
        self._ensure_dir()
        temp_file = self.config_dir / "config.json.tmp"
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Set owner-only permissions on POSIX systems
        if sys.platform != "win32":
            try:
                os.chmod(temp_file, 0o600)
            except Exception:
                pass

        temp_file.replace(self.config_file)

    def get_api_key(self) -> str | None:
        """Retrieve OpenRouter API key.

        Priority:
        1. OPENROUTER_API_KEY environment variable.
        2. Global configuration file (~/.free-coding-agent/config.json).
        """
        env_key = os.environ.get("OPENROUTER_API_KEY")
        if env_key and env_key.strip():
            return env_key.strip()

        data = self.load()
        file_key = data.get("openrouter_api_key")
        if file_key and str(file_key).strip():
            return str(file_key).strip()

        return None

    def set_api_key(self, api_key: str) -> None:
        """Persist API key to the global configuration file."""
        data = self.load()
        data["openrouter_api_key"] = api_key.strip()
        self.save(data)

    def get_default_model(self) -> str:
        """Retrieve default model from configuration or fallback to openrouter/free."""
        data = self.load()
        return data.get("default_model", DEFAULT_MODEL)

    def set_default_model(self, model: str) -> None:
        """Persist default model to global configuration."""
        data = self.load()
        data["default_model"] = model.strip()
        self.save(data)
