"""Interface móvel Kivy do Radar DOU. A GUI não hospeda o bot.

A consulta e o polling rodam em um Foreground Service separado. Pode-se fechar
esta tela depois de ativar o radar, desde que o Android mantenha o serviço.
"""
from __future__ import annotations

import logging
from pathlib import Path
import threading
from urllib.parse import urlencode
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from .android_runtime import (
    SERVICE_CLASS, is_alive, is_enabled, read_clipboard_text, request_check, set_enabled, setup_android_home,
)
from .database import read_dashboard, read_contest_dashboard
from .messages import friendly_timestamp
from .scraper import SEARCH_ENDPOINT, search_parameters
from .concursos import UF_NAMES, listing_url
from .settings import AppConfig, database_file, load_settings, log_file, save_settings

BG = (0.055, 0.09, 0.15, 1)
PANEL = (0.10, 0.15, 0.23, 1)
INPUT = (0.13, 0.19, 0.29, 1)
WHITE = (0.92, 0.96, 1, 1)
SOFT = (0.69, 0.77, 0.86, 1)
MINT = (0.28, 0.86, 0.79, 1)
BLUE = (0.24, 0.45, 0.95, 1)
RED = (0.96, 0.53, 0.58, 1)


def label(text: str, height: int = 30, color=SOFT, size: int = 15) -> Label:
    obj = Label(text=text, markup=True, font_size=dp(size), color=color,
                size_hint_y=None, height=dp(height), halign="left", valign="middle")
    obj.bind(size=lambda instance, width: setattr(instance, "text_size", (max(1, instance.width), None)))
    return obj


def button(title, callback, accent=False, height=49) -> Button:
    obj = Button(text=title, size_hint_y=None, height=dp(height),
                 background_normal="", background_color=BLUE if accent else INPUT,
                 color=WHITE, bold=True, font_size=dp(15))
    obj.bind(on_release=lambda *_: callback())
    return obj


