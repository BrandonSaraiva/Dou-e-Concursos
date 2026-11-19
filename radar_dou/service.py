"""Central de monitoramento DOU + concursos, com polling privado do Telegram.

A thread de asyncio não usa widgets: Tkinter e Android apenas comandam o serviço.
O catálogo de concursos é conferido a cada hora; DOU segue o intervalo definido.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading

from .concursos import ConcursoClient, UF_NAMES, listing_url
from .database import Store
from .messages import friendly_timestamp, message_lines, publication_card, safe, status_card
from .scraper import DOUClient, SEARCH_ENDPOINT
from .settings import AppConfig, database_file

LOG = logging.getLogger("radar_dou.service")


def _suppress_private_logs() -> None:
    # SDKs podem registrar a URL completa, o token e o conteúdo de atualizações.
    for library in ("telegram", "httpx", "httpcore", "urllib3"):
        logging.getLogger(library).setLevel(logging.CRITICAL + 1)


def contest_card(entry) -> str:
    """Alerta compacto e seguro (Telegram aceita somente HTML limitado)."""
    area = "🌎 Nacional" if entry["scope"] == "BR" else f"📍 {safe(entry['scope'])} · {safe(UF_NAMES[entry['scope']])}"
    return ("<b>🚨 NOVO CONCURSO NO RADAR!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{area}\n\n"
            f"🏛 <b>{safe(entry['organization'], 180)}</b>\n"
            f"📋 {safe(entry['title'], 300)}\n"
            f"👥 <b>Vagas:</b> {safe(entry['vacancies'], 100)}\n\n"
            "<i>Informação do portal Concursos no Brasil. Confira o edital e o prazo de inscrição na fonte oficial.</i>")


class RadarService:
    def __init__(self, config: AppConfig):
        self.config = config.validated()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._stop_requested = threading.Event()
        self._started = threading.Event()
        self._stopped = threading.Event()
        self._manual_checks: set[asyncio.Task] = set()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._started.is_set())

    @property
    def busy(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.busy:
            raise RuntimeError("O monitoramento já está em execução")
        self._started.clear()
        self._stopped.clear()
        self._stop_requested.clear()
        self._thread = threading.Thread(target=self._thread_main, name="radar-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested.set()
        loop, stop = self._loop, self._stop
        if loop and stop:
            try:
                loop.call_soon_threadsafe(stop.set)
            except RuntimeError:  # A thread already finishing may have closed the loop.
                return
            LOG.info("Parada solicitada; a consulta em andamento será concluída com segurança.")

    def check_now(self) -> bool:
        loop = self._loop
        if not self.running or not loop or self._stop_requested.is_set():
            return False

        def enqueue():
            if self._stop_requested.is_set() or self._manual_checks:
                return
            if self._dou_lock.locked() or self._contest_lock.locked():
                LOG.info("Já há consulta em andamento. Não vou iniciar uma duplicada.")
                return
            task = asyncio.create_task(self._check_all(self._app))
            self._manual_checks.add(task)
            task.add_done_callback(self._manual_checks.discard)

        try:
            loop.call_soon_threadsafe(enqueue)
        except RuntimeError:
            return False
        return True

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._stop = asyncio.Event()
        try:
            if not self._stop_requested.is_set():
                loop.run_until_complete(self._run())
        except Exception as exc:
            LOG.error("Serviço interrompido (%s). Confira internet, token e se outro dispositivo usa o mesmo bot.",
                      type(exc).__name__)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
            except Exception as exc:
                LOG.error("Problema ao concluir tarefas de rede (%s)", type(exc).__name__)
            loop.close()
            self._loop = None
            self._stop = None
            self._started.clear()
            self._stopped.set()
            LOG.info("Monitoramento desligado.")

    async def _run(self) -> None:
        _suppress_private_logs()

        from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M
        from telegram.constants import ParseMode
        from telegram.error import NetworkError
        from telegram.ext import Application, CallbackQueryHandler, CommandHandler

        config = self.config
        store = Store(database_file())
        if config.monitor_dou:
            store.register_admin(config.telegram_id, config.name)
        else:
            store.deactivate_watches()
        self._store = store
        self._client = DOUClient(
            browser_fallback=not (sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ
                                  or "ANDROID_PRIVATE" in os.environ),
            report=lambda message: LOG.info(message),
        )
        self._contest_client = ConcursoClient(browser_fallback=not (
            sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ
            or "ANDROID_PRIVATE" in os.environ
        ))
        self._dou_lock = asyncio.Lock()
        self._contest_lock = asyncio.Lock()

        def main_buttons():
            rows = []
            if config.monitor_concursos:
                rows.append([B("🌎 Nacionais", callback_data="ct:BR:0"),
                             B(f"📍 {config.uf or 'Estado'}", callback_data="ct:UF:0")])
                rows.append([B("🗂 Concursos disponíveis", callback_data="contest_menu")])
            if config.monitor_dou:
                rows.append([B("📚 Publicações DOU", callback_data="latest"),
                             B("🌐 Site do DOU", url=SEARCH_ENDPOINT)])
            rows.append([B("🔄 Conferir agora", callback_data="check"),
                         B("📊 Status", callback_data="status")])
            return M(rows)

        def contests_menu_buttons():
            rows = [[B("🌎 Ver nacionais", callback_data="ct:BR:0")]]
            if config.uf:
                rows.append([B(f"📍 Ver {config.uf}", callback_data="ct:UF:0")])
            rows.append([B("🔄 Conferir concursos", callback_data="check_contests"),
                         B("🏠 Menu", callback_data="home")])
            return M(rows)

        async def permitted(update):
            user, chat = update.effective_user, update.effective_chat
            ok = bool(user and chat and user.id == config.telegram_id and
                      chat.id == config.telegram_id and chat.type == "private")
            if not ok:
                LOG.warning("Tentativa de acesso não autorizada ao bot (recusada)")
                if update.callback_query:
                    await update.callback_query.answer("Acesso restrito", show_alert=True)
                elif update.effective_message:
                    await update.effective_message.reply_text("🔒 Bot privado. Você não está autorizado.")
            return ok

        async def send(update, text: str, *, markup=None, edit=False):
            if edit and update.callback_query:
                try:
                    await update.callback_query.edit_message_text(
                        text, parse_mode=ParseMode.HTML, reply_markup=markup,
                        disable_web_page_preview=True)
                    return
                except Exception as exc:
                    # Mensagem não modificada ou antiga; faça nova mensagem.
                    LOG.debug("Não foi possível editar menu: %s", type(exc).__name__)
            await update.effective_message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=markup,
                disable_web_page_preview=True)

        async def start_cmd(update, context):
            if not await permitted(update):
                return
            features = []
            if config.monitor_dou:
                features.append(f"📡 <b>DOU:</b> {safe(config.name)} · a cada {config.interval_minutes} min")
            if config.monitor_concursos:
                features.append(f"🗂 <b>Concursos:</b> nacionais" + (f" + {config.uf}" if config.uf else "") + " · a cada 60 min")
            await send(update, "<b>◉ RADAR · SUA CENTRAL DE ALERTAS</b>\n"
                       "━━━━━━━━━━━━━━━━━━━━\n\n"
                       + "\n".join(features) + "\n\n"
                       "🔔 Notificações de novidades após o cadastro inicial.\n"
                       "💾 Histórico salvo neste dispositivo.\n\n"
                       "<b>Escolha o que deseja consultar:</b>", markup=main_buttons())

        async def status_cmd(update, context):
            if not await permitted(update):
                return
            lines = ["<b>📊 STATUS DO RADAR</b>", "━━━━━━━━━━━━━━━━━━━━", ""]
            if config.monitor_dou:
                watch = store.watch(config.telegram_id)
                saved, pending = store.counts(watch["id"])
                lines.append(status_card(watch, saved, pending, config.interval_minutes))
            if config.monitor_concursos:
                lines.extend(["", "<b>🗂 CONCURSOS</b>"])
                for scope in ("BR", *((config.uf,) if config.uf else ())):
                    total, waiting = store.contest_counts(config.telegram_id, scope)
                    st = store.contest_status(config.telegram_id, scope)
                    label = "Nacionais" if scope == "BR" else scope
                    last = friendly_timestamp(st["last_success"]) if st else "Ainda não consultado"
                    lines.append(f"• <b>{safe(label)}:</b> {total} disponíveis · {waiting} avisos pendentes")
                    lines.append(f"  Atualizado: {safe(last)}")
                    if st and st["last_error"]:
                        lines.append(f"  ⚠ {safe(st['last_error'][:100])}")
            await send(update, message_lines(lines), markup=main_buttons())

        async def latest_cmd(update, context):
            if not await permitted(update):
                return
            if not config.monitor_dou:
                await send(update, "O monitoramento do DOU está desativado nas configurações.")
                return
            watch = store.watch(config.telegram_id)
            rows = store.latest(watch["id"], 10)
            if not rows:
                await send(update, "Ainda não há publicações salvas. Use /verificar.", markup=main_buttons())
                return
            body = ["<b>📚 ÚLTIMAS PUBLICAÇÕES DOU</b>", ""]
            for idx, row in enumerate(rows, 1):
                body.extend([f"<b>{idx}. {safe(row['title'], 160)}</b>",
                             f"📅 {safe(row['pub_date'], 30)} · {safe(row['organization'], 100)}",
                             f'<a href="{safe(row["url"])}">Abrir publicação</a>', ""])
            await send(update, message_lines(body), markup=main_buttons())

        async def contest_menu_cmd(update, context, *, edit=False):
            if not await permitted(update):
                return
            if not config.monitor_concursos:
                await send(update, "Concursos desativados. Ative-os no aplicativo.")
                return
            national, pending = store.contest_counts(config.telegram_id, "BR")
            local, local_pending = store.contest_counts(config.telegram_id, config.uf) if config.uf else (0,0)
            text = ("<b>🗂 CENTRAL DE CONCURSOS</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🌎 <b>Nacionais:</b> {national} disponíveis\n"
                    + (f"📍 <b>{config.uf} · {safe(UF_NAMES[config.uf])}:</b> {local} disponíveis\n" if config.uf else
                       "📍 <i>Estado não selecionado no aplicativo</i>\n")
                    + f"🔔 <b>Avisos pendentes:</b> {pending + local_pending}\n"
                      "⏰ <b>Atualização:</b> a cada 60 minutos\n\n"
                      "Selecione uma lista para ver os editais divulgados como abertos. "
                      "O portal inclui processos seletivos e estágios; confirme sempre as inscrições no edital oficial.")
            await send(update, text, markup=contests_menu_buttons(), edit=edit)

        async def contest_list_cmd(update, scope: str, offset: int = 0, *, edit=False):
            if not await permitted(update):
                return
            if not config.monitor_concursos:
                await send(update, "Concursos desativados. Ative-os no aplicativo.")
                return
            if scope == "UF":
                if not config.uf:
                    await send(update, "📍 Escolha uma UF no aplicativo e clique em Salvar configurações.",
                               markup=contests_menu_buttons())
                    return
                scope = config.uf
            if scope not in ("BR", config.uf):
                await send(update, "Região indisponível.", markup=contests_menu_buttons())
                return
            count, _ = store.contest_counts(config.telegram_id, scope)
            status = store.contest_status(config.telegram_id, scope)
            offset = max(0, min(offset, ((max(count,1)-1)//5)*5))
            lines = [f"<b>{'🌎 CONCURSOS NACIONAIS' if scope == 'BR' else '📍 CONCURSOS ' + safe(scope)}</b>",
                     "━━━━━━━━━━━━━━━━━━━━", "",
                     f"📋 <b>{count} oportunidades listadas como abertas</b>",
                     f"🕒 {safe(friendly_timestamp(status['last_success'])) if status else 'Ainda não consultado'}", ""]
            if not status or not status["seeded"]:
                lines.append("Aguardando a primeira consulta. Use ↻ Conferir concursos.")
            elif count == 0:
                lines.append("Nenhuma oportunidade listada na última consulta íntegra.")
            else:
                for index, row in enumerate(store.contest_list(config.telegram_id, scope, limit=5,offset=offset), offset+1):
                    lines.extend([f'<b>{index:02d}. <a href="{safe(row["url"])}">{safe(row["organization"], 140)}</a></b>',
                                  f"👥 Vagas: {safe(row['vacancies'], 80)}",
                                  f"📝 {safe(row['title'], 160)}", ""])
            if status and status["last_error"]:
                lines.append("⚠ Última tentativa falhou; lista salva anteriormente.")
            from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M
            navigation = []
            selector = "BR" if scope == "BR" else "UF"
            if offset > 0:
                navigation.append(B("◀ Anterior", callback_data=f"ct:{selector}:{offset-5}"))
            if offset+5 < count:
                navigation.append(B("Próxima ▶", callback_data=f"ct:{selector}:{offset+5}"))
            menu = [navigation] if navigation else []
            menu.append([B("🌎 Nacional", callback_data="ct:BR:0"),
                         B(f"📍 {config.uf or 'Estado'}", callback_data="ct:UF:0")])
            menu.append([B("↻ Atualizar", callback_data="check_contests"),
                         B("🏠 Início", callback_data="home")])
            await send(update, message_lines(lines), markup=M(menu), edit=edit)

        async def help_cmd(update, context):
            if not await permitted(update):
                return
            await send(update,
                "<b>💡 COMANDOS DO RADAR</b>\n\n"
                "/start — Menu principal\n"
                "/verificar — Consultar DOU e concursos agora\n"
                "/concursos — Abrir menu de concursos\n"
                "/nacionais — Concursos nacionais abertos\n"
                "/estaduais — Concursos abertos na UF selecionada\n"
                "/conferirconcursos — Consultar oportunidades agora\n"
                "/status — Últimas consultas e erros\n"
                "/ultimas — Últimas publicações do DOU\n"
                "/ajuda — Estas instruções\n\n"
                "A primeira consulta salva a referência, sem alertas antigos. "
                "O portal de concursos é uma fonte jornalística, não substitui o edital oficial.",
                markup=main_buttons())

        async def check_cmd(update, context):
            if not await permitted(update):
                return
            await send(update, "🔎 Consultando serviços ativos. Pode demorar um pouco...")
            summaries = await self._check_all(context.application)
            await send(update, "\n".join(summaries)[:3800], markup=main_buttons())

        async def check_contests_cmd(update, context):
            if not await permitted(update):
                return
            if not config.monitor_concursos:
                await send(update, "Concursos desativados nas configurações.")
                return
            await send(update, "🗂 Conferindo concursos nacionais e estaduais...")
            summaries = await self._check_contests(context.application)
            await send(update, "\n".join(summaries), markup=contests_menu_buttons())

        async def callback(update, context):
            if not await permitted(update):
                return
            action = update.callback_query.data
            await update.callback_query.answer()
            if action.startswith("ct:"):
                try:
                    _, scope, offset = action.split(":", 2)
                    if scope not in ("BR", "UF"):
                        return
                    page_offset = int(offset)
                    if page_offset < 0 or page_offset > 100000 or page_offset % 5:
                        return
                except (ValueError, TypeError):
                    return
                await contest_list_cmd(update, scope, page_offset, edit=True)
            elif action == "contest_menu":
                await contest_menu_cmd(update, context, edit=True)
            elif action == "check_contests":
                await check_contests_cmd(update, context)
            elif action == "check":
                await check_cmd(update, context)
            elif action == "status":
                await status_cmd(update, context)
            elif action == "latest":
                await latest_cmd(update, context)
            elif action == "home":
                await start_cmd(update, context)

        async def scheduled_dou(context):
            await self._check_cycle(context.application)

        async def scheduled_contests(context):
            await self._check_contests(context.application)

        async def telegram_error(update, context):
            if context.error:
                LOG.warning("Falha na comunicação com Telegram (%s)", type(context.error).__name__)

        def polling_error(error):
            LOG.warning("Falha no recebimento de mensagens do Telegram (%s)", type(error).__name__)

        app = Application.builder().token(config.token).build()
        self._app = app
        commands = (
            ("start", start_cmd), ("verificar", check_cmd), ("status", status_cmd),
            ("ultimas", latest_cmd), ("resultados", latest_cmd), ("ajuda", help_cmd),
            ("concursos", lambda u,c: contest_menu_cmd(u,c)),
            ("nacionais", lambda u,c: contest_list_cmd(u,"BR")),
            ("estaduais", lambda u,c: contest_list_cmd(u,"UF")),
            ("conferirconcursos", check_contests_cmd),
        )
        for command, handler in commands:
            app.add_handler(CommandHandler(command, handler))
        app.add_handler(CallbackQueryHandler(callback, pattern=r"^(ct:(BR|UF):\d+|contest_menu|check_contests|check|status|latest|home)$"))
        app.add_error_handler(telegram_error)
        if app.job_queue is None:
            raise RuntimeError("Instale python-telegram-bot[job-queue]")
        if config.monitor_dou:
            app.job_queue.run_repeating(scheduled_dou, interval=config.interval_minutes*60,
                  first=config.interval_minutes*60, name="dou-periodico",
                  job_kwargs={"coalesce":True,"max_instances":1})
        if config.monitor_concursos:
            app.job_queue.run_repeating(scheduled_contests, interval=3600, first=3600,
                  name="concursos-a-cada-hora", job_kwargs={"coalesce":True,"max_instances":1})
        initialized = started = polling = False
        active_check = None
        try:
            LOG.info("Conectando ao Telegram para validar as credenciais...")
            delay = 2
            while not self._stop_requested.is_set():
                try:
                    if not initialized:
                        await app.initialize()
                        initialized = True
                    await app.updater.start_polling(
                        drop_pending_updates=False, timeout=15, error_callback=polling_error)
                    polling = True
                    break
                except NetworkError as exc:
                    LOG.warning("Telegram indisponível (%s). Nova tentativa em %s s.",
                                type(exc).__name__, delay)
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    except asyncio.TimeoutError:
                        delay = min(delay * 2, 60)
            if self._stop_requested.is_set():
                return
            LOG.info("Bot autenticado no Telegram.")
            await app.start()
            started = True
            self._started.set()
            LOG.info("RADAR ATIVO. DOU: %s | Concursos: %s; checagem de concursos a cada 60 minutos.",
                     "sim" if config.monitor_dou else "não", "sim" if config.monitor_concursos else "não")
            active_check = asyncio.create_task(self._check_all(app))
            await self._stop.wait()
        finally:
            self._started.clear()
            checks = list(self._manual_checks)
            if active_check is not None:
                checks.append(active_check)
            try:
                if polling:
                    await app.updater.stop()
            finally:
                try:
                    if checks:
                        await asyncio.gather(*checks, return_exceptions=True)
                    if started:
                        await app.stop()
                finally:
                    try:
                        if initialized:
                            await app.shutdown()
                    finally:
                        self._client.session.close()
                        self._contest_client.session.close()
                        store.close()

    async def _check_all(self, app) -> list[str]:
        tasks = []
        if self.config.monitor_dou:
            tasks.append(self._check_cycle(app))
        if self.config.monitor_concursos:
            tasks.append(self._check_contests(app))
        answers = await asyncio.gather(*tasks, return_exceptions=True)
        result = []
        for answer in answers:
            if isinstance(answer, BaseException):
                LOG.error("Erro de consulta: %s", type(answer).__name__)
                result.append("⚠ Falha em um monitor. Consulte os logs.")
            elif isinstance(answer, list):
                result.extend(answer)
            else:
                result.append(answer)
        return result

    async def _check_cycle(self, app) -> str:
        from telegram.constants import ParseMode
        from telegram.error import TelegramError
        if self._stop_requested.is_set():
            return "DOU: monitoramento encerrando."
        if self._dou_lock.locked():
            return "DOU: já existe verificação em andamento."
        async with self._dou_lock:
            watch = self._store.watch(self.config.telegram_id)
            if not watch:
                return "DOU: sem monitor configurado."
            summary = "⚠ DOU: consulta indisponível; dados anteriores preservados."
            try:
                LOG.info("DOU: iniciando busca.")
                snap = await asyncio.to_thread(self._client.fetch, self.config.name)
                added, baseline = self._store.ingest(watch["id"], snap)
                LOG.info("DOU: %s publicação(ões) encontradas; %s inédita(s).", snap.total, added)
                if baseline:
                    LOG.info("DOU: primeira consulta salva sem notificações antigas.")
                    summary = f"✅ DOU: referência inicial com {snap.total} publicações."
                else:
                    summary = f"✅ DOU: {snap.total} resultados, {added} novos."
            except Exception as exc:
                detail = type(exc).__name__
                self._store.set_error(watch["id"], f"Consulta ao DOU indisponível ({detail})")
                LOG.warning("DOU: consulta falhou (%s). Histórico preservado.", detail)

            # Pendências do Telegram podem ser entregues mesmo quando o DOU está fora do ar.
            sent = 0
            for pub in self._store.pending(watch["id"], limit=60):
                if self._stop_requested.is_set():
                    break
                try:
                    await app.bot.send_message(chat_id=self.config.telegram_id,
                          text=publication_card(pub), parse_mode=ParseMode.HTML,
                          disable_web_page_preview=True)
                except TelegramError as exc:
                    self._store.mark_send_error(watch["id"], pub["uid"], type(exc).__name__)
                    LOG.warning("DOU: alerta não entregue (%s), mantido na fila.", type(exc).__name__)
                    break
                self._store.mark_sent(watch["id"], pub["uid"])
                sent += 1
                await asyncio.sleep(1.05)
            LOG.info("DOU: %s notificações entregues neste ciclo.", sent)
            return f"{summary} {sent} alertas enviados." if sent else summary

    async def _check_contests(self, app) -> list[str]:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.constants import ParseMode
        from telegram.error import TelegramError
        if self._stop_requested.is_set():
            return ["Concursos: monitoramento encerrando."]
        if self._contest_lock.locked():
            return ["Concursos: outra conferência está em andamento."]
        async with self._contest_lock:
            config = self.config
            results = []
            for scope in ("BR", *((config.uf,) if config.uf else ())):
                if self._stop_requested.is_set():
                    break
                try:
                    LOG.info("CONCURSOS %s: conectando ao portal %s", scope, listing_url(scope))
                    snap = await asyncio.to_thread(self._contest_client.fetch, scope)
                    if snap.scope != scope:
                        raise ValueError("Catálogo de região inesperada")
                    added, baseline = self._store.ingest_contests(config.telegram_id, snap)
                    current, _ = self._store.contest_counts(config.telegram_id, scope)
                    LOG.info("CONCURSOS %s: %s oportunidades abertas, %s URLs inéditas, referência inicial=%s.",
                             scope, current, added, baseline)
                    results.append(f"✅ Concursos {scope}: {current} abertos" +
                                   (" (referência inicial)." if baseline else f", {added} novos."))
                except Exception as exc:
                    detail = type(exc).__name__
                    self._store.set_contests_error(config.telegram_id, scope, f"Consulta indisponível ({detail})")
                    LOG.warning("CONCURSOS %s: %s. Histórico anterior preservado.", scope, detail)
                    results.append(f"⚠ Concursos {scope}: consulta falhou; histórico mantido.")
            delivered = 0
            for entry in self._store.pending_contests(config.telegram_id, limit=30,
                                    scopes=("BR", *((config.uf,) if config.uf else ()))):
                if self._stop_requested.is_set():
                    break
                try:
                    controls = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📄 Ver detalhes do concurso", url=entry["url"])],
                        [InlineKeyboardButton("🌎 Ver nacionais", callback_data="ct:BR:0"),
                         InlineKeyboardButton(f"📍 {config.uf or 'Estado'}", callback_data="ct:UF:0")],
                    ])
                    await app.bot.send_message(chat_id=config.telegram_id,
                            text=contest_card(entry), parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True, reply_markup=controls)
                except TelegramError as exc:
                    self._store.mark_contest_send_error(config.telegram_id, entry["scope"],
                                                        entry["url"], type(exc).__name__)
                    LOG.warning("CONCURSOS: falha no Telegram (%s); aviso permanece pendente.", type(exc).__name__)
                    break
                else:
                    self._store.mark_contest_sent(config.telegram_id, entry["scope"], entry["url"])
                    delivered += 1
                    LOG.info("CONCURSOS: alerta entregue: %s (%s).", entry["organization"][:80], entry["scope"])
                    await asyncio.sleep(1.05)
            LOG.info("CONCURSOS: %s alertas entregues neste ciclo.", delivered)
            return results


async def _test_credentials_async(config: AppConfig) -> str:
    _suppress_private_logs()
    from telegram import Bot
    from telegram.error import TelegramError
    try:
        async with Bot(config.token) as bot:
            await bot.send_message(chat_id=config.telegram_id,
                text="✅ Radar conectado! O Telegram receberá alertas de DOU e/ou concursos conforme suas escolhas.")
            return "Mensagem de teste entregue no Telegram."
    except TelegramError as exc:
        raise RuntimeError(f"Telegram indisponível ({type(exc).__name__}). Confira o token, o ID e se enviou /start ao bot.") from None


def test_credentials(config: AppConfig) -> str:
    return asyncio.run(_test_credentials_async(config.validated()))
