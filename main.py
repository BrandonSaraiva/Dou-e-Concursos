"""Entrada desktop/Android e diagnósticos do executável."""
from __future__ import annotations

import os
import sys


def main() -> int:
    read_back = "--self-test-read" in sys.argv
    if "--self-test" in sys.argv or read_back:
        from radar_dou.self_test import run
        return run(read_back=read_back)
    if (sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ
            or "ANDROID_PRIVATE" in os.environ):
        from radar_dou.android_ui import main as start_app
        start_app()
        return 0
    from radar_dou.gui import main as start_app
    return start_app(background="--background" in sys.argv,
                     smoke="--smoke-gui" in sys.argv)


def _report_fatal_error(error: Exception) -> None:
    """Registra o tipo e o local do erro, sem valores de variáveis ou URLs."""
    automated = any(flag in sys.argv for flag in ("--smoke-gui", "--self-test", "--self-test-read"))
    if automated and not os.environ.get("RADAR_DOU_HOME"):
        return

    try:
        import traceback
        from pathlib import Path
        from radar_dou.settings import data_dir

        path = data_dir() / "falha_inicializacao.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        frames = traceback.extract_tb(error.__traceback__)
        lines = [type(error).__name__]
        lines.extend(f"{Path(frame.filename).name}:{frame.lineno} ({frame.name})"
                     for frame in frames)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        path = None

    if automated:
        return

    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        details = f"\n\nDiagnóstico salvo em:\n{path}" if path is not None else ""
        messagebox.showerror("Radar DOU", f"Falha na inicialização ({type(error).__name__}).{details}",
                             parent=root)
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as failure:
        _report_fatal_error(failure)
        raise SystemExit(1)
