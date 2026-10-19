import json
import threading
from pathlib import Path
from typing import Any, List

DATA_DIR = Path(__file__).parent / "data"

_lock = threading.Lock()


def _load(filename: str) -> Any:
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save(filename: str, data: Any) -> None:
    with _lock:
        with open(DATA_DIR / filename, "w") as f:
            json.dump(data, f, indent=2)


def get_users() -> List[dict]:
    return _load("users.json")


def get_configs() -> List[dict]:
    return _load("notification_configs.json")


def save_configs(configs: List[dict]) -> None:
    _save("notification_configs.json", configs)


def get_notifications() -> List[dict]:
    return _load("notifications.json")


def save_notifications(notifications: List[dict]) -> None:
    _save("notifications.json", notifications)


def get_history() -> List[dict]:
    return _load("notification_history.json")


def save_history(history: List[dict]) -> None:
    _save("notification_history.json", history)


def reset_notifications() -> None:
    _save("notifications.json", [])
    _save("notification_history.json", [])
