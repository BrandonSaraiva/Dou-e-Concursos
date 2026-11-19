"""Entrada do serviço Android em primeiro plano: independente da interface.

O SO pode matar/reiniciar serviços; o arquivo monitor.json documenta a escolha
explícita do usuário. Não iniciamos serviço automaticamente ao ligar o celular.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import re
import time

from radar_dou.android_runtime import (
    is_enabled, set_enabled, setup_android_home, take_check_request, write_heartbeat,
)
from radar_dou.settings import load_settings, log_file
from radar_dou.service import RadarService


class PrivateFormatter(logging.Formatter):
    def __init__(self, secret: str):
        super().__init__("%(asctime)s | %(levelname)s | %(message)s", "%d/%m %H:%M:%S")
        self.secret = secret

    def format(self, record):
        content = super().format(record)
        if self.secret:
            content = content.replace(self.secret, "[TOKEN_OCULTO]")
        return re.sub(r"bot\d{5,}:[A-Za-z0-9_-]{20,}", "bot[TOKEN_OCULTO]", content)


def run() -> None:
    root = setup_android_home(for_service=True)
    config = load_settings()
    logger = logging.getLogger("radar_dou")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for old in list(logger.handlers):
        logger.removeHandler(old)
        old.close()
    file_handler = RotatingFileHandler(log_file(), encoding="utf-8", maxBytes=2_000_000, backupCount=3)
    file_handler.setFormatter(PrivateFormatter(config.token if config else ""))
    logger.addHandler(file_handler)
    for library in ("httpx", "httpcore", "telegram", "apscheduler"):
        logging.getLogger(library).setLevel(logging.WARNING)

    from jnius import autoclass
    android = autoclass("org.kivy.android.PythonService").mService
    # Reinício pelo SO quando possível; não implica promessa de execução 24/7.
    android.setAutoRestartService(True)
    service = None
    try:
        if not is_enabled(root):
            logger.info("Serviço iniciado, mas monitoramento está desativado.")
            return
        if not config:
            logger.error("Nenhuma configuração foi encontrada; abra o aplicativo e salve seus dados.")
            set_enabled(root, False)
            return
        logger.info("Serviço Android em primeiro plano iniciado; notificação persistente ativa.")
        logger.info("Consultas móveis DOU/concursos por HTTP; Playwright indisponível no Android.")
        service = RadarService(config)
        service.start()
        # Serviço Android possui processo próprio e continua quando a janela é fechada.
        while is_enabled(root):
            write_heartbeat(root)
            if take_check_request(root):
                if service.running:
                    logger.info("Consulta manual solicitada pela interface Android.")
                    service.check_now()
                else:
                    logger.warning("O bot ainda não se conectou para aceitar a consulta manual.")
            if not service.busy:
                logger.error("O bot foi interrompido. Consulte as mensagens acima e reative o radar.")
                set_enabled(root, False)
                break
            time.sleep(1.5)
    except Exception as error:
        logger.exception("Falha inesperada do serviço Android: %s", type(error).__name__)
        set_enabled(root, False)
    finally:
        if service and service.busy:
            service.stop()
            for _ in range(120):
                if not service.busy:
                    break
                time.sleep(0.5)
        if not is_enabled(root):
            android.setAutoRestartService(False)
        write_heartbeat(root, active=False)
        logger.info("Serviço Android finalizado.")


if __name__ == "__main__":
    run()
