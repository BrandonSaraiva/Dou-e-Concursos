"""Mensagens Telegram formatadas; saída HTML escapada."""
from datetime import datetime, timedelta, timezone
from html import escape
import json

BRT = timezone(timedelta(hours=-3))


def safe(value, limit: int | None = None) -> str:
    text = str(value if value not in (None, "") else "Não informado")
    if limit is not None and len(text) > limit:
        text = text[:limit - 1].rstrip() + "…"
    return escape(text, quote=True)


def message_lines(lines: list[str], limit: int = 3700) -> str:
    """Limita o HTML sem cortar entidades escapadas, tags ou links ao meio."""
    chunks = []
    length = 0
    for line in lines:
        length += len(line) + 1
        if length > limit:
            break
        chunks.append(line)
    return "\n".join(chunks)


def friendly_timestamp(value: str | None) -> str:
    if not value:
        return "Ainda não realizada"
    try:
        return datetime.fromisoformat(value).astimezone(BRT).strftime("%d/%m/%Y às %H:%M")
    except (TypeError, ValueError):
        return "Não disponível"


def publication_card(pub, number: int | None = None) -> str:
    try:
        hierarchy_items = json.loads(pub["hierarchy_json"] or "[]")
    except (ValueError, TypeError):
        hierarchy_items = []
    hierarchy = " › ".join(map(str, hierarchy_items)) if isinstance(hierarchy_items, list) else ""
    snippet = pub["snippet"] or "Sem trecho disponível no resultado."
    no = f" • {number}" if number else ""
    return (f"<b>📰 NOVA PUBLICAÇÃO NO DOU{no}</b>\n\n"
            f"<b>{safe(pub['title'], 240)}</b>\n\n"
            f"📅 <b>Data:</b> {safe(pub['pub_date'], 30)}\n"
            f"🏛 <b>Órgão:</b> {safe(pub['organization'], 160)}\n"
            f"📑 <b>Local:</b> {safe(pub['section'], 100)} · Edição {safe(pub['edition'], 30)} · pág. {safe(pub['page'], 30)}\n"
            f"🏷 <b>Tipo:</b> {safe(pub['act_type'], 100)}\n"
            + (f"🔎 <b>Vinculação:</b> {safe(hierarchy, 180)}\n" if hierarchy else "")
            + f"\n<b>Trecho da busca</b>\n{safe(snippet, 1100)}\n\n"
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
