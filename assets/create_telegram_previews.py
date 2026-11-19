"""Renderiza duas prévias do bot com o serviço real e fontes fictícias locais.

Execute na raiz do projeto: python -m assets.create_telegram_previews
Requer as dependências do projeto e Microsoft Edge ou Chromium do Playwright.
"""

import asyncio
from dataclasses import replace
from html import escape
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from playwright.sync_api import sync_playwright
from telegram.ext import Application

from radar_dou import service as radar
from radar_dou.concursos import Concurso, ConcursoSnapshot
from radar_dou.scraper import Publication, Snapshot
from radar_dou.settings import AppConfig


ASSETS = Path(__file__).resolve().parent
EXAMPLE_URL = "https://radar-exemplo.invalid"
EXAMPLE_NAME = "Pessoa Demonstrativa"
EXAMPLE_ID = 314159
EXAMPLE_TOKEN = "314159:" + "APENAS_DEMONSTRACAO_" * 2
EXAMPLE_TIME = "2026-11-12T12:18:00+00:00"


def local_client(fetch):
    return SimpleNamespace(fetch=fetch, session=SimpleNamespace(close=Mock()))


async def record(config, command, *, seed, dou_client=None, contest_client=None):
    """Executa os handlers do bot com um Telegram em memória e um SQLite temporário."""
    service = radar.RadarService(config)
    service._stop = asyncio.Event()
    recorded = asyncio.get_running_loop().create_future()
    handlers = []
    app = SimpleNamespace(
        add_handler=handlers.append, add_error_handler=Mock(),
        initialize=AsyncMock(), start=AsyncMock(), stop=AsyncMock(), shutdown=AsyncMock(),
        updater=SimpleNamespace(start_polling=AsyncMock(), stop=AsyncMock()),
        job_queue=SimpleNamespace(run_repeating=Mock()),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )
    builder = Mock()
    builder.token.return_value.build.return_value = app

    async def capture(active_app):
        try:
            seed(service._store)
            if config.monitor_dou:
                await service._check_cycle(active_app)
            else:
                await service._check_contests(active_app)
            assert app.bot.send_message.await_count == 1, "A fixture deve gerar um único alerta."
            reply = AsyncMock()
            update = SimpleNamespace(
                effective_user=SimpleNamespace(id=config.telegram_id),
                effective_chat=SimpleNamespace(id=config.telegram_id, type="private"),
                effective_message=SimpleNamespace(reply_text=reply),
                callback_query=None,
            )
            handler = next(item for item in handlers if command in getattr(item, "commands", ()))
            await handler.callback(update, None)
            reply.assert_awaited_once()
            response = dict(text=reply.await_args.args[0], **reply.await_args.kwargs)
            recorded.set_result((response, app.bot.send_message.await_args.kwargs))
        except Exception as error:
            recorded.set_exception(error)
        finally:
            service._stop.set()

    with TemporaryDirectory(prefix="radar-telegram-exemplo-") as folder:
        with (
            patch.object(Application, "builder", return_value=builder),
            patch.object(radar, "database_file", return_value=Path(folder) / "exemplo.sqlite3"),
            patch.object(radar, "DOUClient", return_value=dou_client or local_client(Mock())),
            patch.object(radar, "ConcursoClient", return_value=contest_client or local_client(Mock())),
            patch("radar_dou.database.now_utc", return_value=EXAMPLE_TIME),
            patch.object(service, "_check_all", side_effect=capture),
        ):
            await asyncio.wait_for(service._run(), timeout=30)
    return recorded.result()


async def dou_example():
    publication = Publication(
        uid="dou-exemplo-2",
        title="Portaria de demonstração nº 24, de 12 de novembro de 2026",
        url=f"{EXAMPLE_URL}/dou/portaria-24",
        pub_date="12/11/2026", section="Seção 2", edition="214", page="17",
        organization="Agência Federal de Exemplo",
        hierarchy=("Agência Federal de Exemplo", "Diretoria de Administração"),
        act_type="Portaria",
        snippet=f"Designar {EXAMPLE_NAME} para integrar a comissão de modernização administrativa.",
        raw={},
    )
    previous = replace(
        publication, uid="dou-exemplo-1", title="Portaria de demonstração nº 18",
        url=f"{EXAMPLE_URL}/dou/portaria-18",
    )
    search_url = f"{EXAMPLE_URL}/consulta"

    def seed(store):
        watch = store.watch(EXAMPLE_ID)
        store.ingest(watch["id"], Snapshot(1, (previous,), search_url))

    latest = Snapshot(2, (publication, previous), search_url)
    return await record(
        AppConfig(EXAMPLE_NAME, EXAMPLE_ID, EXAMPLE_TOKEN, monitor_concursos=False),
        "status", seed=seed, dou_client=local_client(lambda name: latest),
    )


