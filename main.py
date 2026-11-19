"""Entrada desktop/Android e autodiagnóstico de um executável compilado."""
from __future__ import annotations

import os
import sys


def bundled_self_test() -> int:
    """Smoke test sem rede, interface, token ou banco de dados do usuário.

    Deve funcionar também no RadarDOU.exe --self-test (--windowed).
    """
    try:
        import requests  # noqa: F401
        import bs4  # noqa: F401
        import telegram  # noqa: F401
        import apscheduler  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
        from radar_dou.gui import RadarApp  # noqa: F401
        from radar_dou.scraper import search_parameters
        from radar_dou.concursos import parse_concursos_html

        if not search_parameters("Maria da Silva").get("q"):
            return 3
        mock = """<main id='conteudo'><h1>Concursos Brasil</h1>
        <h2>Concursos Públicos Abertos Brasil</h2><table><tbody>
        <tr><td><a href='https://concursosnobrasil.com/concurso-exemplo/'
        title='Concurso de exemplo'>Órgão</a></td><td>3</td></tr>
        </tbody></table></main>"""
        if len(parse_concursos_html(mock, 'BR').contests) != 1:
            return 4
        return 0
    except Exception:
        # --windowed não tem sys.stderr; salvar o diagnóstico sem credenciais.
        try:
            import tempfile
            import traceback
            from pathlib import Path
            (Path(tempfile.gettempdir()) / "radar-dou-self-test-erro.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        return 2


def main():
    if "--self-test" in sys.argv:
        raise SystemExit(bundled_self_test())
    if (sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ
            or "ANDROID_PRIVATE" in os.environ):
        from radar_dou.android_ui import main as start_app
    else:
        from radar_dou.gui import main as start_app
    start_app()


def _report_fatal_error(error: Exception) -> None:
    """Evita que um EXE --windowed suma sem deixar diagnóstico."""
    try:
        import traceback
        from radar_dou.settings import data_dir
        path = data_dir() / "falha_inicializacao.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Local ao usuário. Não publicar relatórios sem revisar dados sensíveis.
        path.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            from tkinter import Tk, messagebox
            root = Tk()
            root.withdraw()
            messagebox.showerror(
                "Radar DOU: falha na inicialização",
                f"O programa encontrou um erro: {type(error).__name__}.\n\n"
                f"Detalhes foram salvos em:\n{path}\n\n"
                "Não compartilhe o arquivo sem ocultar dados pessoais.",
                parent=root,
            )
            root.destroy()
        except Exception:
            pass
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        _report_fatal_error(failure)
        raise SystemExit(1)
