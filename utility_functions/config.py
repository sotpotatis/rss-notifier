"""config.py
Utilities related to configuration files."""

import os, toml

CONFIG_FILE_PATH = os.path.join(os.getcwd(), "config.toml")


def read_config() -> dict:
    """Reads the configuration file."""
    return toml.loads(open(CONFIG_FILE_PATH, "r", encoding="UTF-8").read())
