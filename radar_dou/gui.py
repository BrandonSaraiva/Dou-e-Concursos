"""Interface gráfica Tkinter: funciona sem terminal, VS Code ou edição de .env."""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from contextlib import nullcontext
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from .database import read_dashboard, read_contest_dashboard
from .messages import friendly_timestamp
from .settings import AppConfig, data_dir, database_file, load_settings, log_file, save_settings
from .scraper import SEARCH_ENDPOINT
from .concursos import UF_NAMES, listing_url

BG = "#101725"
PANEL = "#192335"
CARD = "#1f2c40"
BORDER = "#30425c"
TEXT = "#edf4ff"
MUTED = "#a9b9d1"
CYAN = "#38d5ca"
BLUE = "#4078f5"
RED = "#fc878e"
YELLOW = "#ffd08b"


class SafeLogFormatter(logging.Formatter):
    def __init__(self, token_getter):
        super().__init__("%(asctime)s | %(levelname)s | %(message)s", datefmt="%d/%m %H:%M:%S")
        self.token_getter = token_getter

    def format(self, record):
        result = super().format(record)
        token = self.token_getter()
        if token:
            result = result.replace(token, "[TOKEN_OCULTO]")
        return re.sub(r"\d{5,}:[A-Za-z0-9_-]{20,}", "[TOKEN_OCULTO]", result)


class UIQueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.events = q

    def emit(self, record):
        try:
            self.events.put(("log", self.format(record), record.levelno))
        except Exception:
            self.handleError(record)


