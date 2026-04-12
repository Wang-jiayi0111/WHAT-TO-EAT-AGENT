import os
import yaml
from pathlib import Path
from typing import Any, Dict

class Settings:
    def __init__(self, config_path: str = None):
        if config_path is None:
            root_dir = Path(__file__).parents[3] 
            config_path = root_dir / "config" / "setting.yaml"
        
        self._config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
                content = os.path.expandvars(content)
                self._config = yaml.safe_load(content) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with an optional default."""
        return self._config.get(key, default)