class RadarAndroid(App):
    title = "Radar DOU + Concursos"

    def build(self):
        Window.clearcolor = BG
        Window.softinput_mode = "below_target"
        self.root_dir = setup_android_home()
        self._testing = False
        self._last_logs = ""
        self._previous_status = ""
        self._log_offset = 0
        try:
            from android.permissions import request_permissions
            request_permissions(["android.permission.POST_NOTIFICATIONS"])
        except ImportError:
            pass

        page = ScrollView(do_scroll_x=False, bar_width=dp(4))
        body = BoxLayout(orientation="vertical", spacing=dp(11), padding=(dp(16), dp(20)),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        page.add_widget(body)
        body.add_widget(label("[b][color=44DCCC]◉[/color]  RADAR DOU[/b]", 58, WHITE, 29))
        body.add_widget(label("DOU + Concursos  |  Alertas no Telegram", 29, SOFT, 13))
        self.state = label("● Aguardando configuração", 40, MINT, 15)
        body.add_widget(self.state)

        body.add_widget(label("[b]01  Configuração[/b]", 39, WHITE, 19))
        body.add_widget(label("Nome ou expressão que o DOU deve acompanhar", 28, WHITE, 14))
        self.monitored_name = self._add_input(body, "Ex.: Maria da Silva")
        body.add_widget(label("Seu ID numérico no Telegram", 28, WHITE, 14))
        self.chat = self._add_input(body, "Ex.: 123456789", numeric=True)
        body.add_widget(label("Token do bot fornecido pelo @BotFather", 28, WHITE, 14))
        self.token = self._add_input(body, "123456789:token_do_bot", secret=True)
        body.add_widget(button("Mostrar/ocultar token", self._toggle, height=37))
        body.add_widget(label("Intervalo entre consultas", 28, WHITE, 14))
        self.interval = Spinner(text="60 minutos", values=("15 minutos", "30 minutos", "60 minutos",
                      "120 minutos", "360 minutos", "720 minutos", "1440 minutos"),
                      background_normal="", background_color=INPUT, color=WHITE,
                      font_size=dp(15), size_hint_y=None, height=dp(48))
        body.add_widget(self.interval)

        body.add_widget(label("[b]Escolha o que deseja monitorar[/b]", 33, WHITE, 15))
        self.dou_enabled = CheckBox(active=True, color=MINT)
        self.contests_enabled = CheckBox(active=True, color=MINT)
        for title, checkbox in (("Diário Oficial da União", self.dou_enabled),
                                ("Concursos públicos abertos", self.contests_enabled)):
            line = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(39))
            checkbox.size_hint_x = None
            checkbox.width = dp(48)
            line.add_widget(checkbox)
            line.add_widget(label(title, 39, WHITE, 14))
            body.add_widget(line)
        body.add_widget(label("UF dos concursos (além dos nacionais)", 33, WHITE, 14))
        self.uf = Spinner(text="Somente nacional", values=("Somente nacional", *UF_NAMES.keys()),
                          background_normal="", background_color=INPUT, color=WHITE,
                          size_hint_y=None, height=dp(49), font_size=dp(15))
        body.add_widget(self.uf)
        body.add_widget(label("Os concursos são consultados a cada 60 min.\n"
                              "A primeira consulta salva os existentes sem avisar.",
                              54, SOFT, 12))

        links = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(45))
        links.add_widget(button("Criar bot ↗", lambda: webbrowser.open("https://t.me/BotFather"), height=45))
        links.add_widget(button("Descobrir ID ↗", lambda: webbrowser.open("https://t.me/userinfobot"), height=45))
        body.add_widget(links)
        body.add_widget(button("SALVAR CONFIGURAÇÕES", self._save, accent=True, height=52))
        body.add_widget(button("TESTAR ENVIO PARA O TELEGRAM", self._test, height=48))

        body.add_widget(label("[b]02  Central de monitoramento[/b]", 46, WHITE, 19))
        self.numbers = label("DOU: —    Salvos: —    Pendentes: —", 42, MINT, 16)
        body.add_widget(self.numbers)
        self.contest_numbers = label("Concursos: Nacional — | UF —", 41, MINT, 14)
        body.add_widget(self.contest_numbers)
        self.last = label("Nenhuma consulta concluída", 29, SOFT, 12)
        body.add_widget(self.last)
        body.add_widget(button("▶  ATIVAR RADAR", self._start, accent=True, height=56))
        row = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(49))
        row.add_widget(button("■  DESLIGAR", self._stop))
        row.add_widget(button("↻  CONFERIR AGORA", self._check))
        body.add_widget(row)
        places = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(45))
        places.add_widget(button("Abrir site do DOU ↗", self._open_dou, height=43))
        places.add_widget(button("Concursos nacionais ↗", lambda: webbrowser.open(listing_url("BR")), height=43))
        body.add_widget(places)
        body.add_widget(label("[b]03  Registro de atividades[/b]", 43, WHITE, 19))
        self.logs = TextInput(text="Aguardando atividades...", readonly=True, multiline=True,
                              size_hint_y=None, height=dp(285), background_color=INPUT,
                              foreground_color=MINT, cursor_color=MINT, font_size=dp(12),
                              padding=(dp(10), dp(12)))
        body.add_widget(self.logs)
        body.add_widget(label("Você pode sair desta tela e usar o bot no Telegram.\n"
                              "Mantenha a notificação de serviço ativa e permita execução sem restrição de bateria.",
                              74, SOFT, 12))
        self._load()
        Clock.schedule_interval(self._refresh, 2.0)
        return page

    def _add_input(self, body, placeholder, numeric=False, secret=False):
        field = TextInput(hint_text=placeholder, multiline=False, password=secret,
                          input_filter="int" if numeric else None,
                          background_color=INPUT, foreground_color=WHITE, hint_text_color=SOFT,
                          cursor_color=MINT, font_size=dp(16),
                          padding=(dp(11), dp(11)))
        paste = button("Colar token" if secret else "Colar", lambda: self._paste_into(field), height=48)
        paste.size_hint_x = None
        paste.width = dp(103 if secret else 68)
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        row.add_widget(field)
        row.add_widget(paste)
        body.add_widget(row)
        return field

    def _paste_into(self, field):
        try:
            text = read_clipboard_text().strip()
        except Exception:
            self._set_state("Não foi possível ler a área de transferência.", error=True)
            return
        if not text:
            self._set_state("Copie um texto antes de tocar em Colar.", error=True)
            return
        if field is self.chat and (not text.isascii() or not text.isdecimal()):
            self._set_state("Copie somente o ID numérico do Telegram.", error=True)
            return
        field.text = " ".join(text.splitlines())
        self._set_state("Texto colado.")

    def _set_state(self, text, error=False):
        self.state.text = text
        self.state.color = RED if error else MINT

    def _values(self):
        try:
            state = self.uf.text.strip().upper()
            if state == "SOMENTE NACIONAL":
                state = ""
            return AppConfig(self.monitored_name.text, int(self.chat.text.strip()), self.token.text.strip(),
                             int(self.interval.text.split()[0]), uf=state,
                             monitor_dou=bool(self.dou_enabled.active),
                             monitor_concursos=bool(self.contests_enabled.active)).validated()
        except ValueError as exc:
            self._set_state("⚠ " + str(exc)[:110], error=True)
            return None

    def _toggle(self):
        self.token.password = not self.token.password

    def _load(self):
        try:
            config = load_settings()
            if config:
                self.monitored_name.text = config.name
                self.chat.text = str(config.telegram_id)
                self.token.text = config.token
                self.interval.text = f"{config.interval_minutes} minutos"
                self.uf.text = config.uf if config.uf else "Somente nacional"
                self.dou_enabled.active = config.monitor_dou
                self.contests_enabled.active = config.monitor_concursos
                self._set_state("● Dados recuperados do armazenamento local")
        except ValueError as exc:
            self._set_state("⚠ " + str(exc)[:100], error=True)
        self._refresh(0)

    def _save(self):
        if is_alive(self.root_dir):
            self._set_state("⚠ Desligue o radar antes de alterar os dados", error=True)
            return False
        config = self._values()
        if config is None:
            return False
        try:
            save_settings(config)
        except (OSError, ValueError) as exc:
            self._set_state("⚠ Falha ao salvar: " + str(exc)[:80], error=True)
            return False
        self._set_state("✓ Configuração salva no celular")
        return True

    def _start(self):
        if is_alive(self.root_dir):
            self._set_state("● O radar já está ativo")
            return
        if not self._save():
            return
        try:
            # Somente botão do usuário pode iniciar o serviço em primeiro plano.
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            service = autoclass(SERVICE_CLASS)
            set_enabled(self.root_dir, True)
            service.start(activity, "")
        except Exception as exc:
            set_enabled(self.root_dir, False)
            self._set_state("⚠ Não foi possível iniciar: " + type(exc).__name__, error=True)
            return
        self._set_state("● Ligando serviço, confira os logs...")

    def _stop(self):
        set_enabled(self.root_dir, False)
        self._set_state("○ Encerramento solicitado. Finalizando consulta com segurança...")

    def _check(self):
        if not is_alive(self.root_dir):
            self._set_state("⚠ Ative o radar antes de verificar", error=True)
            return
        request_check(self.root_dir)
        self._set_state("↻ Consulta manual solicitada")

    def _test(self):
        if self._testing:
            return
        config = self._values()
        if config is None:
            return
        self._testing = True
        self._set_state("↻ Testando o Telegram...")
        def work():
            try:
                from .service import test_credentials
                result = test_credentials(config)
                Clock.schedule_once(lambda dt, value=result: self._set_state("✓ " + value[:105]))
            except Exception:
                message = "Falha no Telegram. Confira sua conexão, o token e se enviou /start ao bot."
                Clock.schedule_once(lambda dt, value=message: self._set_state("⚠ " + value, error=True))
            finally:
                Clock.schedule_once(lambda dt: setattr(self, "_testing", False))
        threading.Thread(target=work, name="testar-telegram-android", daemon=True).start()

    def _open_dou(self):
        try:
            url = SEARCH_ENDPOINT + "?" + urlencode(search_parameters(self.monitored_name.text))
        except ValueError:
            url = SEARCH_ENDPOINT
        webbrowser.open(url)

    def _refresh(self, dt):
        active = is_alive(self.root_dir)
        if active and self._previous_status != "active":
            self._set_state("● Radar ligado no celular. Pode sair do aplicativo.")
        elif not active and self._previous_status == "active":
            self._set_state("○ Radar não está executando. Confira os logs.", error=True)
        self._previous_status = "active" if active else "inactive"
        try:
            mid = int(self.chat.text or "0")
            contests = read_contest_dashboard(database_file(), mid)
            national = contests.get("BR", {})
            region = contests.get(self.uf.text, {})
            self.contest_numbers.text = (f"🌎 Nacional: {national.get('current', '—')}"
                                         f"    📍 {self.uf.text if self.uf.text in UF_NAMES else 'UF'}: "
                                         f"{region.get('current','—')}")
            dashboard = read_dashboard(database_file(), mid)
            if dashboard:
                total = dashboard.get("result_total")
                self.numbers.text = f"DOU: {total if total is not None else '—'}   Salvos: {dashboard['saved']}   Pendentes: {dashboard['pending']}"
                self.last.text = "Última verificação: " + friendly_timestamp(dashboard.get("last_success"))
                if dashboard.get("last_error") and not active:
                    self.last.text = "Último problema: " + str(dashboard["last_error"])[:65]
        except (OSError, ValueError):
            pass
        try:
            source = log_file()
            if source.exists():
                # Tamanho limitado pelo RotatingFileHandler; exibimos apenas as linhas recentes.
                content = source.read_text(encoding="utf-8", errors="replace")
                lines = "\n".join(content.splitlines()[-90:])
                if lines != self._last_logs:
                    self.logs.text = lines or "Sem eventos ainda"
                    self._last_logs = lines
                    self.logs.scroll_y = 0
        except (OSError, AttributeError):
            pass


def main():
    RadarAndroid().run()
