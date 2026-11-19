"""Teste integração do ciclo de alertas com cliente fake e Telegram fake."""
import asyncio
import sys
import threading
import types
from dataclasses import replace
from types import SimpleNamespace

from radar_dou.concursos import Concurso, ConcursoSnapshot, listing_url
from radar_dou.database import Store
from radar_dou.scraper import parse_search_html
from radar_dou.service import RadarService
from radar_dou.settings import AppConfig
from tests.test_scraper import HTML



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


def test_dou_pending_delivered_once_during_source_failure(tmp_path, monkeypatch, caplog):
    fake_telegram(monkeypatch)
    monitored_name = "Nome de teste para consulta"

    def fetch_unavailable(name):
        raise RuntimeError(f"Falha na URL de busca de {name}")

    async def run():
        service = RadarService(AppConfig(monitored_name, 123, FAKE_TOKEN, 60, "", True, False))
        service._dou_lock = asyncio.Lock()
        service._client = SimpleNamespace(fetch=fetch_unavailable)
        store = service._store = Store(tmp_path / "dou.sqlite")
        store.register_admin(123, monitored_name)
        watch_id = store.watch(123)["id"]
        snapshot = parse_search_html(HTML)
        store.ingest(watch_id, snapshot)
        new = replace(snapshot.publications[0], uid="new", title="Nova publicação")
        store.ingest(watch_id, replace(snapshot, total=3, publications=(*snapshot.publications, new)))
        sent = []

        async def send_message(**kwargs):
            sent.append(kwargs["text"])

        app = SimpleNamespace(bot=SimpleNamespace(send_message=send_message))
        try:
            await service._check_cycle(app)
            await service._check_cycle(app)
            assert len(sent) == 1
            assert "Nova publicação" in sent[0]
            assert store.counts(watch_id) == (3, 0)
            assert monitored_name not in store.watch(123)["last_error"]
        finally:
            store.close()

    asyncio.run(run())
    assert monitored_name not in caplog.text


def test_stop_before_thread_initializes(monkeypatch):
    service = RadarService(AppConfig("Nome de teste", 123, FAKE_TOKEN))
    ready = threading.Event()
    calls = []
    thread_main = service._thread_main

    def delayed_thread():
        ready.wait(2)
        thread_main()

    async def run():
        calls.append("started")

    monkeypatch.setattr(service, "_thread_main", delayed_thread)
    monkeypatch.setattr(service, "_run", run)
    service.start()
    service.stop()
    ready.set()
    service._thread.join(5)
    assert not service.busy
    assert calls == []


def test_temporary_telegram_startup_failure_is_retried(tmp_path, monkeypatch):
    from telegram.error import NetworkError
    from telegram.ext import Application

    monkeypatch.setenv("RADAR_DOU_HOME", str(tmp_path))
    service = RadarService(AppConfig("Nome de teste", 123, FAKE_TOKEN))
    attempts = 0
    events = []

    async def initialize(self):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise NetworkError("Temporary failure")

    async def start(self):
        events.append("started")

    async def stop(self):
        events.append("stopped")

    async def shutdown(self):
        events.append("shutdown")

    async def start_polling(self, **kwargs):
        events.append("polling")

    async def stop_polling(self):
        events.append("polling stopped")

    async def check_all(app):
        service._stop.set()

    async def timeout_immediately(awaitable, timeout):
        awaitable.close()
        raise asyncio.TimeoutError

    from telegram.ext import Updater

    monkeypatch.setattr(Application, "initialize", initialize)
    monkeypatch.setattr(Application, "start", start)
    monkeypatch.setattr(Application, "stop", stop)
    monkeypatch.setattr(Application, "shutdown", shutdown)
    monkeypatch.setattr(Updater, "start_polling", start_polling)
    monkeypatch.setattr(Updater, "stop", stop_polling)
    monkeypatch.setattr(service, "_check_all", check_all)
    monkeypatch.setattr(asyncio, "wait_for", timeout_immediately)

    async def run():
        service._stop = asyncio.Event()
        await service._run()

    asyncio.run(run())
    assert attempts == 2
    assert events == ["polling", "started", "polling stopped", "stopped", "shutdown"]
