"""Consulta pública do DOU; adapta o parser/paginador do projeto concours.

Só devolve Snapshot depois da paginação integral validada. Falhas nunca
substituem um histórico anterior por resultado vazio.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://www.in.gov.br"
SEARCH_ENDPOINT = BASE + "/consulta/-/buscar/dou"
_PUBLICATION_PATH = "/web/dou/-/"
_DOU_HOSTS = ("in.gov.br", "www.in.gov.br")


class ScrapeError(RuntimeError):
    """A consulta não é confiável; nada deve ser gravado."""


@dataclass(frozen=True)
class Publication:
    uid: str
    title: str
    url: str
    pub_date: str
    section: str
    edition: str
    page: str
    organization: str
    hierarchy: tuple[str, ...]
    act_type: str
    snippet: str
    raw: dict


@dataclass(frozen=True)
class Snapshot:
    total: int
    publications: tuple[Publication, ...]
    search_url: str


def search_parameters(name: str, delta: int | None = None) -> dict[str, str]:
    term = " ".join(name.strip().split())
    if len(term) < 3:
        raise ValueError("Informe um nome com pelo menos 3 caracteres")
    # Preserva a expressão exata e o espaço interno da consulta original do usuário.
    params = {"q": f'" {term}"', "s": "todos", "exactDate": "all", "sortType": "0"}
    if delta is not None:
        params["delta"] = str(delta)
    return params


def normalized_text(value: object) -> str:
    return " ".join(unescape(BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)).split())


def _publication_from_json(hit: dict) -> Publication:
    if not isinstance(hit, dict):
        raise ScrapeError("A pesquisa trouxe um registro sem metadados")
    path = urlsplit(str(hit.get("urlTitle") or "").strip())
    slug = unquote(path.path.removeprefix(_PUBLICATION_PATH).lstrip("/"))
    if (not slug or not hit.get("title") or (path.hostname and path.hostname not in _DOU_HOSTS)
            or any(part in ("", ".", "..") for part in slug.split("/"))):
        raise ScrapeError("Resultado sem título/URL, impedindo comparação segura")
    url = BASE + _PUBLICATION_PATH + quote(slug, safe="/-")
    hierarchy = tuple(str(x).strip() for x in (hit.get("hierarchyList") or []) if str(x).strip())
    name = str(hit.get("pubName", "")).strip()
    section = {"DO1": "Seção 1", "DO2": "Seção 2", "DO3": "Seção 3"}.get(name, name)
    return Publication(
        uid=sha256(url.encode("utf-8")).hexdigest(), title=normalized_text(hit.get("title")),
        url=url, pub_date=str(hit.get("pubDate") or "").strip(), section=section,
        edition=str(hit.get("editionNumber") or "").strip(),
        page=str(hit.get("numberPage") or "").strip(),
        organization=hierarchy[-1] if hierarchy else "Não informado", hierarchy=hierarchy,
        act_type=normalized_text(hit.get("artType")), snippet=normalized_text(hit.get("content")),
        raw=hit,
    )


def parse_search_html(html: str, search_url: str = SEARCH_ENDPOINT) -> Snapshot:
    """Lê o JSON incorporado no front-end ou os cartões HTML como fallback."""
    soup = BeautifulSoup(html, "html.parser")
    total_elem = soup.select_one(".search-total-label")
    label = total_elem.get_text(" ", strip=True) if total_elem else ""
    found = re.search(r"([\d.,]+)\s+resultados?", label, flags=re.I)
    total = int(re.sub(r"\D", "", found.group(1))) if found else None
    if total is None and re.search(r"nenhum resultado|0\s+resultado", label, flags=re.I):
        total = 0
    embedded = soup.find("script", id=re.compile(r"Busc[a-zA-Z]*DouPortlet_params$", re.I))
    if embedded is None:
        embedded = soup.find("script", id=lambda v: isinstance(v, str) and "_BuscaDouPortlet_params" in v)
    if embedded is not None:
        try:
            payload = json.loads(embedded.string or embedded.get_text() or "{}")
            hits = payload["jsonArray"]
            if not isinstance(hits, list):
                raise ValueError("jsonArray não é uma lista")
            results = tuple(_publication_from_json(hit) for hit in hits)
        except (ValueError, KeyError, TypeError) as exc:
            raise ScrapeError("O JSON do DOU mudou ou está incompleto") from exc
    else:
        results_list: list[Publication] = []
        for box in soup.select(".resultados-wrapper .resultado"):
            anchor = box.select_one(".title-marker a[href]")
            if anchor is None:
                continue
            hierarchy = [x.get_text(" ", strip=True) for x in box.select(".hierarchy-item-marker")]
            info_el = box.select_one(".publication-info-marker")
            info = info_el.get_text(" ", strip=True) if info_el else ""
            numbers = re.search(r"Edição\s*N[º°o.]?\s*([\d]+)\s+de\s+([\d/]+)\s*-\s*Pág\.?\s*([\d]+)", info, re.I)
            href = urlsplit(urljoin(BASE, anchor["href"]))
            if href.hostname not in _DOU_HOSTS or not href.path.startswith(_PUBLICATION_PATH):
                raise ScrapeError("Resultado do DOU aponta para um endereço inesperado")
            section_el = box.select_one(".secao-marker")
            snippet_el = box.select_one(".abstract-marker")
            raw = {
                "urlTitle": href.path.removeprefix(_PUBLICATION_PATH),
                "title": anchor.get_text(" ", strip=True),
                "pubDate": numbers.group(2) if numbers else "",
                "editionNumber": numbers.group(1) if numbers else "",
                "numberPage": numbers.group(3) if numbers else "",
                "hierarchyList": hierarchy,
                "pubName": section_el.get_text(" ", strip=True) if section_el else "",
                "artType": "", "content": snippet_el.get_text(" ", strip=True) if snippet_el else "",
            }
            results_list.append(_publication_from_json(raw))
        results = tuple(results_list)
    if total is None:
        raise ScrapeError("O DOU não mostrou o contador de resultados (instabilidade, bloqueio ou layout alterado)")
    if len(results) > total:
        raise ScrapeError("O DOU retornou mais registros que o contador")
    if total and not results:
        raise ScrapeError("O DOU informou resultados mas nenhum registro pôde ser lido")
    if len({p.uid for p in results}) != len(results):
        raise ScrapeError("O DOU trouxe URLs duplicadas na mesma página")
    return Snapshot(total=total, publications=results, search_url=search_url)


class DOUClient:
    def __init__(self, timeout: int = 30, max_pages: int = 30,
                 browser_fallback: bool = True, report: Callable[[str], None] | None = None):
        self.timeout = timeout
        self.max_pages = max_pages
        self.browser_fallback = browser_fallback
        self.report = report or (lambda _: None)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        retry = Retry(total=2, connect=2, read=1, backoff_factor=1.5,
                      status_forcelist=(500, 502, 503, 504), respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get_http(self, params: dict) -> Snapshot:
        try:
            response = self.session.get(SEARCH_ENDPOINT, params=params, timeout=self.timeout)
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ScrapeError("O portal não devolveu uma página HTML")
            return parse_search_html(response.text, response.url)
        except requests.RequestException as exc:
            raise ScrapeError(f"Falha HTTP: {type(exc).__name__}") from exc

    def _get_curl(self, params: dict) -> Snapshot:
        if os.name == "nt":
            system_curl = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
            executable = str(system_curl) if system_curl.is_file() else None
        else:
            executable = shutil.which("curl")
        if not executable:
            raise ScrapeError("curl indisponível")
        url = requests.Request("GET", SEARCH_ENDPOINT, params=params).prepare().url
        command = [executable, "--disable", "--silent", "--show-error", "--fail", "--location", "--compressed",
                   "--connect-timeout", "15", "--max-time", str(self.timeout), "--retry", "1",
                   "--header", "Accept-Language: pt-BR,pt;q=0.9",
                   "--user-agent", self.session.headers["User-Agent"], "--config", "-"]
        try:
            # A expressão monitorada passa por stdin, sem ficar na linha de comando.
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                    input=f'url = "{url}"\n',
                                    errors="replace", timeout=self.timeout + 15, check=False,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ScrapeError(f"Falha no curl: {type(exc).__name__}") from exc
        if result.returncode != 0:
            raise ScrapeError(f"curl falhou (código {result.returncode})")
        return parse_search_html(result.stdout, url)

    def _get_browser(self, page, params: dict) -> Snapshot:
        url = requests.Request("GET", SEARCH_ENDPOINT, params=params).prepare().url
        page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
        page.locator(".search-total-label").wait_for(state="attached", timeout=self.timeout * 1000)
        return parse_search_html(page.content(), page.url)

    def _fetch_pages(self, name: str, get_page) -> Snapshot:
        params = search_parameters(name)
        first = get_page(params)
        self.report(f"DOU respondeu: {first.total} resultado(s) anunciado(s) na busca.")
        items = list(first.publications)
        seen = {p.uid for p in items}
        previous = first
        page_num = 1
        while len(items) < first.total:
            if page_num >= self.max_pages:
                raise ScrapeError(f"Busca com mais de {self.max_pages} páginas; histórico preservado")
            if not previous.publications:
                raise ScrapeError("Página vazia antes do fim dos resultados")
            raw = previous.publications[-1].raw
            required = ("classPK", "displayDateSortable", "score")
            if any(k not in raw for k in required):
                raise ScrapeError("Campos de paginação não encontrados no site")
            next_params = {
                **params, "delta": "20", "currentPage": str(page_num),
                "newPage": str(page_num + 1), "score": str(raw["score"]),
                "id": str(raw["classPK"]), "displayDate": str(raw["displayDateSortable"]),
            }
            following = get_page(next_params)
            if following.total != first.total:
                raise ScrapeError("Contagem mudou durante a busca. Nenhum dado atualizado")
            if not following.publications:
                raise ScrapeError("DOU parou de entregar páginas antes do fim")
            fresh = [p for p in following.publications if p.uid not in seen]
            if not fresh:
                raise ScrapeError("DOU repetiu página de resultados; histórico preservado")
            items.extend(fresh)
            seen.update(p.uid for p in fresh)
            previous = following
            page_num += 1
            self.report(f"Página {page_num} conferida: {len(items)}/{first.total} publicação(ões) lidas.")
        if len(items) != first.total:
            raise ScrapeError(f"Busca incompleta ({len(items)}/{first.total}); histórico preservado")
        return Snapshot(total=first.total, publications=tuple(items), search_url=first.search_url)

    def _fetch_with_browser(self, name: str) -> Snapshot:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ScrapeError("Automação do navegador não instalada") from exc
        with sync_playwright() as p:
            browser = None
            for channel in ("msedge", "chrome", None):
                try:
                    options = {"headless": True}
                    if channel:
                        options["channel"] = channel
                    self.report(f"Tentando navegador: {channel or 'Chromium do Playwright'}...")
                    browser = p.chromium.launch(**options)
                    self.report(f"Navegador conectado: {channel or 'Chromium'}.")
                    break
                except Exception:
                    continue
            if browser is None:
                raise ScrapeError("Nenhum navegador compatível disponível. Instale Microsoft Edge ou Chrome")
            try:
                context = browser.new_context(locale="pt-BR")
                try:
                    page = context.new_page()
                    return self._fetch_pages(name, lambda params: self._get_browser(page, params))
                finally:
                    context.close()
            finally:
                browser.close()

    def fetch(self, name: str) -> Snapshot:
        errors = []
        for method, getter in (("conexão direta", self._get_http), ("curl", self._get_curl)):
            self.report(f"Consultando DOU por {method}...")
            try:
                snapshot = self._fetch_pages(name, getter)
                self.report(f"Consulta íntegra pelo método {method}: {len(snapshot.publications)} registro(s).")
                return snapshot
            except ScrapeError as exc:
                errors.append(f"{method}: {str(exc)[:170]}")
                self.report(f"Método {method} indisponível: {exc}")
        if self.browser_fallback:
            self.report("Tentando navegador invisível para recuperar a consulta...")
            try:
                snapshot = self._fetch_with_browser(name)
                self.report("Consulta pelo navegador concluída e validada.")
                return snapshot
            except Exception as exc:
                # O traceback do navegador pode incluir a URL com o nome pesquisado.
                errors.append(f"navegador: {type(exc).__name__}")
        raise ScrapeError("Não foi possível validar a consulta. " + "; ".join(errors) + ". Histórico preservado.")
