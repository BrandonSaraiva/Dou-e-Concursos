import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import pytest
from radar_dou.settings import AppConfig, config_file, load_settings, save_settings

FAKE_TOKEN = "123456789:THIS_IS_A_DEMONSTRATION_TOKEN_ONLY"


def test_settings_survive_restarts(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_DOU_HOME", str(tmp_path))
    expected = AppConfig("  Maria   Silva ", 123456789, FAKE_TOKEN, 60,
                         "rj", False, True, True).validated()
    assert expected.name == "Maria Silva"
    save_settings(expected)
    assert load_settings() == expected
    assert config_file().parent == tmp_path
    raw = json.loads(config_file().read_text("utf-8"))
    assert raw["version"] == 3
    assert "protected_token" in raw
    assert "token" not in raw
    if os.name == "nt":
        assert raw["token_method"] == "dpapi"
        assert FAKE_TOKEN not in config_file().read_text("utf-8")
    else:
        assert stat.S_IMODE(config_file().stat().st_mode) == 0o600
    assert FAKE_TOKEN not in repr(expected)
    assert str(expected.telegram_id) not in repr(expected)
    assert expected.name not in repr(expected)

    subprocess.run(
        [sys.executable, "-c",
         "from radar_dou.settings import load_settings;"
         "c = load_settings(); assert c and c.start_with_windows and c.uf == 'RJ'"],
        check=True, cwd=Path(__file__).resolve().parents[1],
    )


def test_invalid_token_and_telegram_id():
    with pytest.raises(ValueError, match="Token inválido"):
        AppConfig("Maria Silva", 123, "12345").validated()
    with pytest.raises(ValueError, match="número positivo"):
        AppConfig("Maria Silva", -1, FAKE_TOKEN).validated()


def test_corrupted_config_is_not_silently_reset(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_DOU_HOME", str(tmp_path))
    config_file().write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="configuração local"):
        load_settings()


def test_existing_version_two_config_without_preferences_loads(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_DOU_HOME", str(tmp_path))
    expected = AppConfig("Maria Silva", 123456789, FAKE_TOKEN)
    path = save_settings(expected)
    original = json.loads(path.read_text("utf-8"))
    legacy = {key: original[key] for key in ("name", "telegram_id", "token_method", "protected_token")}
    path.write_text(json.dumps({"version": 2, **legacy}), encoding="utf-8")
    assert load_settings() == expected


def test_failed_replacement_preserves_existing_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_DOU_HOME", str(tmp_path))
    expected = AppConfig("Maria Silva", 123456789, FAKE_TOKEN)
    save_settings(expected)

    def fail_replace(*args):
        raise PermissionError("arquivo em uso")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(PermissionError):
        save_settings(AppConfig("Outro Nome", 123456789, FAKE_TOKEN))
    assert load_settings() == expected
    assert list(tmp_path.iterdir()) == [config_file()]
