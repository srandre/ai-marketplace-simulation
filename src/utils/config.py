"""Configuration management for the game."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


class Config:
    """Singleton configuration manager."""

    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._config:
            self.load_config()

    def load_config(self, config_path: str = None) -> None:
        """Load configuration from YAML file and environment variables."""
        # Load environment variables from .env file
        project_root = Path(__file__).parent.parent.parent
        dotenv_path = project_root / ".env"
        load_dotenv(dotenv_path)

        if config_path is None:
            # Default to config/game_config.yaml
            config_path = project_root / "config" / "game_config.yaml"

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        # Override API key from environment variable if present
        api_key_env = os.getenv("DEEPSEEK_API_KEY")
        if api_key_env:
            if "ai" not in self._config:
                self._config["ai"] = {}
            self._config["ai"]["api_key"] = api_key_env

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Example: config.get('game.num_players') returns 10
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration dictionary."""
        return self._config.copy()


# Global config instance
config = Config()
