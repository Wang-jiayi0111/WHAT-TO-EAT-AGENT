import os
import yaml
from typing import Any, Dict

class Settings:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.config = self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from a YAML file and override with environment variables."""
        with open(self.config_file, 'r') as file:
            config = yaml.safe_load(file)

        # Override with environment variables
        for key, value in os.environ.items():
            if key in config:
                config[key] = value

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with an optional default."""
        return self.config.get(key, default)