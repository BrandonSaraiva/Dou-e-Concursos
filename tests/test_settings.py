import json
import os
import pytest
from radar_dou.settings import AppConfig, config_file, load_settings, save_settings

FAKE_TOKEN = "123456789:THIS_IS_A_DEMONSTRATION_TOKEN_ONLY"


def test_settings_survive_restarts(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_DOU_HOME", str(tmp_path))
    expected = AppConfig("  Maria   Silva ", 123456789, FAKE_TOKEN, 60).validated()
    assert expected.name == "Maria Silva"
    save_settings(expected)
    assert load_settings() == expected
    assert config_file().parent == tmp_path
    raw = json.loads(config_file().read_text("utf-8"))
    assert raw["version"] == 3
    assert "protected_token" in raw
    assert "token" not in raw
    if os.name == "nt":
        assert FAKE_TOKEN not in config_file().read_text("utf-8")


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
