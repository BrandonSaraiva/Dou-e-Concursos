"""Mensagens Telegram formatadas; saída HTML escapada."""
from datetime import datetime, timedelta, timezone
from html import escape
import json

BRT = timezone(timedelta(hours=-3))


def safe(value) -> str:
    return escape(str(value if value not in (None, "") else "Não informado"), quote=True)


def friendly_timestamp(value: str | None) -> str:
    if not value:
        return "Ainda não realizada"
    try:
        return datetime.fromisoformat(value).astimezone(BRT).strftime("%d/%m/%Y às %H:%M")
    except (TypeError, ValueError):
        return "Não disponível"


def publication_card(pub, number: int | None = None) -> str:
    hierarchy = " › ".join(str(x) for x in json.loads(pub["hierarchy_json"] or "[]"))
    snippet = str(pub["snippet"] or "Sem trecho disponível no resultado.")
    if len(snippet) > 1100:
        snippet = snippet[:1097].rstrip() + "…"
    no = f" • {number}" if number else ""
    return (f"<b>📰 NOVA PUBLICAÇÃO NO DOU{no}</b>\n\n"
            f"<b>{safe(pub['title'])}</b>\n\n"
            f"📅 <b>Data:</b> {safe(pub['pub_date'])}\n"
            f"🏛 <b>Órgão:</b> {safe(pub['organization'])}\n"
            f"📑 <b>Local:</b> {safe(pub['section'])} · Edição {safe(pub['edition'])} · pág. {safe(pub['page'])}\n"
            f"🏷 <b>Tipo:</b> {safe(pub['act_type'])}\n"
            + (f"🔎 <b>Vinculação:</b> {safe(hierarchy)}\n" if hierarchy else "")
            + f"\n<b>Trecho da busca</b>\n{safe(snippet)}\n\n"
              f"🔗 <a href=\"{safe(pub['url'])}\">Abrir publicação original no DOU</a>")


def status_card(watch, stored: int, pending: int, interval: int) -> str:
    if watch["last_error"]:
        state = "🔴 Falha na última consulta"
    elif watch["last_success"]:
        state = "🟢 Última consulta concluída"
    else:
        state = "🟡 Aguardando primeira consulta"
    return ("<b>📡 RADAR DOU · STATUS</b>\n\n"
            f"{state}\n\n"
            f"👤 <b>Pesquisa:</b> {safe(watch['term'])}\n"
            f"📊 <b>Resultados no DOU:</b> {watch['result_total'] if watch['result_total'] is not None else '—'}\n"
            f"🗄 <b>Publicações armazenadas:</b> {stored}\n"
            f"📬 <b>Alertas pendentes:</b> {pending}\n"
            f"⏱ <b>Intervalo:</b> {interval} min\n"
            f"✅ <b>Última consulta:</b> {friendly_timestamp(watch['last_success'])}\n"
            + (f"\n⚠️ <b>Erro:</b> {safe(watch['last_error'])}" if watch["last_error"] else ""))
