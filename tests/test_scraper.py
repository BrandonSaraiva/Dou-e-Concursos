import pytest
from radar_dou.scraper import DOUClient, ScrapeError, parse_search_html, search_parameters

HTML = '''<!doctype html><html><p class="search-total-label">2 resultados para "exemplo"</p>
<script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params" type="application/json">
{"jsonArray": [
{"urlTitle":"edital-001","title":"EDITAL", "pubDate":"19/11/2026", "pubName":"DO3", "editionNumber":"50", "numberPage":"15", "hierarchyList":["Ineditoriais","Órgão Um"], "artType":"Edital", "content":"Nome <span>exemplo</span>", "classPK":"1", "displayDateSortable":"1", "score":0},
{"urlTitle":"edital-002","title":"EDITAL", "pubDate":"18/11/2026", "pubName":"DO3", "editionNumber":"49", "numberPage":"16", "hierarchyList":["Ineditoriais","Órgão Dois"], "artType":"Edital", "content":"Outro nome", "classPK":"2", "displayDateSortable":"2", "score":0}
]}</script></html>'''


def test_json_exact_fields():
    snap = parse_search_html(HTML)
    assert snap.total == 2
    a, b = snap.publications
    assert a.uid != b.uid
    assert a.organization == "Órgão Um"
    assert a.section == "Seção 3"
    assert a.snippet == "Nome exemplo"
    assert a.page == "15"


def test_blocked_layout_does_not_become_empty():
    with pytest.raises(ScrapeError):
        parse_search_html("<html>Access denied</html>")


def test_invalid_count_keeps_history_safe():
    with pytest.raises(ScrapeError):
        parse_search_html(HTML.replace("2 resultados", "1 resultado"))


def test_quoted_search_is_same_as_original_project():
    params = search_parameters("  Maria   da Silva  ")
    assert params == {"q": '" Maria da Silva"', "s": "todos", "exactDate": "all", "sortType": "0"}


def test_no_results_are_valid_only_when_site_confirms():
    html = '<html><p class="search-total-label">0 resultados</p></html>'
    assert parse_search_html(html).total == 0
    assert len(parse_search_html(html).publications) == 0


def test_http_failure_fallback():
    c = DOUClient(browser_fallback=True)
    c._get_http = lambda params: (_ for _ in ()).throw(ScrapeError("Erro HTTP"))
    c._get_curl = lambda params: (_ for _ in ()).throw(ScrapeError("Erro curl"))
    c._fetch_with_browser = lambda name: parse_search_html(HTML)
    assert c.fetch("Nome Exemplo").total == 2


def test_every_method_failing_does_not_return_fake_zero():
    c = DOUClient(browser_fallback=True)
    c._get_http = lambda params: (_ for _ in ()).throw(ScrapeError("RemoteDisconnected"))
    c._get_curl = c._get_http
    c._fetch_with_browser = lambda name: (_ for _ in ()).throw(ScrapeError("Browser bloqueado"))
    with pytest.raises(ScrapeError, match="Histórico preservado"):
        c.fetch("Nome Exemplo")


def test_curl_not_required_for_successful_http():
    c = DOUClient(browser_fallback=False)
    c._get_http = lambda params: parse_search_html(HTML)
    c._get_curl = lambda params: pytest.fail("Não deveria usar curl")
    assert len(c.fetch("Nome Exemplo").publications) == 2


def test_multi_page_validation_and_incremental_log():
    source = HTML.replace("2 resultados", "4 resultados")
    page2 = source.replace("edital-001", "edital-003").replace("edital-002", "edital-004")
    c = DOUClient(browser_fallback=False)
    steps = []
    def fake(params):
        steps.append(params)
        if "currentPage" not in params:
            return parse_search_html(source)
        return parse_search_html(page2)
    result = c._fetch_pages("Nome Exemplo", fake)
    assert result.total == 4
    assert len(result.publications) == 4
    assert steps[1]["currentPage"] == "1"
    assert steps[1]["newPage"] == "2"


def test_repeated_page_raises():
    source = HTML.replace("2 resultados", "4 resultados")
    c = DOUClient(browser_fallback=False)
    with pytest.raises(ScrapeError, match="repetiu"):
        c._fetch_pages("Nome Exemplo", lambda _: parse_search_html(source))
