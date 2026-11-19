"""Consulta as listagens *abertas* do portal Concursos no Brasil.

Fonte editorial independente, NÃO é um edital oficial nem certifica inscrições
vigentes. Um HTML inválido/bloqueado deve falhar sem alterar o histórico local.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://concursosnobrasil.com"
INDEX = BASE + "/concursos/"
UF_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}
LOG = logging.getLogger("radar_dou.concursos")


class ConcursoError(RuntimeError):
    """Falha de acesso ou leitura; não modificar dados persistentes."""


@dataclass(frozen=True)
class Concurso:
    organization: str
    vacancies: str
    title: str
    url: str


@dataclass(frozen=True)
class ConcursoSnapshot:
    scope: str  # 'BR' ou sigla UF
    contests: tuple[Concurso, ...]
    page_url: str


def listing_url(scope: str) -> str:
    scope = scope.upper()
    if scope != "BR" and scope not in UF_NAMES:
        raise ValueError("UF inválida")
    return INDEX + scope.lower() + "/"


def canonical_url(value: str) -> str:
    url = urlsplit(urljoin(BASE, value))
    if url.scheme != "https" or url.hostname not in ("concursosnobrasil.com", "www.concursosnobrasil.com"):
        raise ConcursoError("Link de concurso fora do domínio esperado")
    if not url.path.startswith("/") or url.path == "/":
        raise ConcursoError("Link de concurso inválido")
    path = url.path.rstrip("/") + "/"
    return urlunsplit(("https", "concursosnobrasil.com", path, "", ""))


def _clean(text: str) -> str:
    return " ".join(unescape(text).split())


def _is_forecast(row) -> bool:
    # "previsto" pode vir como texto ou classe no tema WordPress.
    text = row.get_text(" ", strip=True).casefold()
    if "previsto" in text or "previsão" in text:
        return True
    return any("previst" in str(c).casefold() for tag in [row, *row.find_all(True)] for c in tag.get("class", ()))


_SKIP_HEADING = re.compile(r"previst|concursos por e.mail|receba.*e.mail|newsletter|concursos em sua cidade", re.I)
_VACANCY_LABEL = re.compile(
    r"(?:\bvagas?\s*[:–-]?\s*)(v[aá]rias|cadastro\s+de\s+reserva|\d[\d.,]*)",
    re.I,
)
_VACANCY_STANDALONE = re.compile(r"^(v[aá]rias|cadastro\s+de\s+reserva|\d[\d.,]*)$", re.I)


def _relevant_article_link(anchor: Tag) -> bool:
    """Aceita links editoriais de editais, não a navegação por UFs/paginação."""
    href = anchor.get("href", "")
    if not href or href.startswith(("#", "mailto:", "javascript:")):
        return False
    try:
        url = canonical_url(href)
    except ConcursoError:
        return False
    parts = [v for v in urlsplit(url).path.split("/") if v]
    if not parts or not _clean(anchor.get_text(" ", strip=True)):
        return False
    if parts[0] == "concursos":
        if len(parts) < 3:
            return False
        if any(x in ("page", "previstos", "novos", "abertos", "busca") for x in parts[1:]):
            return False
        return True
    # Alguns concursos possuem página própria fora da estrutura /concursos/.
    return parts[0].startswith(("concurso-", "processo-seletivo-")) and len(parts) == 1


def _forecast_ancestor(anchor: Tag, main: Tag) -> bool:
    """Marcações 'previsto' podem estar no tr, li, div ou no próprio link."""
    current = anchor
    depth = 0
    while current is not None and current is not main and depth < 8:
        classes = " ".join(str(c) for c in current.get("class", ())).casefold()
        if "previst" in classes or "previs" in classes:
            return True
        if current.name in ("tr", "li", "article") and _is_forecast(current):
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return False


def _row_for_anchor(anchor: Tag, main: Tag) -> Tag:
    for tag in ("tr", "li", "article"):
        ancestor = anchor.find_parent(tag)
        if ancestor is not None and main in ancestor.parents:
            return ancestor
    # Cards de categorias WordPress podem ser divs, sem nenhuma <table>.
    candidate = anchor
    for _ in range(4):
        parent = candidate.parent
        if not isinstance(parent, Tag) or parent is main:
            break
        text = _clean(parent.get_text(" ", strip=True))
        if (len(text) < 320 and ("vagas" in text.casefold() or
                parent.find(class_=re.compile("vagas?|vacanc", re.I)) is not None)):
            return parent
        candidate = parent
    return anchor.parent if isinstance(anchor.parent, Tag) else anchor


def _vacancies(anchor: Tag, row: Tag) -> str:
    cells = row.find_all("td", recursive=False) if row.name == "tr" else []
    if len(cells) >= 2:
        value = _clean(cells[-1].get_text(" ", strip=True))
        if value:
            return value
    # HTML em cards/grid: <span class="vagas">6</span>, "Vagas: 6" etc.
    for element in row.find_all(class_=re.compile("vagas?|vacanc", re.I)):
        value = _clean(element.get_text(" ", strip=True))
        found = _VACANCY_LABEL.search(value)
        if found:
            return found.group(1)
        if _VACANCY_STANDALONE.fullmatch(value):
            return value
    value = _clean(row.get_text(" ", strip=True))
    match = _VACANCY_LABEL.search(value)
    if match:
        return match.group(1)
    org = _clean(anchor.get_text(" ", strip=True))
    if value.startswith(org):
        remainder = value[len(org):].strip()
        if _VACANCY_STANDALONE.fullmatch(remainder):
            return remainder
    # Ausência de contagem não transforma um concurso aberto em inexistente.
    return "Não informado"


def _open_section(main: Tag) -> tuple[Tag, list[Tag]]:
    """Isola a seção 'Abertos' independentemente de table, grid, list ou card.

    Páginas /br/ e /UF/ têm uma lista de abertos seguida de outra de
    previstos; nunca misturar as duas. No caso de HTML inválido, falhar
    explicitamente para não substituir o último snapshot íntegro.
    """
    titles = main.find_all(["h2", "h3", "h4"])
    start = next((h for h in titles if re.search(
        r"concursos?\s+(?:p[uú]blicos?\s+)?abertos?",
        h.get_text(" ", strip=True), re.I
    )), None)
    if start is None:
        raise ConcursoError("Título da seção 'Concursos Abertos' não localizado; layout do portal pode ter mudado")
    links: list[Tag] = []
    for element in start.next_elements:
        if not isinstance(element, Tag):
            continue
        if main not in element.parents:
            break
        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6") and _SKIP_HEADING.search(element.get_text(" ", strip=True)):
            break
        if element.name == "a" and element.has_attr("href"):
            links.append(element)
    return start, links


def parse_concursos_html(html: str, scope: str, *, page_url: str = "") -> ConcursoSnapshot:
    """Lê a categoria por UF/BR; suporta tabelas, cards e listas WordPress.

    Não depende de <table> ou da classe post-title: o site pode trocar o
    componente visual mantendo os links e o título semântico dos abertos.
    """
    scope = scope.upper()
    page_url = page_url or listing_url(scope)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main.taxonomy") or soup.select_one("main#conteudo") or soup.select_one("main")
    if main is None:
        raise ConcursoError("Página de concursos sem conteúdo principal (bloqueio ou mudança no site)")
    heading = main.select_one("h1")
    title = heading.get_text(" ", strip=True).casefold() if heading else ""
    if "concurso" not in title:
        raise ConcursoError("Cabeçalho do catálogo de concursos não encontrado")
    # A página-resumo geral é parcial: só exibe até 5 por estado.
    if urlsplit(page_url).path.rstrip("/") == "/concursos":
        raise ConcursoError("Página-resumo não serve para monitorar todos os concursos")
    if scope == "BR":
        if "brasil" not in title and "nacion" not in title:
            raise ConcursoError("A página recebida não corresponde a concursos nacionais")
    else:
        name = UF_NAMES.get(scope)
        if not name:
            raise ValueError("UF inválida")
        if name.casefold() not in title and scope.casefold() not in title.split():
            raise ConcursoError(f"O portal retornou a UF errada (esperado: {name})")
    _, anchors = _open_section(main)
    items: dict[str, Concurso] = {}
    for anchor in anchors:
        if not _relevant_article_link(anchor) or _forecast_ancestor(anchor, main):
            continue
        row = _row_for_anchor(anchor, main)
        if _is_forecast(row):
            continue
        organization = _clean(anchor.get_text(" ", strip=True))
        title_text = _clean(anchor.get("title") or organization)
        url = canonical_url(anchor["href"])
        vacancies = _vacancies(anchor, row)
        if url not in items:
            items[url] = Concurso(organization, vacancies, title_text, url)
    if not items:
        content = _clean(main.get_text(" ", strip=True)).casefold()
        if "nenhum concurso aberto" not in content and "não há concursos abertos" not in content:
            raise ConcursoError(
                f"Seção 'Abertos' reconhecida, mas nenhum concurso foi identificado "
                f"({len(anchors)} links analisados); HTML do portal pode ter mudado. "
                "Histórico preservado"
            )
    LOG.info("Concursos %s: %s abertos reconhecidos por links na seção Abertos (%s âncoras).",
             scope, len(items), len(anchors))
    return ConcursoSnapshot(scope, tuple(items.values()), page_url)


class ConcursoClient:
    def __init__(self, timeout: int = 25, max_pages: int = 12, browser_fallback: bool = True):
        self.timeout = timeout
        self.max_pages = max_pages
        self.browser_fallback = browser_fallback
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RadarDOU/1.2 (+monitoramento publico, 1 consulta/hora; contato via repositorio GitHub)",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
        })
        retry = Retry(total=2, backoff_factor=1, status_forcelist=(429,500,502,503,504),
                      respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    @staticmethod
    def _next_page(html: str, page_url: str, first_url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        next_tag = (soup.select_one("main a.next.page-numbers[href]")
                    or soup.select_one('main a[rel="next"][href]')
                    or soup.select_one('main .pagination a.next[href]')
                    or soup.select_one('head link[rel="next"][href]'))
        if next_tag is None:
            return None
        candidate = urljoin(page_url, next_tag["href"])
        target = urlsplit(candidate)
        if (target.scheme == "https" and
            target.hostname in ("concursosnobrasil.com", "www.concursosnobrasil.com") and
            target.path.startswith(urlsplit(first_url).path + "page/")):
            return candidate
        return None

    def _fetch_http(self, scope: str) -> ConcursoSnapshot:
        scope = scope.upper()
        first_url = listing_url(scope)
        seen_pages = set()
        to_fetch = first_url
        all_items: dict[str, Concurso] = {}
        while to_fetch:
            if len(seen_pages) >= self.max_pages:
                raise ConcursoError("Limite de páginas atingido; não vou gravar uma listagem parcial")
            if to_fetch in seen_pages:
                raise ConcursoError("Paginação circular detectada; listagem não atualizada")
            seen_pages.add(to_fetch)
            try:
                response = self.session.get(to_fetch, timeout=self.timeout)
                response.raise_for_status()
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "desconhecido"
                raise ConcursoError(f"Portal Concursos no Brasil respondeu HTTP {status}") from exc
            except requests.RequestException as exc:
                raise ConcursoError(f"Portal Concursos no Brasil indisponível ({type(exc).__name__})") from exc
            content_type = response.headers.get("Content-Type", "")
            LOG.info("CONCURSOS %s: HTTP %s em %s (%s bytes; tipo %s)",
                     scope, response.status_code, response.url,
                     len(response.content), content_type or "não informado")
            if "text/html" not in content_type.lower():
                raise ConcursoError("Portal não retornou HTML (pode ser bloqueio de acesso)")
            page = parse_concursos_html(response.text, scope, page_url=response.url)
            for item in page.contests:
                all_items[item.url] = item
            LOG.info("Concursos %s: página %s lida (%s abertos).", scope, len(seen_pages), len(page.contests))
            to_fetch = self._next_page(response.text, response.url, first_url)
        return ConcursoSnapshot(scope, tuple(all_items.values()), first_url)

    def _fetch_browser(self, scope: str) -> ConcursoSnapshot:
        """Navegador Edge/Chrome instalado, somente como alternativa no desktop."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ConcursoError("Playwright não está instalado; o navegador alternativo não está disponível") from exc
        first_url = listing_url(scope)
        with sync_playwright() as playwright:
            browser = None
            last_error = None
            for channel in ("msedge", "chrome", None):
                try:
                    kwargs = {"headless": True}
                    if channel:
                        kwargs["channel"] = channel
                    browser = playwright.chromium.launch(**kwargs)
                    break
                except Exception as exc:
                    last_error = exc
            if browser is None:
                raise ConcursoError("Navegador Edge/Chrome/Chromium indisponível") from last_error
            try:
                page = browser.new_page(locale="pt-BR")
                seen = set()
                target = first_url
                items = {}
                while target:
                    if len(seen) >= self.max_pages or target in seen:
                        raise ConcursoError("Navegador: paginação incompleta ou circular; histórico preservado")
                    seen.add(target)
                    page.goto(target, wait_until="domcontentloaded", timeout=self.timeout*1000)
                    page.locator("main").wait_for(state="attached", timeout=self.timeout*1000)
                    html = page.content()
                    result = parse_concursos_html(html, scope, page_url=page.url)
                    items.update((x.url, x) for x in result.contests)
                    LOG.info("CONCURSOS %s: navegador leu página %s (%s abertos).",
                             scope, len(seen), len(result.contests))
                    target = self._next_page(html, page.url, first_url)
                return ConcursoSnapshot(scope, tuple(items.values()), first_url)
            finally:
                browser.close()

    def fetch(self, scope: str) -> ConcursoSnapshot:
        """HTTP primeiro. Se o tema renderizar conteúdo só no browser, tente Edge.

        No Android o fallback é desligado em RadarService, pois não há
        Playwright desktop na distribuição APK.
        """
        try:
            return self._fetch_http(scope)
        except ConcursoError as http_error:
            if not self.browser_fallback:
                raise
            LOG.warning("CONCURSOS %s: leitura HTTP não validada (%s). Tentando navegador oculto.",
                        scope, str(http_error)[:180])
            try:
                return self._fetch_browser(scope)
            except Exception as browser_error:
                raise ConcursoError(
                    f"HTTP: {str(http_error)[:180]}; "
                    f"navegador: {type(browser_error).__name__}: {str(browser_error)[:170]}. "
                    "Histórico preservado"
                ) from browser_error
