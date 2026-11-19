"""Preferências persistentes fora do repositório e do diretório do executável.

No Windows, o token é criptografado com DPAPI do usuário atual.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import re
import sys
import tempfile

TOKEN_PATTERN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{20,}$")


def data_dir() -> Path:
    override = os.environ.get("RADAR_DOU_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "RadarDOU"


def config_file() -> Path:
    return data_dir() / "config.json"


def database_file() -> Path:
    return data_dir() / "radar.sqlite3"


def log_file() -> Path:
    return data_dir() / "radar.log"


@dataclass(frozen=True)
class AppConfig:
    name: str = field(repr=False)
    telegram_id: int = field(repr=False)
    token: str = field(repr=False)
    interval_minutes: int = 60
    uf: str = ""  # vazio = apenas nacionais
    monitor_dou: bool = True
    monitor_concursos: bool = True
    start_with_windows: bool = False

    def validated(self) -> "AppConfig":
        if not all(isinstance(value, str) for value in (self.name, self.uf, self.token)):
            raise ValueError("Preencha corretamente o nome, a UF e o token")
        name = " ".join(self.name.split())
        if self.monitor_dou and (len(name) < 3 or len(name) > 180):
            raise ValueError("O nome deve ter entre 3 e 180 caracteres se o DOU estiver ativo")
        if not all(isinstance(value, bool) for value in
                   (self.monitor_dou, self.monitor_concursos, self.start_with_windows)):
            raise ValueError("Marque corretamente as preferências do radar")
        if not (self.monitor_dou or self.monitor_concursos):
            raise ValueError("Ative o DOU, os concursos ou ambos")
        from .concursos import UF_NAMES
        uf = self.uf.strip().upper()
        if uf and uf not in UF_NAMES:
            raise ValueError("Selecione uma UF brasileira válida")
        if type(self.telegram_id) is not int or self.telegram_id <= 0:
            raise ValueError("O ID da sua conta do Telegram deve ser um número positivo")
        if not TOKEN_PATTERN.fullmatch(self.token.strip()):
            raise ValueError("Token inválido. Copie o token completo do @BotFather, incluindo os dois-pontos")
        if type(self.interval_minutes) is not int or not 15 <= self.interval_minutes <= 1440:
            raise ValueError("Intervalo permitido: de 15 a 1440 minutos")
        return replace(self, name=name, token=self.token.strip(), uf=uf)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _protect = _crypt32.CryptProtectData
    _unprotect = _crypt32.CryptUnprotectData
    _blob_pointer = ctypes.POINTER(_Blob)
    _common_dpapi_args = [_blob_pointer, ctypes.c_void_p, ctypes.c_void_p,
                          wintypes.DWORD, _blob_pointer]
    _protect.argtypes = [_blob_pointer, wintypes.LPCWSTR, *_common_dpapi_args]
    _unprotect.argtypes = [_blob_pointer, ctypes.POINTER(wintypes.LPWSTR), *_common_dpapi_args]
    _protect.restype = _unprotect.restype = wintypes.BOOL
    _local_free = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
    _local_free.argtypes = [ctypes.c_void_p]
    _local_free.restype = ctypes.c_void_p
    _CRYPTPROTECT_UI_FORBIDDEN = 1

    def _dpapi(data: bytes, encrypt: bool) -> bytes:
        # O Windows cifra/desfaz a cifra com as credenciais do usuário logado.
        source = ctypes.create_string_buffer(data)
        source_blob = _Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
        target_blob = _Blob()
        func = _protect if encrypt else _unprotect
        ok = func(ctypes.byref(source_blob), None, None, None, None,
                  _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(target_blob))
        if not ok:
            raise OSError("O Windows não conseguiu proteger/desproteger o token deste usuário")
        try:
            return ctypes.string_at(target_blob.pbData, target_blob.cbData)
        finally:
            _local_free(target_blob.pbData)


def protect_token(token: str) -> tuple[str, str]:
    if sys.platform == "win32":
        return "dpapi", base64.b64encode(_dpapi(token.encode("utf-8"), True)).decode("ascii")
    # Outros sistemas: permissões 0600 para a conta do usuário.
    return "user-file", token


def unprotect_token(method: str, protected: str) -> str:
    if method == "dpapi" and sys.platform == "win32":
        return _dpapi(base64.b64decode(protected, validate=True), False).decode("utf-8")
    if method == "user-file" and sys.platform != "win32":
        return protected
    raise ValueError("O token foi salvo em outro sistema operacional/usuário. Configure-o novamente")


def save_settings(config: AppConfig) -> Path:
    value = config.validated()
    dest = config_file()
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    method, encrypted = protect_token(value.token)
    record = {
        "version": 3, "name": value.name, "telegram_id": value.telegram_id,
        "interval_minutes": value.interval_minutes,
        "uf": value.uf, "monitor_dou": value.monitor_dou,
        "monitor_concursos": value.monitor_concursos,
        "start_with_windows": value.start_with_windows,
        "token_method": method, "protected_token": encrypted,
    }
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=dest.parent,
            prefix=".config-", suffix=".tmp", delete=False,
        ) as file:
            tmp = Path(file.name)
            json.dump(record, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        tmp.replace(dest)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return dest


def load_settings() -> AppConfig | None:
    file = config_file()
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (ValueError, OSError):
        raise ValueError("Não foi possível ler a configuração local") from None
    try:
        if not isinstance(data, dict) or data.get("version") not in (2, 3):
            raise ValueError("Formato de configuração desconhecido")
        config = AppConfig(
            name=data["name"], telegram_id=int(data["telegram_id"]),
            token=unprotect_token(data["token_method"], data["protected_token"]),
            interval_minutes=int(data.get("interval_minutes", 60)),
            uf=data.get("uf", ""),
            monitor_dou=data.get("monitor_dou", True),
            monitor_concursos=data.get("monitor_concursos", True),
            start_with_windows=data.get("start_with_windows", False),
        )
        return config.validated()
    except (KeyError, TypeError, ValueError, OSError):
        raise ValueError("Não foi possível ler a configuração local. Confira os dados e salve novamente se necessário.") from None
