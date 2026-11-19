"""Intercâmbio local de estado entre a tela Kivy e o serviço Android.

Nenhuma credencial é transportada por arquivo de comando ou log.
O Android armazena dados em getFilesDir() no sandbox do aplicativo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time


PACKAGE = "org.radardou.monitor"
SERVICE_CLASS = PACKAGE + ".ServiceRadar"


def setup_android_home(for_service: bool = False) -> Path:
    """Mesmo diretório privado para o processo da interface e o serviço."""
    from jnius import autoclass
    klass = "org.kivy.android.PythonService" if for_service else "org.kivy.android.PythonActivity"
    obj = autoclass(klass)
    context = obj.mService if for_service else obj.mActivity
    if context is None:
        raise RuntimeError("Contexto Android indisponível")
    path = Path(str(context.getFilesDir().getAbsolutePath())) / "RadarDOU"
    path.mkdir(parents=True, exist_ok=True)
    os.environ["RADAR_DOU_HOME"] = str(path)
    return path


def _atomic_json(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def desired_file(root: Path) -> Path:
    return root / "monitor.json"


def heartbeat_file(root: Path) -> Path:
    return root / "heartbeat.json"


def check_file(root: Path) -> Path:
    return root / "manual-check.request"


def set_enabled(root: Path, enabled: bool) -> None:
    _atomic_json(desired_file(root), {"enabled": bool(enabled)})


def is_enabled(root: Path) -> bool:
    try:
        return json.loads(desired_file(root).read_text(encoding="utf-8"))["enabled"] is True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def request_check(root: Path) -> None:
    _atomic_json(check_file(root), {"requested_at": time.time()})


def take_check_request(root: Path) -> bool:
    try:
        check_file(root).unlink()
        return True
    except FileNotFoundError:
        return False


def write_heartbeat(root: Path, active: bool = True) -> None:
    _atomic_json(heartbeat_file(root), {"ts": time.time(), "pid": os.getpid(), "active": active})


def is_alive(root: Path, max_age: float = 15.0) -> bool:
    try:
        item = json.loads(heartbeat_file(root).read_text(encoding="utf-8"))
        return item.get("active") is True and 0 <= time.time() - float(item["ts"]) < max_age
    except (OSError, ValueError, KeyError, TypeError):
        return False
