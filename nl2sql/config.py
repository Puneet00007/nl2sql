"""
Local config storage for saved database connections and default settings.
Stored at ~/.nl2sql/config.json. Connection strings often contain
credentials -- this file is written with 0600 permissions, but treat it like
any other secrets file (don't commit it, don't share it).
"""
import json
import os
import stat
from typing import Dict, Any, Optional

CONFIG_DIR = os.path.expanduser("~/.nl2sql")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, stat.S_IRWXU)  # 0700
    except OSError:
        pass


def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return {"connections": {}, "default_model": "openai/gpt-4o-mini", "api_key": ""}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(cfg: Dict[str, Any]):
    _ensure_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass


def save_connection(name: str, connection_string: str, db_schema: Optional[str] = None):
    cfg = load_config()
    cfg.setdefault("connections", {})[name] = {
        "connection_string": connection_string,
        "db_schema": db_schema,
    }
    save_config(cfg)


def get_connection(name: str) -> Optional[Dict[str, Any]]:
    cfg = load_config()
    return cfg.get("connections", {}).get(name)


def list_connections() -> Dict[str, Any]:
    cfg = load_config()
    return cfg.get("connections", {})


def remove_connection(name: str) -> bool:
    cfg = load_config()
    if name in cfg.get("connections", {}):
        del cfg["connections"][name]
        save_config(cfg)
        return True
    return False


def set_api_key(api_key: str):
    cfg = load_config()
    cfg["api_key"] = api_key
    save_config(cfg)


def get_api_key() -> str:
    return load_config().get("api_key", "") or os.environ.get("OPENROUTER_API_KEY", "")


def set_default_model(model: str):
    cfg = load_config()
    cfg["default_model"] = model
    save_config(cfg)


def get_default_model() -> str:
    return load_config().get("default_model", "openai/gpt-4o-mini")
