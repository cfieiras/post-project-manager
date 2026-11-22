"""
Configuration Manager for Post Project Manager.
Handles loading and saving global user settings, project roots, and DCC executable paths.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def get_config_file() -> Path:
    """Returns the persistent config.json path for frozen executable or dev run."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.json"
    return Path(__file__).resolve().parent.parent.parent / "config.json"


def load_app_config() -> Dict[str, Any]:
    """Loads and returns dictionary from config.json."""
    cfg_file = get_config_file()
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to read config file: {e}")
    return {}


def save_app_config(config_data: Dict[str, Any]) -> bool:
    """Saves dictionary to config.json."""
    cfg_file = get_config_file()
    try:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Warning: Failed to write config file: {e}")
        return False


def get_dcc_paths() -> Dict[str, str]:
    """Returns configured DCC executable paths dictionary."""
    config = load_app_config()
    return config.get("dcc_paths", {
        "nuke": "",
        "maya": "",
        "blender": "",
        "after_effects": "",
        "houdini": "",
        "unreal": ""
    })


def save_dcc_paths(paths: Dict[str, str]) -> bool:
    """Updates and saves DCC executable paths into config.json."""
    config = load_app_config()
    config["dcc_paths"] = paths
    return save_app_config(config)
