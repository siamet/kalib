"""Configuration management for Kalib microscopy control system.

Handles loading, saving, and accessing configuration from YAML files.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from copy import deepcopy


class Settings:
    """Configuration settings manager.

    Loads configuration from YAML files and provides
    convenient access to settings.
    """

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize settings.

        Args:
            config_dict: Configuration dictionary (if None, uses empty dict)
        """
        self._config = config_dict or {}

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated path.

        Args:
            key_path: Dot-separated path (e.g., 'camera.exposure_time_min')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            exposure = settings.get('camera.default_exposure', 15000)
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any) -> None:
        """Set configuration value by dot-separated path.

        Args:
            key_path: Dot-separated path (e.g., 'camera.default_exposure')
            value: Value to set

        Example:
            settings.set('camera.default_exposure', 20000)
        """
        keys = key_path.split('.')
        config = self._config

        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the value
        config[keys[-1]] = value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section.

        Args:
            section: Section name (e.g., 'camera', 'stages')

        Returns:
            Dictionary of section configuration

        Example:
            camera_config = settings.get_section('camera')
        """
        return deepcopy(self._config.get(section, {}))

    def update(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration with new values.

        Args:
            config_dict: Dictionary of configuration values
        """
        self._deep_update(self._config, config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Get entire configuration as dictionary.

        Returns:
            Copy of configuration dictionary
        """
        return deepcopy(self._config)

    @staticmethod
    def _deep_update(base: Dict, update: Dict) -> None:
        """Deep update dictionary (modifies base in-place).

        Args:
            base: Base dictionary to update
            update: Dictionary with updates
        """
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                Settings._deep_update(base[key], value)
            else:
                base[key] = deepcopy(value)


def load_config(
    config_path: Optional[str] = None,
    default_path: Optional[str] = None
) -> Settings:
    """Load configuration from YAML file.

    Args:
        config_path: Path to user configuration file
        default_path: Path to default configuration file

    Returns:
        Settings instance with loaded configuration

    Raises:
        FileNotFoundError: If default config not found and no user config provided
        yaml.YAMLError: If YAML parsing fails

    Example:
        settings = load_config('config/config.yaml', 'config/default_config.yaml')
    """
    # Determine paths
    if default_path is None:
        config_dir = Path(__file__).parent
        default_path = config_dir / 'default_config.yaml'

    if config_path is None:
        config_dir = Path(__file__).parent
        config_path = config_dir / 'config.yaml'

    # Load default configuration
    default_config = {}
    if Path(default_path).exists():
        with open(default_path, 'r') as f:
            default_config = yaml.safe_load(f) or {}
    else:
        raise FileNotFoundError(f"Default configuration not found: {default_path}")

    # Load user configuration (if exists)
    user_config = {}
    if Path(config_path).exists():
        with open(config_path, 'r') as f:
            user_config = yaml.safe_load(f) or {}

    # Merge configurations (user overrides default)
    settings = Settings(default_config)
    if user_config:
        settings.update(user_config)

    return settings


def save_config(settings: Settings, config_path: str) -> None:
    """Save configuration to YAML file.

    Args:
        settings: Settings instance to save
        config_path: Path to save configuration file

    Raises:
        OSError: If file cannot be written

    Example:
        save_config(settings, 'config/config.yaml')
    """
    config_file = Path(config_path)
    config_file.parent.mkdir(parents=True, exist_ok=True)

    with open(config_file, 'w') as f:
        yaml.safe_dump(
            settings.to_dict(),
            f,
            default_flow_style=False,
            sort_keys=False
        )


def create_default_config(output_path: str) -> None:
    """Create a default configuration file.

    Args:
        output_path: Path to create configuration file

    Example:
        create_default_config('config/config.yaml')
    """
    default_path = Path(__file__).parent / 'default_config.yaml'

    if not default_path.exists():
        raise FileNotFoundError(f"Default configuration not found: {default_path}")

    # Copy default to output path
    with open(default_path, 'r') as src:
        content = src.read()

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as dst:
        dst.write(content)


# Convenience function to load default settings
def get_default_settings() -> Settings:
    """Load default settings without user overrides.

    Returns:
        Settings instance with default configuration
    """
    default_path = Path(__file__).parent / 'default_config.yaml'
    return load_config(default_path=str(default_path), config_path=None)
