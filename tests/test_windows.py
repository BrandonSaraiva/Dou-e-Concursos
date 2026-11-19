"""Testes das APIs do Windows sem alterar a inicialização real do usuário."""
import subprocess
import sys
import uuid

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Usa Win32 e HKCU")


def test_single_instance_is_released_and_can_restore_window(tmp_path, monkeypatch):
    from radar_dou.windows import WindowsInstance

    monkeypatch.setenv("RADAR_DOU_HOME", str(tmp_path))
    with WindowsInstance() as first:
        assert first.primary
        subprocess.run([sys.executable, "-c", """
from radar_dou.windows import WindowsInstance
with WindowsInstance() as second:
    assert not second.primary
    second.request_window()
"""], check=True, timeout=15)
        assert first.window_requested()
        assert not first.window_requested()
    with WindowsInstance() as next_instance:
        assert next_instance.primary


def test_startup_writes_background_command_and_can_be_removed(tmp_path, monkeypatch):
    import winreg
    from radar_dou import windows

    key_path = f"Software\\RadarDOU-Test-{uuid.uuid4().hex}"
    executable = str(tmp_path / "Radar de concursos" / "RadarDOU.exe")
    monkeypatch.setattr(windows, "_RUN_KEY", key_path)
    monkeypatch.setattr(sys, "executable", executable)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path).Close()
    try:
        windows.set_start_with_windows(True)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            command, kind = winreg.QueryValueEx(key, windows._RUN_NAME)
        assert kind == winreg.REG_SZ
        assert command == f'"{executable}" --background'

        windows.set_start_with_windows(False)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            with pytest.raises(FileNotFoundError):
                winreg.QueryValueEx(key, windows._RUN_NAME)
        windows.set_start_with_windows(False)
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
