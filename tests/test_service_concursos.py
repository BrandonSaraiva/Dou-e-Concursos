"""Teste integração do ciclo de alertas com cliente fake e Telegram fake."""
import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from radar_dou.concursos import Concurso, ConcursoSnapshot, listing_url
from radar_dou.database import Store
from radar_dou.service import RadarService
from radar_dou.settings import AppConfig



def fake_telegram(monkeypatch):
    class InlineKeyboardButton:
        def __init__(self, text, **kwargs):
            self.text = text
            self.kwargs = kwargs
    class InlineKeyboardMarkup:
        def __init__(self, inline_keyboard):
            self.inline_keyboard = inline_keyboard
    telegram = types.ModuleType("telegram")
    telegram.InlineKeyboardButton = InlineKeyboardButton
    telegram.InlineKeyboardMarkup = InlineKeyboardMarkup
    constants = types.ModuleType("telegram.constants")
    constants.ParseMode = types.SimpleNamespace(HTML="HTML")
    errors = types.ModuleType("telegram.error")
    errors.TelegramError = Exception
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.constants", constants)
    monkeypatch.setitem(sys.modules, "telegram.error", errors)

FAKE_TOKEN = "123456789:THIS_IS_A_DEMONSTRATION_TOKEN_ONLY"


def test_ciclo_concursos_nacional_e_estado_sem_alertas_repetidos(tmp_path,monkeypatch):
    fake_telegram(monkeypatch)
    first_national = Concurso("IBGE", "27.279", "Edital IBGE", "https://concursosnobrasil.com/concurso-ibge/")
    local = Concurso("Câmara DF", "10", "Edital Câmara", "https://concursosnobrasil.com/concursos/df/camara/")
    new = Concurso("IFB", "25", "Novo edital", "https://concursosnobrasil.com/concursos/df/ifb/")
    class Client:
        def __init__(self):
            self.new = False
        def fetch(self, scope):
            if scope == "BR":
                return ConcursoSnapshot("BR", (first_national,), listing_url("BR"))
            return ConcursoSnapshot("DF", (first_national, local, *((new,) if self.new else ())), listing_url("DF"))
    class FakeBot:
        def __init__(self):
            self.sent = []
        async def send_message(self, **kwargs):
            self.sent.append(kwargs)
    async def run():
        config=AppConfig("", 123, FAKE_TOKEN, 60, "DF", False, True)
        service=RadarService(config)
        service._contest_lock=asyncio.Lock()
        service._contest_client=Client()
        service._store=Store(tmp_path/"check.sqlite")
        app=SimpleNamespace(bot=FakeBot())
        try:
            first = await service._check_contests(app)
            assert "referência inicial" in " ".join(first)
            assert len(app.bot.sent)==0
            assert service._store.contest_counts(123,"BR") == (1,0)
            assert service._store.contest_counts(123,"DF") == (1,0)  # IBGE duplicado removido
            service._contest_client.new=True
            second=await service._check_contests(app)
            assert "1 novos" in " ".join(second)
            assert len(app.bot.sent)==1
            assert "IFB" in app.bot.sent[0]["text"]
            assert service._store.contest_counts(123,"DF")==(2,0)
            await service._check_contests(app)
            assert len(app.bot.sent)==1
        finally:
            service._store.close()
    asyncio.run(run())


def test_concurso_consulta_independente_falha_um_scope(tmp_path,monkeypatch):
    fake_telegram(monkeypatch)
    class Client:
        def fetch(self, scope):
            if scope=="BR":
                raise RuntimeError("Portal indisponível")
            contest=Concurso("DF", "2", "Edital", "https://concursosnobrasil.com/concursos/df/abc/")
            return ConcursoSnapshot("DF", (contest,), listing_url("DF"))
    async def run():
        svc=RadarService(AppConfig("",123,FAKE_TOKEN,60,"DF",False,True))
        svc._contest_lock=asyncio.Lock()
        svc._contest_client=Client()
        svc._store=Store(tmp_path/"check.sqlite")
        class Bot:
            async def send_message(self,**kwargs):
                pass
        try:
            result = await svc._check_contests(SimpleNamespace(bot=Bot()))
            assert any("consulta falhou" in x for x in result)
            assert svc._store.contest_counts(123,"DF")== (1,0)
            assert svc._store.contest_status(123,"BR")["last_error"]
        finally:
            svc._store.close()
    asyncio.run(run())
