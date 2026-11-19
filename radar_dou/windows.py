"""Integração do desktop com a sessão do Windows."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import threading
import winreg

from .settings import data_dir

_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
_KERNEL32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_KERNEL32.CreateMutexW.restype = wintypes.HANDLE
_KERNEL32.CreateEventW.argtypes = [
    wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR,
]
_KERNEL32.CreateEventW.restype = wintypes.HANDLE
_KERNEL32.SetEvent.argtypes = [wintypes.HANDLE]
_KERNEL32.SetEvent.restype = wintypes.BOOL
_KERNEL32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_KERNEL32.WaitForSingleObject.restype = wintypes.DWORD
_KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
_KERNEL32.CloseHandle.restype = wintypes.BOOL

_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "RadarDOU"


class WindowsInstance:
    """Uma instância por pasta de dados na sessão, com sinal para reabrir a janela."""

    def __enter__(self) -> WindowsInstance:
        identity = hashlib.sha256(os.path.normcase(str(data_dir())).encode()).hexdigest()
        name = f"Local\\RadarDOU-{identity}"
        self._show = _KERNEL32.CreateEventW(None, False, False, name + "-show")
        if not self._show:
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.set_last_error(0)
        self._mutex = _KERNEL32.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not self._mutex:
            _KERNEL32.CloseHandle(self._show)
            raise ctypes.WinError(error)
        self.primary = error != _ERROR_ALREADY_EXISTS
        return self

    def request_window(self) -> None:
        if not _KERNEL32.SetEvent(self._show):
            raise ctypes.WinError(ctypes.get_last_error())

    def window_requested(self) -> bool:
        return _KERNEL32.WaitForSingleObject(self._show, 0) == _WAIT_OBJECT_0

    def __exit__(self, *_exc):
        _KERNEL32.CloseHandle(self._mutex)
        _KERNEL32.CloseHandle(self._show)


def set_start_with_windows(enabled: bool) -> None:
    """Atualiza apenas a entrada deste aplicativo na conta atual."""
    if enabled:
        executable = Path(sys.executable).resolve()
        command = [str(executable), "--background"]
        if not getattr(sys, "frozen", False):
            windowless = executable.with_name("pythonw.exe")
            if windowless.is_file():
                command[0] = str(windowless)
            command.insert(1, str(Path(__file__).resolve().parent.parent / "main.py"))
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _RUN_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, _RUN_NAME)
        except FileNotFoundError:
            pass


class WindowsTray:
    """Publica comandos da bandeja na fila da interface, sem chamar Tkinter."""

    def __init__(self, post):
        from PIL import Image, ImageDraw
        from pystray import Menu, MenuItem
        from pystray._win32 import Icon

        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((3, 3, 60, 60), fill="#192335", outline="#38d5ca", width=6)
        draw.ellipse((24, 24, 39, 39), fill="#38d5ca")
        self._post = post
        self._icon = Icon("RadarDOU", image, "Radar DOU + Concursos", Menu(
            MenuItem("Abrir Radar DOU", self._open, default=True),
            MenuItem("Sair do Radar DOU", self._quit),
        ))
        self._thread = threading.Thread(target=self._run, name="radar-bandeja", daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self._icon.run(setup=self._show)
        except Exception:
            # O aplicativo continua acessível pela janela se a bandeja falhar.
            pass
        finally:
            self._post("tray_unavailable")

    def _show(self, icon):
        try:
            icon.visible = True
        except Exception:
            icon.stop()
        else:
            self._post("tray_ready")

    def _open(self, _icon, _item):
        self._post("tray_open")

    def _quit(self, _icon, _item):
        self._post("tray_quit")

    def close(self) -> None:
        self._icon.stop()
        self._thread.join(timeout=2)
