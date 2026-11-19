"""Preferências persistentes fora do repositório e do diretório do executável.

No Windows, o token é criptografado com DPAPI do usuário atual.
"""
from __future__ import annotations
import base64
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import sys

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
    name: str
    telegram_id: int
    token: str
    interval_minutes: int = 60
    uf: str = ""  # vazio = apenas nacionais
    monitor_dou: bool = True
    monitor_concursos: bool = True

    def validated(self) -> "AppConfig":
        name = " ".join(self.name.split())
        if self.monitor_dou and (len(name) < 3 or len(name) > 180):
            raise ValueError("O nome deve ter entre 3 e 180 caracteres se o DOU estiver ativo")
        if not isinstance(self.monitor_dou, bool) or not isinstance(self.monitor_concursos, bool):
            raise ValueError("Marque corretamente os serviços a monitorar")
        if not (self.monitor_dou or self.monitor_concursos):
            raise ValueError("Ative o DOU, os concursos ou ambos")
        from .concursos import UF_NAMES
        uf = self.uf.strip().upper()
        if uf and uf not in UF_NAMES:
            raise ValueError("Selecione uma UF brasileira válida")
        if not isinstance(self.telegram_id, int) or self.telegram_id <= 0:
            raise ValueError("O ID da sua conta do Telegram deve ser um número positivo")
        if not TOKEN_PATTERN.fullmatch(self.token.strip()):
            raise ValueError("Token inválido. Copie o token completo do @BotFather, incluindo os dois-pontos")
        if not 15 <= self.interval_minutes <= 1440:
            raise ValueError("Intervalo permitido: de 15 a 1440 minutos")
        return AppConfig(name, self.telegram_id, self.token.strip(), self.interval_minutes, uf, self.monitor_dou, self.monitor_concursos)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    def _dpapi(data: bytes, encrypt: bool) -> bytes:
        # O Windows cifra/desfaz a cifra com as credenciais do usuário logado.
        source = ctypes.create_string_buffer(data)
        source_blob = _Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
        target_blob = _Blob()
        crypt32 = ctypes.windll.crypt32
        func = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
        if encrypt:
            ok = func(ctypes.byref(source_blob), None, None, None, None, 0,
                      ctypes.byref(target_blob))
        else:
            ok = func(ctypes.byref(source_blob), None, None, None, None, 0,
                      ctypes.byref(target_blob))
        if not ok:
            raise OSError("O Windows não conseguiu proteger/desproteger o token deste usuário")
        try:
            return ctypes.string_at(target_blob.pbData, target_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(target_blob.pbData)


def protect_token(token: str) -> tuple[str, str]:
    if sys.platform == "win32":
        return "dpapi", base64.b64encode(_dpapi(token.encode("utf-8"), True)).decode("ascii")
    # Outros sistemas: permissões 0600 para a conta do usuário.
    return "user-file", token


def unprotect_token(method: str, protected: str) -> str:
    if method == "dpapi" and sys.platform == "win32":
        return _dpapi(base64.b64decode(protected), False).decode("utf-8")
    if method == "user-file" and sys.platform != "win32":
        return protected
    raise ValueError("O token foi salvo em outro sistema operacional/usuário. Configure-o novamente")


def save_settings(config: AppConfig) -> Path:
    value = config.validated()
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    method, encrypted = protect_token(value.token)
    record = {
        "version": 3, "name": value.name, "telegram_id": value.telegram_id,
        "interval_minutes": value.interval_minutes,
        "uf": value.uf, "monitor_dou": value.monitor_dou,
        "monitor_concursos": value.monitor_concursos,
        "token_method": method, "protected_token": encrypted,
    }
    dest = config_file()
    tmp = dest.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(dest)
    return dest


def load_settings() -> AppConfig | None:
    file = config_file()
    if not file.exists():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("version") not in (2, 3):
            raise ValueError("Formato de configuração desconhecido")
        config = AppConfig(
            name=data["name"], telegram_id=int(data["telegram_id"]),
            token=unprotect_token(data["token_method"], data["protected_token"]),
            interval_minutes=int(data.get("interval_minutes", 60)),
            uf=str(data.get("uf", "")),
            monitor_dou=data.get("monitor_dou", True),
            monitor_concursos=data.get("monitor_concursos", True),
        )
        return config.validated()
    except (KeyError, TypeError, json.JSONDecodeError, ValueError, OSError) as exc:
        raise ValueError("Não foi possível ler a configuração local: " + str(exc)) from exc