class RadarApp(tk.Tk):
    def __init__(self, *, instance=None, background=False, smoke=False):
        super().__init__()
        if background:
            self.withdraw()
        self.title("Radar DOU + Concursos  •  Central de alertas")
        self.geometry("1160x830")
        self.minsize(1000, 720)
        self.configure(bg=BG)
        self._service = None
        self._events = queue.Queue()
        self._closing = False
        self._last_running = False
        self._last_busy = False
        self._stop_requested = False
        self._instance = instance
        self._tray = None
        self._tray_ready = False
        self._logged_token = ""
        self._smoke = smoke
        self.smoke_result = 0
        self._ticks = 0
        self.name_var = tk.StringVar()
        self.chat_var = tk.StringVar()
        self.token_var = tk.StringVar()
        self.interval_var = tk.StringVar(value="60")
        self.start_with_windows_var = tk.BooleanVar(value=False)
        self.dou_enabled_var = tk.BooleanVar(value=True)
        self.contests_enabled_var = tk.BooleanVar(value=True)
        self.uf_var = tk.StringVar(value="Somente nacional")
        self.contests_var = tk.StringVar(value="Nacionais: —    Estado: —")
        self.state_var = tk.StringVar(value="Aguardando configuração")
        self.total_var = tk.StringVar(value="—")
        self.saved_var = tk.StringVar(value="—")
        self.pending_var = tk.StringVar(value="—")
        self.last_var = tk.StringVar(value="Nenhuma consulta realizada")
        styles = ttk.Style(self)
        styles.theme_use("clam")
        styles.configure("Radar.TCombobox", fieldbackground=BG, background=CARD,
                         foreground=TEXT, arrowcolor=CYAN, bordercolor=BORDER,
                         lightcolor=BORDER, darkcolor=BORDER)
        styles.map("Radar.TCombobox", fieldbackground=[("readonly", BG)],
                   foreground=[("readonly", TEXT)])
        self._build()
        self._setup_logging()
        config = self._load_persisted()
        self._load_previous_logs()
        if background and (not config or not config.start_with_windows):
            self.destroy()
            return
        if self._instance is not None:
            try:
                from .windows import WindowsTray
                self._tray = WindowsTray(lambda event: self._events.put((event, "", logging.INFO)))
            except Exception as exc:
                if smoke:
                    raise
                self.log.warning("Bandeja indisponível (%s).", type(exc).__name__)
                self._restore_window()
        if background:
            self._start_monitor(config)
        self.after(150, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _setup_logging(self):
        folder = data_dir()
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        logger = logging.getLogger("radar_dou")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        # Os handlers também rodam na thread do serviço. Não consultam Tkinter.
        formatter = SafeLogFormatter(lambda: self._logged_token)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        ui_handler = UIQueueHandler(self._events)
        ui_handler.setFormatter(formatter)
        file_handler = RotatingFileHandler(log_file(), maxBytes=2_000_000,
                                           backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(ui_handler)
        logger.addHandler(file_handler)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
        self.log = logger

    def _pill(self, parent, label, color):
        return tk.Label(parent, text=label, bg=PANEL, fg=color, font=("Segoe UI", 10, "bold"), padx=10, pady=7)

    def _build(self):
        header = tk.Frame(self, bg=BG, padx=30, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="◉", bg=BG, fg=CYAN, font=("Segoe UI", 32)).pack(side="left", padx=(0, 11))
        htext = tk.Frame(header, bg=BG)
        htext.pack(side="left")
        tk.Label(htext, text="RADAR DOU", bg=BG, fg=TEXT,
                 font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(htext, text="Diário Oficial + Concursos públicos  /  Alertas no Telegram",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(header, textvariable=self.state_var, bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 10, "bold"), padx=16, pady=12).pack(side="right")

        content = tk.Frame(self, bg=BG, padx=24)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=4)
        content.grid_columnconfigure(1, weight=6)
        content.grid_rowconfigure(0, weight=1)

        left = tk.Frame(content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                        padx=20, pady=20)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 11))
        right = tk.Frame(content, bg=PANEL, highlightbackground=BORDER,
                         highlightthickness=1, padx=20, pady=20)
        right.grid(row=0, column=1, sticky="nsew", padx=(11, 0))
        # O painel de configuração recebe barra de rolagem para caber em telas menores.
        canvas = tk.Canvas(left, bg=PANEL, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content_left = tk.Frame(canvas, bg=PANEL, padx=2, pady=2)
        window_id = canvas.create_window((0,0), window=content_left, anchor="nw")
        content_left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        self._left(content_left)
        self._right(right)
        tk.Label(self, text="Projeto independente  •  DOU + Concursos no Brasil  •  Dados armazenados no dispositivo",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9), pady=13).pack(fill="x")

    def _section(self, parent, title, desc):
        tk.Label(parent, text=title, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(parent, text=desc, bg=PANEL, fg=MUTED, font=("Segoe UI", 10),
                 wraplength=335, justify="left", pady=5).pack(anchor="w")

    def _field(self, parent, title, var, hint, secret=False):
        tk.Label(parent, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold"),
                 pady=4).pack(anchor="w")
        line = tk.Frame(parent, bg=PANEL)
        line.pack(fill="x")
        entry = tk.Entry(line, textvariable=var, bg=BG, fg=TEXT, relief="flat",
                         insertbackground=CYAN, font=("Segoe UI", 11),
                         highlightbackground=BORDER, highlightthickness=1,
                         highlightcolor=CYAN, borderwidth=0,
                         show="•" if secret else "")
        entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 7) if secret else 0)
        if secret:
            tk.Button(line, text="Mostrar", command=self._toggle_secret, bg=CARD,
                      fg=TEXT, relief="flat", cursor="hand2", padx=8, pady=9,
                      activebackground=BORDER, activeforeground=TEXT).pack(side="right")
            self._token_entry = entry
        tk.Label(parent, text=hint, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), wraplength=330, justify="left").pack(anchor="w", pady=(2, 4))
        return entry

    def _button(self, parent, text, command, accent=False, width=None):
        button = tk.Button(parent, text=text, command=command,
                           bg=BLUE if accent else CARD, fg="#ffffff" if accent else TEXT,
                           activebackground="#5587fc" if accent else BORDER,
                           activeforeground="white", relief="flat", borderwidth=0,
                           font=("Segoe UI", 10, "bold"), padx=13, pady=10,
                           cursor="hand2", width=width)
        return button

    def _left(self, parent):
        self._section(parent, "01  Configurar monitoramento",
                      "Preencha uma vez. As informações serão lembradas nas próximas vezes.")
        self._field(parent, "Nome ou expressão para acompanhar", self.name_var,
                    "A busca replica a expressão exata do DOU.")
        self._field(parent, "Seu ID numérico do Telegram", self.chat_var,
                    "É o ID da sua conta, não o número de telefone. Veja @userinfobot.")
        self._field(parent, "Token do seu bot (BotFather)", self.token_var,
                    "O token inclui números, dois-pontos e letras. Ele não é apenas o ID do bot.", secret=True)
        tk.Label(parent, text="Intervalo entre consultas", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold"), pady=4).pack(anchor="w")
        items = ttk.Combobox(parent, style="Radar.TCombobox", values=("15", "30", "60", "120", "360", "720", "1440"),
                             textvariable=self.interval_var, state="readonly", width=8,
                             font=("Segoe UI", 11))
        items.pack(anchor="w", fill="x", ipady=6)
        tk.Label(parent, text="Intervalo do DOU. Concursos são consultados a cada 60 min.", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 9), pady=4, wraplength=330, justify="left").pack(anchor="w")
        tk.Label(parent, text="MONITORAMENTOS", bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 10, "bold"), pady=8).pack(anchor="w")
        for label_text, variable in (("📡 Monitorar nome no DOU", self.dou_enabled_var),
                                     ("🗂 Monitorar concursos abertos", self.contests_enabled_var)):
            tk.Checkbutton(parent, text=label_text, variable=variable, bg=PANEL, fg=TEXT,
                           activebackground=PANEL, activeforeground=CYAN,
                           selectcolor=BG, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(parent, text="UF para os concursos estaduais", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold"), pady=5).pack(anchor="w")
        self.uf_picker = ttk.Combobox(parent, textvariable=self.uf_var,
                     values=("Somente nacional", *UF_NAMES.keys()), state="readonly",
                     style="Radar.TCombobox", font=("Segoe UI", 11))
        self.uf_picker.pack(fill="x", ipady=5)
        tk.Label(parent, text="Nacionais são monitorados sempre que Concursos estiver ativo.\n"
                 "Para receber também seu estado, escolha a sigla (ex.: DF).",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9), justify="left",
                 wraplength=330).pack(anchor="w", pady=(2,7))
        if self._instance is not None:
            tk.Checkbutton(parent, text="Iniciar monitoramento ao entrar no Windows",
                           variable=self.start_with_windows_var, bg=PANEL, fg=TEXT,
                           activebackground=PANEL, activeforeground=CYAN,
                           selectcolor=BG, font=("Segoe UI", 10),
                           wraplength=310, justify="left").pack(anchor="w")
        links = tk.Frame(parent, bg=PANEL)
        links.pack(fill="x", pady=2)
        self._button(links, "Criar bot ↗", lambda: webbrowser.open("https://t.me/BotFather")).pack(side="left", padx=(0, 7))
        self._button(links, "Encontrar meu ID ↗", lambda: webbrowser.open("https://t.me/userinfobot")).pack(side="left")
        self._button(parent, "💾  Salvar configurações", self._save, accent=True).pack(fill="x", pady=(8, 6))
        self._button(parent, "🔌  Testar conexão com Telegram", self._test).pack(fill="x")

    def _stat(self, parent, title, variable, column):
        card = tk.Frame(parent, bg=CARD, padx=12, pady=10)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column < 2 else 0)
        tk.Label(card, text=title, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(card, textvariable=variable, bg=CARD, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")

    def _right(self, parent):
        self._section(parent, "02  Central de monitoramento",
                      "Acompanhe cada consulta, a conexão ao DOU e a entrega dos alertas.")
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=(0, 14))
        row.grid_columnconfigure((0, 1, 2), weight=1)
        self._stat(row, "Resultados DOU", self.total_var, 0)
        self._stat(row, "Salvos", self.saved_var, 1)
        self._stat(row, "Alertas pendentes", self.pending_var, 2)
        tk.Label(parent, textvariable=self.last_var, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), pady=5).pack(anchor="w")
        tk.Label(parent, text="CONCURSOS ABERTOS · LISTA DO PORTAL", bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 10, "bold"), pady=5).pack(anchor="w")
        tk.Label(parent, textvariable=self.contests_var, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 11, "bold"), pady=3).pack(anchor="w")
        self._button(parent, "🌎  Abrir concursos nacionais ↗",
                     lambda: webbrowser.open(listing_url("BR"))).pack(side="top", anchor="w", pady=(4,8))

        run = tk.Frame(parent, bg=PANEL)
        run.pack(fill="x", pady=(10, 14))
        self.start_btn = self._button(run, "▶  Ativar radar", self._start, accent=True)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.stop_btn = self._button(run, "■  Desligar", self._stop_service)
        self.stop_btn.pack(side="left", padx=5)
        self.check_btn = self._button(run, "↻  Conferir agora", self._check)
        self.check_btn.pack(side="left", padx=(5, 0))
        self.stop_btn.configure(state="disabled")
        self.check_btn.configure(state="disabled")
        if self._instance is not None:
            tk.Label(parent, text="Fechar a janela mantém o Radar na bandeja. Use o ícone para sair.",
                     bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                     wraplength=470, justify="left").pack(anchor="w")
        console_title = tk.Frame(parent, bg=PANEL)
        console_title.pack(fill="x", pady=(5, 8))
        tk.Label(console_title, text="REGISTRO DE ATIVIDADES", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._button(console_title, "Limpar tela", self._clear_logs).pack(side="right")
        self._button(console_title, "Abrir DOU ↗", self._open_dou).pack(side="right", padx=(0, 7))
        logs = tk.Frame(parent, bg=BG, highlightbackground=BORDER, highlightthickness=1)
        logs.pack(fill="both", expand=True)
        self.log_view = tk.Text(logs, bg=BG, fg="#b7e0cf", insertbackground=TEXT,
                                font=("Consolas", 9), relief="flat", wrap="word",
                                borderwidth=0, state="disabled", padx=12, pady=12)
        scroller = ttk.Scrollbar(logs, orient="vertical", command=self.log_view.yview)
        self.log_view.configure(yscrollcommand=scroller.set)
        scroller.pack(side="right", fill="y")
        self.log_view.pack(side="left", fill="both", expand=True)
        self.log_view.tag_configure("error", foreground=RED)
        self.log_view.tag_configure("warning", foreground=YELLOW)
        self.log_view.tag_configure("info", foreground="#b7e0cf")

    def _toggle_secret(self):
        now_visible = self._token_entry.cget("show") == ""
        self._token_entry.configure(show="•" if now_visible else "")

    def _load_persisted(self):
        try:
            config = load_settings()
        except ValueError as exc:
            self.log.error("Configuração local inválida: %s", exc)
            return
        if config:
            self._logged_token = config.token
            self.name_var.set(config.name)
            self.chat_var.set(str(config.telegram_id))
            self.token_var.set(config.token)
            self.interval_var.set(str(config.interval_minutes))
            self.dou_enabled_var.set(config.monitor_dou)
            self.contests_enabled_var.set(config.monitor_concursos)
            self.start_with_windows_var.set(config.start_with_windows)
            self.uf_var.set(config.uf if config.uf else "Somente nacional")
            self.state_var.set("Configuração recuperada")
            self.log.info("Configurações anteriores carregadas.")
        else:
            self.log.info("Bem-vindo! Preencha os campos à esquerda para iniciar.")
        self._refresh_dashboard()
        return config

    def _load_previous_logs(self):
        path = log_file()
        try:
            # Somente as últimas linhas, evitando travar com arquivos grandes.
            lines = path.read_text(encoding="utf-8").splitlines()[-70:]
            for line in lines:
                self._append_line(line, "info")
        except (OSError, UnicodeError):
            pass

    def _values(self):
        try:
            telegram_id = int(self.chat_var.get().strip())
            interval = int(self.interval_var.get())
        except ValueError:
            messagebox.showerror("Verifique os dados",
                                 "Informe o ID do Telegram e o intervalo em números inteiros.",
                                 parent=self)
            return None
        try:
            uf = self.uf_var.get().strip().upper()
            if uf == "SOMENTE NACIONAL":
                uf = ""
            return AppConfig(self.name_var.get(), telegram_id,
                             self.token_var.get().strip(), interval,
                             uf=uf, monitor_dou=self.dou_enabled_var.get(),
                             monitor_concursos=self.contests_enabled_var.get(),
                             start_with_windows=self.start_with_windows_var.get()).validated()
        except ValueError as exc:
            messagebox.showerror("Verifique os dados", str(exc), parent=self)
            return None

    def _save(self):
        if self._service and self._service.busy:
            messagebox.showinfo("Monitoramento em andamento",
                                "Desligue o radar antes de modificar as configurações.", parent=self)
            return None
        config = self._values()
        if not config:
            return None
        try:
            save_settings(config)
        except (OSError, ValueError):
            messagebox.showerror("Falha ao salvar",
                                 "Confira se a pasta de dados do Radar aceita gravação.",
                                 parent=self)
            return None
        self._logged_token = config.token
        self.state_var.set("Configuração salva")
        self.log.info("Configuração salva localmente.")
        if self._instance is not None:
            from .windows import set_start_with_windows
            try:
                set_start_with_windows(config.start_with_windows)
            except OSError:
                messagebox.showwarning(
                    "Inicialização do Windows",
                    "As configurações foram salvas. O Windows recusou a atualização da inicialização automática.",
                    parent=self,
                )
        self._refresh_dashboard()
        return config

    def _start(self):
        config = self._save()
        if config is not None:
            self._start_monitor(config)

    def _start_monitor(self, config):
        try:
            from .service import RadarService
            self._service = RadarService(config)
            self._service.start()
        except Exception as exc:
            self.log.error("Não foi possível iniciar: %s", type(exc).__name__)
            self.state_var.set("Falha ao iniciar o radar")
            self._restore_window()
            return
        self._last_busy = True
        self._stop_requested = False
        self.state_var.set("Conectando...")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log.info("Iniciando o serviço de monitoramento...")

    def _stop_service(self):
        if self._service and self._service.busy:
            self._stop_requested = True
            self._service.stop()
            self.state_var.set("Desligando com segurança...")
            self.stop_btn.configure(state="disabled")

    def _check(self):
        if self._service and self._service.check_now():
            self.log.info("Consulta manual solicitada pela interface.")
        else:
            self.log.warning("Ative o radar antes de consultar manualmente.")

    def _test(self):
        config = self._values()
        if not config:
            return
        self.log.info("Testando autenticação e envio de uma mensagem ao seu Telegram...")
        def job():
            try:
                from .service import test_credentials
                test_credentials(config)
                self._events.put(("test_ok", "A mensagem de teste foi entregue no Telegram.", logging.INFO))
            except Exception:
                self._events.put(("test_error",
                                  "Confira o token, o ID e se você enviou /start ao bot.",
                                  logging.ERROR))
        threading.Thread(target=job, name="testar-telegram", daemon=True).start()

    def _open_dou(self):
        term = " ".join(self.name_var.get().split())
        if term:
            from urllib.parse import urlencode
            from .scraper import search_parameters
            try:
                url = SEARCH_ENDPOINT + "?" + urlencode(search_parameters(term))
            except ValueError:
                url = SEARCH_ENDPOINT
        else:
            url = SEARCH_ENDPOINT
        webbrowser.open(url)

    def _append_line(self, message, tag):
        view = self.log_view
        view.configure(state="normal")
        view.insert("end", message + "\n", tag)
        # Conserva apenas os últimos 500 registros visíveis.
        if int(view.index("end-1c").split(".")[0]) > 500:
            view.delete("1.0", "60.0")
        view.see("end")
        view.configure(state="disabled")

    def _clear_logs(self):
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.configure(state="disabled")
        self.log.info("Janela de logs limpa. O arquivo de histórico foi mantido no computador.")

    def _refresh_dashboard(self):
        try:
            telegram_id = int(self.chat_var.get())
        except ValueError:
            return
        contests = read_contest_dashboard(database_file(), telegram_id)
        national = contests.get("BR", {})
        uf = self.uf_var.get()
        region = contests.get(uf, {}) if uf in UF_NAMES else {}
        uf_name = uf if uf in UF_NAMES else "UF"
        self.contests_var.set(f"🌎 Nacional: {national.get('current', '—')}  |  "
                              f"📍 {uf_name}: {region.get('current', '—')}")
        data = read_dashboard(database_file(), telegram_id)
        if not data:
            self.total_var.set("—")
            self.saved_var.set("—")
            self.pending_var.set("—")
            self.last_var.set("Ainda não há histórico para este ID")
            return
        self.total_var.set(str(data.get("result_total") if data.get("result_total") is not None else "—"))
        self.saved_var.set(str(data.get("saved", 0)))
        self.pending_var.set(str(data.get("pending", 0)))
        self.last_var.set("Última consulta: " + friendly_timestamp(data.get("last_success")))

    def _pump(self):
        for _ in range(150):
            try:
                typ, msg, level = self._events.get_nowait()
            except queue.Empty:
                break
            if typ == "log":
                tag = "error" if level >= logging.ERROR else "warning" if level >= logging.WARNING else "info"
                self._append_line(msg, tag)
            elif typ == "test_ok":
                self.log.info(msg)
                messagebox.showinfo("Telegram conectado", msg, parent=self)
            elif typ == "test_error":
                self.log.error(msg)
                messagebox.showerror("Não foi possível enviar", msg, parent=self)
            elif typ == "tray_ready":
                self._tray_ready = True
            elif typ == "tray_unavailable":
                self._tray_ready = False
                self.log.warning("O ícone da bandeja ficou indisponível.")
                if not self._closing:
                    self._restore_window()
            elif typ == "tray_open":
                self._restore_window()
            elif typ == "tray_quit":
                self._quit()
        if self._instance is not None and self._instance.window_requested() and not self._closing:
            self._restore_window()
        active = bool(self._service and self._service.running)
        busy = bool(self._service and self._service.busy)
        if active and not self._last_running:
            self.state_var.set("● Radar em funcionamento")
            self.check_btn.configure(state="normal")
        elif self._last_busy and not busy:
            self.state_var.set("Radar desligado" if self._stop_requested
                               else "Radar interrompido. Consulte o registro.")
            self.check_btn.configure(state="disabled")
        self._last_running = active
        self._last_busy = busy
        if not busy:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
        if self._closing and not busy:
            self.destroy()
            return
        self._ticks += 1
        if self._ticks % 12 == 0:
            self._refresh_dashboard()
        self.after(250, self._pump)

    def _close(self):
        if self._tray_ready and not self._closing:
            self.withdraw()
            return
        self._quit()

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit(self):
        if self._closing:
            return
        if self._service and self._service.busy:
            self._restore_window()
            if not messagebox.askyesno("Encerrar o Radar DOU?",
                    "Sair interrompe o monitoramento. Deseja encerrar?", parent=self):
                return
            self._closing = True
            self._stop_service()
        else:
            self._closing = True

    def report_callback_exception(self, exc_type, _value, _traceback):
        self.log.error("Erro na interface (%s).", exc_type.__name__)
        if self._smoke:
            self.smoke_result = 6
            self.destroy()

    def smoke_gui(self):
        """Verifica janela real, fechamento para a bandeja e reabertura."""
        deadline = time.monotonic() + 15

        def wait_for(ready, action):
            if ready():
                action()
            elif time.monotonic() >= deadline:
                self.smoke_result = 7
                self.destroy()
            else:
                self.after(100, wait_for, ready, action)

        def exercise_tray():
            from .windows import WindowsInstance
            self._close()
            if self.state() != "withdrawn":
                raise RuntimeError("A janela não foi para a bandeja")
            with WindowsInstance() as duplicate:
                if duplicate.primary:
                    raise RuntimeError("Outra instância pôde ser iniciada")
                duplicate.request_window()
            wait_for(self.winfo_viewable, self.destroy)

        wait_for(lambda: self.winfo_viewable()
                 and (self._instance is None or self._tray_ready),
                 self.destroy if self._instance is None else exercise_tray)


def main(*, background=False, smoke=False):
    if smoke and not os.environ.get("RADAR_DOU_HOME"):
        return 5
    if sys.platform == "win32":
        from .windows import WindowsInstance
        instance_context = WindowsInstance()
    else:
        instance_context = nullcontext()
    with instance_context as instance:
        if instance is not None and not instance.primary:
            if not background and not smoke:
                instance.request_window()
            return 8 if smoke else 0
        app = RadarApp(instance=instance, background=background and not smoke, smoke=smoke)
        try:
            if smoke:
                app.after(100, app.smoke_gui)
            app.mainloop()
            return app.smoke_result
        finally:
            if app._tray:
                app._tray.close()
            for handler in list(app.log.handlers):
                app.log.removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    main()
