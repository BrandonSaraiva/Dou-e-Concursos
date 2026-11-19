from pathlib import Path
import time

from radar_dou.android_runtime import (
    set_enabled, is_enabled, request_check, take_check_request,
    write_heartbeat, is_alive,
)


def test_android_service_control_survives_restart(tmp_path: Path):
    assert not is_enabled(tmp_path)
    set_enabled(tmp_path, True)
    assert is_enabled(tmp_path)
    set_enabled(tmp_path, False)
    assert not is_enabled(tmp_path)


def test_manual_check_consumed_once(tmp_path: Path):
    assert not take_check_request(tmp_path)
    request_check(tmp_path)
    assert take_check_request(tmp_path)
    assert not take_check_request(tmp_path)


def test_heartbeat_detects_worker_state(tmp_path: Path):
    assert not is_alive(tmp_path)
    write_heartbeat(tmp_path)
    assert is_alive(tmp_path)
    write_heartbeat(tmp_path, False)
    assert not is_alive(tmp_path)