async def contests_example():
    national = Concurso(
        "Fundação Nacional de Exemplo", "18", "Seleção de demonstração",
        f"{EXAMPLE_URL}/concursos/exemplo-nacional",
    )
    state = Concurso(
        "Instituto Distrital de Exemplo", "12", "Concurso para analista e técnico",
        f"{EXAMPLE_URL}/concursos/auditoria-distrital",
    )
    another_national = replace(
        national, organization="Agência Nacional de Exemplo", vacancies="25",
        url=f"{EXAMPLE_URL}/concursos/outro-exemplo-nacional",
    )
    previous_state = replace(
        state, organization="Secretaria Distrital de Exemplo", vacancies="7",
        url=f"{EXAMPLE_URL}/concursos/exemplo-distrital",
    )
    national_catalog = ConcursoSnapshot(
        "BR", (national, another_national), f"{EXAMPLE_URL}/concursos/br",
    )
    state_catalog = ConcursoSnapshot("DF", (previous_state, state), f"{EXAMPLE_URL}/concursos/df")

    def seed(store):
        store.ingest_contests(EXAMPLE_ID, national_catalog)
        store.ingest_contests(EXAMPLE_ID, replace(state_catalog, contests=(previous_state,)))

    catalogs = {"BR": national_catalog, "DF": state_catalog}
    return await record(
        AppConfig("", EXAMPLE_ID, EXAMPLE_TOKEN, uf="DF", monitor_dou=False),
        "concursos", seed=seed, contest_client=local_client(catalogs.__getitem__),
    )


STYLE = """
    * { box-sizing: border-box; }
    body {
        margin: 0; background: #101725; color: #edf4ff;
        font: 22px/1.38 "Segoe UI", "DejaVu Sans", sans-serif;
    }
    main { padding: 40px 48px 32px; }
    header { margin-bottom: 28px; }
    .eyebrow { color: #66e1d3; font-size: 21px; font-weight: 700; letter-spacing: .04em; }
    h1 { font-size: 45px; line-height: 1.18; margin: 8px 0; }
    header p, footer { color: #b6c7df; margin: 0; }
    section { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
    article {
        background: #192335; border: 1px solid #354a64; border-radius: 18px;
        padding: 20px; display: flex; flex-direction: column; gap: 14px;
    }
    h2 { font-size: 25px; margin: 0; }
    .tag {
        font-size: 19px; font-weight: 600; background: #253650; color: #bfece6;
        border-radius: 8px; padding: 4px 11px; align-self: flex-start;
    }
    .message {
        white-space: pre-line; overflow-wrap: anywhere;
        background: #111b2b; border: 1px solid #354a64;
        border-radius: 12px; padding: 16px 18px; font-size: 20px;
    }
    a { color: #96ddff; text-underline-offset: 3px; }
    .keyboard { display: grid; gap: 6px; }
    .row { display: flex; gap: 6px; }
    .control {
        background: #253650; border: 1px solid #354a64; border-radius: 8px;
        color: #c7eefc; padding: 8px 10px; text-align: center; flex: 1;
        font-size: 17px; font-weight: 600;
    }
    footer { margin-top: 20px; font-size: 19px; }
"""


def message_panel(title, caption, content):
    controls = content.get("reply_markup")
    keyboard = ""
    if controls:
        rows = []
        for row in controls.inline_keyboard:
            buttons = "".join(f'<span class="control">{escape(button.text)}</span>' for button in row)
            rows.append(f'<div class="row">{buttons}</div>')
        keyboard = f'<div class="keyboard">{"".join(rows)}</div>'
    return (
        f"<article><h2>{title}</h2><div class='tag'>{caption}</div>"
        f"<div class='message'>{content['text']}</div>{keyboard}</article>"
    )


def render(page, filename, title, subtitle, command, messages, footer):
    response, alert = messages
    page.set_content(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        f"<style>{STYLE}</style><main><header><div class='eyebrow'>TELEGRAM / SIMULAÇÃO COM DADOS FICTÍCIOS</div>"
        f"<h1>{title}</h1><p>{subtitle}</p></header><section>"
        + message_panel("Consulta no chat", command, response)
        + message_panel("Alerta automático", "Após a referência inicial", alert)
        + f"</section><footer>{footer}</footer></main></html>"
    )
    page.locator("main").screenshot(path=str(ASSETS / filename), animations="disabled")


def main():
    dou = asyncio.run(dou_example())
    contests = asyncio.run(contests_example())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge" if os.name == "nt" else None)
        page = browser.new_page(viewport={"width": 1200, "height": 1000})
        page.route("**/*", lambda route: route.abort())
        render(
            page, "telegram-dou-exemplo.png", "Uma publicação nova no DOU",
            "O bot mostra o nome monitorado em /status e avisa quando encontra uma publicação inédita.",
            "/status", dou, "Abra a publicação original para confirmar o contexto e o conteúdo do ato.",
        )
        render(
            page, "telegram-concursos-exemplo.png", "Concursos nacionais e estaduais",
            "O comando /concursos abre o menu. Neste exemplo, a UF configurada é DF.",
            "/concursos", contests, "Para consultar uma lista, toque em Ver nacionais ou Ver DF.",
        )
        browser.close()


if __name__ == "__main__":
    main()
