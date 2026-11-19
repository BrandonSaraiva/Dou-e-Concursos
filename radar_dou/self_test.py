"""Diagnóstico do executável em uma pasta descartável, sem credenciais ou rede."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback


def run(*, read_back: bool = False) -> int:
    configured_home = os.environ.get("RADAR_DOU_HOME")
    if not configured_home or os.environ.get("RADAR_DOU_SELF_TEST") != "1":
        return 2

    home = Path(configured_home).resolve()
    if home.name != "persistence" or not home.parent.name.startswith("radar-dou-smoke-"):
        return 2
    try:
        from playwright.sync_api import sync_playwright
        from telegram.ext import JobQueue

        from .concursos import parse_concursos_html
        from .database import Store
        from .scraper import search_parameters
        from .settings import AppConfig, config_file, database_file, load_settings, save_settings

        config = AppConfig(
            "Pessoa de Teste", 123456789, "123456789:" + "X" * 35, 30, "DF",
            monitor_concursos=False,
        )
        if not read_back and home.exists():
            raise RuntimeError("A pasta do autoteste precisa ser nova")
        if read_back and not (config_file().is_file() and database_file().is_file()):
            raise RuntimeError("A primeira execução não gravou configuração e histórico")

        if not search_parameters(config.name).get("q"):
            raise RuntimeError("Parâmetros da pesquisa do DOU ausentes")
        html = """<main id="conteudo"><h1>Concursos Brasil</h1>
        <h2>Concursos Públicos Abertos Brasil</h2><table><tbody>
        <tr><td><a href="/concurso-exemplo/" title="Concurso de exemplo">Órgão</a></td>
        <td>3</td></tr></tbody></table></main>"""
        snapshot = parse_concursos_html(html, "BR")
        if len(snapshot.contests) != 1:
            raise RuntimeError("A listagem de teste não foi interpretada")

        if not read_back:
            JobQueue()
            with sync_playwright():
                pass  # Inicia o driver empacotado sem navegador nem acesso à rede.
            save_settings(config)
        if load_settings() != config:
            raise RuntimeError("A configuração lida diverge da configuração salva")
        if sys.platform == "win32":
            persisted = config_file().read_text(encoding="utf-8")
            if json.loads(persisted)["token_method"] != "dpapi" or config.token in persisted:
                raise RuntimeError("O token Windows não foi armazenado com DPAPI")

        store = Store(database_file())
        try:
            if not read_back:
                store.register_admin(config.telegram_id, config.name)
                store.ingest_contests(config.telegram_id, snapshot)
            watch = store.watch(config.telegram_id)
            contests = store.contest_list(config.telegram_id, "BR")
            if watch is None or watch["term"] != config.name:
                raise RuntimeError("O monitor não foi recuperado do SQLite")
            if len(contests) != 1 or contests[0]["url"] != snapshot.contests[0].url:
                raise RuntimeError("O histórico de concursos não foi recuperado do SQLite")
        finally:
            store.close()
    except Exception:
        home.mkdir(parents=True, exist_ok=True)
        (home / "self-test-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    return 0
