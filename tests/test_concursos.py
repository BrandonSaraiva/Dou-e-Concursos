"""Cobertura do catálogo sem internet; HTML inspirado nas tabelas enviadas pelo usuário."""
import sqlite3
import pytest

from radar_dou.concursos import (
    Concurso, ConcursoSnapshot, ConcursoError, parse_concursos_html,
    canonical_url, listing_url, UF_NAMES,
)
from radar_dou.database import Store, read_contest_dashboard
from radar_dou.settings import AppConfig, save_settings, load_settings
from radar_dou.service import contest_card

FAKE_TOKEN = "123456789:THIS_IS_A_DEMONSTRATION_TOKEN_ONLY"

NATIONAL = """<main class='taxonomy' id='conteudo'>
<h1>Concursos Brasil</h1><h2>Concursos Públicos Abertos Brasil</h2>
<table><thead><tr><th>Órgão</th><th>Vagas</th></tr></thead><tbody>
<tr><td><a class='post-title post-url' href='https://concursosnobrasil.com/concurso-ibge/'
 title='Concurso IBGE com novas vagas'>IBGE</a></td><td>27.279</td></tr>
<tr class='previsto'><td><a class='post-title post-url' href='/concursos/anpd/'
 title='Concurso ANPD previsto'>ANPD <b>previsto</b></a></td><td>50</td></tr>
</tbody></table></main>"""

DF = """<main class='taxonomy' id='conteudo'>
<h1>Concursos Distrito Federal</h1><h2>Concursos Públicos Abertos Distrito Federal</h2>
<table><tbody>
<tr><td><a class='post-title post-url'
 href='/concursos/df/2026/11/10/ancine-abre-cadastro-reserva-para-estagio-de-nivel-superior/'
 title='ANCINE abre cadastro reserva de estágio'>ANCINE</a></td><td>Várias</td></tr>
<tr><td><a class='post-title post-url'
 href='/concursos/df/2026/10/26/concurso-dpdf-oferta-mais-de-700-vagas-com-iniciais-de-r-11-mil/'
 title='Concurso DPDF'>DPDF</a></td><td>707</td></tr>
<tr class='destaque'><td><a class='post-title post-url'
 href='https://concursosnobrasil.com/concurso-ibge/'
 title='Concurso IBGE com novas vagas'>IBGE</a></td><td>27.279</td></tr>
<tr><td><a class='post-title post-url' href='/concursos/df/sesdf/'
 title='SES DF previsto'>SES DF <span class='previsto'>previsto</span></a></td><td>300</td></tr>
</tbody></table></main>"""


def test_parse_national_only_open_no_predicted():
    data = parse_concursos_html(NATIONAL,"BR")
    assert len(data.contests) == 1
    assert data.contests[0].organization == "IBGE"
    assert data.contests[0].vacancies == "27.279"
    assert data.contests[0].url == "https://concursosnobrasil.com/concurso-ibge/"


def test_parse_state_open_and_skip_predicted():
    data = parse_concursos_html(DF, "DF")
    assert len(data.contests) == 3
    assert {x.organization for x in data.contests} == {"ANCINE", "DPDF", "IBGE"}
    assert [x.vacancies for x in data.contests if x.organization=="ANCINE"] == ["Várias"]


def test_bad_html_and_wrong_region_dont_wipe_data():
    with pytest.raises(ConcursoError):
        parse_concursos_html("<html><title>Blocked</title></html>","DF")
    with pytest.raises(ConcursoError):
        parse_concursos_html(NATIONAL,"DF")
    # O layout do site pode mudar as classes; manter a capacidade de identificar os links.
    assert len(parse_concursos_html(DF.replace("post-title", "unknown-class"),"DF").contests) == 3
    with pytest.raises(ConcursoError):
        parse_concursos_html(DF,"DF",page_url="https://concursosnobrasil.com/concursos/")
    with pytest.raises(ConcursoError):
        canonical_url("https://evil.example/data")


def test_all_states_have_distinct_urls():
    assert len(UF_NAMES) == 27
    assert len({listing_url(x) for x in UF_NAMES}) == 27
    assert listing_url("BR").endswith("/br/")


def test_contest_baseline_new_persist_and_reappear(tmp_path):
    path = tmp_path / "radar.sqlite"
    first = parse_concursos_html(DF,"DF")
    store=Store(path)
    assert store.ingest_contests(123, first) == (3,True)
    assert store.contest_counts(123,"DF") == (3,0)
    # Simula fim de uma divulgação; não apagar histórico.
    subset = ConcursoSnapshot("DF",tuple(first.contests[:2]),first.page_url)
    assert store.ingest_contests(123,subset) == (0,False)
    assert store.contest_counts(123,"DF")== (2,0)
    # O concurso conhecido retorna: NÃO é novidade novamente.
    assert store.ingest_contests(123,first) == (0,False)
    assert store.contest_counts(123,"DF")== (3,0)
    new = Concurso("ANPD", "50", "Concurso ANPD aberto", "https://concursosnobrasil.com/concursos/anpd/")
    second = ConcursoSnapshot("DF",(*first.contests,new),first.page_url)
    assert store.ingest_contests(123,second) == (1,False)
    assert store.contest_counts(123,"DF") == (4,1)
    assert len(store.pending_contests(123))==1
    store.close()
    store=Store(path)
    assert store.contest_counts(123,"DF")== (4,1)
    store.mark_contest_send_error(123,"DF",new.url,"Erro de Telegram")
    assert store.contest_counts(123,"DF")== (4,1)
    store.mark_contest_sent(123,"DF",new.url)
    assert store.contest_counts(123,"DF")== (4,0)
    store.close()
    assert read_contest_dashboard(path,123)["DF"]["current"] == 4


def test_contest_error_keeps_last_success(tmp_path):
    db=Store(tmp_path/"t.sqlite")
    db.ingest_contests(1,parse_concursos_html(NATIONAL,"BR"))
    before=db.contest_status(1,"BR")["last_success"]
    db.set_contests_error(1,"BR","HTTP 503")
    st=db.contest_status(1,"BR")
    assert st["last_success"] == before and st["last_error"] == "HTTP 503"
    assert db.contest_counts(1,"BR")== (1,0)
    db.close()


def test_state_and_national_baselines_independent(tmp_path):
    db=Store(tmp_path/"t.sqlite")
    national=parse_concursos_html(NATIONAL,"BR")
    df=parse_concursos_html(DF,"DF")
    df_only=ConcursoSnapshot("DF", tuple(x for x in df.contests
                          if x.url not in {n.url for n in national.contests}),df.page_url)
    assert len(df_only.contests)==2
    assert db.ingest_contests(1,national)==(1,True)
    assert db.ingest_contests(1,df_only)==(2,True)
    assert db.contest_counts(1,"BR")== (1,0)
    assert db.contest_counts(1,"DF")== (2,0)
    assert db.ingest_contests(2,national)==(1,True)
    db.close()


def test_custom_uf_and_config_migration(monkeypatch,tmp_path):
    monkeypatch.setenv("RADAR_DOU_HOME",str(tmp_path))
    config=AppConfig("",4,FAKE_TOKEN,60,"RS",False,True).validated()
    save_settings(config)
    assert load_settings()==config
    assert "monitor_concursos" in (tmp_path / "config.json").read_text()
    with pytest.raises(ValueError,match="UF"):
        AppConfig("nome",4,FAKE_TOKEN,60,"XX",True,True).validated()
    with pytest.raises(ValueError,match="Ative"):
        AppConfig("",4,FAKE_TOKEN,60,"",False,False).validated()
    import json
    p=tmp_path / "config.json"
    old=json.loads(p.read_text())
    for key in ("monitor_dou","monitor_concursos","uf"):
        old.pop(key,None)
    old["version"] = 2
    old["name"] = "Maria da Silva"
    p.write_text(json.dumps(old))
    loaded=load_settings()
    assert loaded.name=="Maria da Silva" and loaded.monitor_dou and loaded.monitor_concursos
    assert loaded.uf==""


def test_card_escapes_html():
    entry={"scope":"DF","organization":"Órgão <br>",
            "vacancies":"2 & cadastro","title":"Seleção <script>"}
    card=contest_card(entry)
    assert "&lt;script&gt;" in card and "&lt;br&gt;" in card
    assert "2 &amp; cadastro" in card


def test_change_scope_keeps_old_history(tmp_path):
    db=Store(tmp_path/"t.sqlite")
    df=ConcursoSnapshot("DF",(Concurso("DF", "1", "Edital 1", "https://concursosnobrasil.com/concursos/df/a/"),),listing_url("DF"))
    go=ConcursoSnapshot("GO",(Concurso("GO", "2", "Edital 2", "https://concursosnobrasil.com/concursos/go/a/"),),listing_url("GO"))
    db.ingest_contests(3,df)
    db.ingest_contests(3,go)
    assert db.contest_counts(3,"DF")== (1,0)
    assert db.contest_counts(3,"GO")== (1,0)
    db.close()


def test_new_state_does_not_send_pending_old_state(tmp_path):
    db = Store(tmp_path / "monitor.sqlite")
    initial = ConcursoSnapshot("DF", (Concurso("A", "1", "A", "https://concursosnobrasil.com/concursos/df/a/"),), listing_url("DF"))
    more = ConcursoSnapshot("DF", (*initial.contests, Concurso("B","2","B","https://concursosnobrasil.com/concursos/df/b/")), listing_url("DF"))
    db.ingest_contests(22, initial)
    db.ingest_contests(22, more)
    assert len(db.pending_contests(22,scopes=("BR","DF"))) == 1
    assert len(db.pending_contests(22,scopes=("BR","GO"))) == 0
    db.close()


def test_move_between_categories_does_not_send_same_url_twice(tmp_path):
    db=Store(tmp_path/"monitor.sqlite")
    published=Concurso("IBGE", "27.279", "Concurso IBGE", "https://concursosnobrasil.com/concurso-ibge/")
    first=ConcursoSnapshot("BR", (published,), listing_url("BR"))
    local=ConcursoSnapshot("DF", (published,), listing_url("DF"))
    db.ingest_contests(123,first)
    db.ingest_contests(123,ConcursoSnapshot("DF",(),listing_url("DF")))
    assert db.ingest_contests(123,local)==(1,False)
    assert db.contest_counts(123,"DF")==(1,0)
    db.close()


# Regressão do erro reportado em 19/11/2026: categorias sem table/post-title.
CARD_LAYOUT = """<main id="conteudo" class="taxonomy">
<h1>Concursos Distrito Federal</h1>
<h2>Concursos Públicos Abertos Distrito Federal</h2>
<div class="cards-grid">
 <div class="card"><div class="organization"><a href="/concursos/df/2026/11/18/camara-do-df-lanca-edital/" title="Edital Câmara DF">Câmara do DF</a></div><span class="vagas">Vagas: 50</span></div>
 <div class="card"><a href="/concursos/df/2026/11/19/defensoria-edital/">Defensoria Pública</a><div class="vacancies">Várias</div></div>
</div>
<h2>Concursos Públicos Previstos Distrito Federal</h2>
<div class="card"><a href="/concursos/df/2026/11/19/previsto/">Concurso previsto</a><span>999 vagas</span></div>
</main>"""


def test_regression_card_grid_without_table_or_post_title():
    snapshot = parse_concursos_html(CARD_LAYOUT,"DF")
    assert [(x.organization,x.vacancies) for x in snapshot.contests] == [
        ("Câmara do DF", "50"), ("Defensoria Pública", "Várias")
    ]
    assert not any("previsto" in x.url for x in snapshot.contests)


def test_regression_multiple_tables_in_open_section():
    html = NATIONAL.replace(
        "</tbody></table></main>",
        "</tbody></table><h3>Outros concursos abertos</h3>"
        "<table><tbody><tr><td><a href='/concursos/2026/11/19/novo/' title='Novo concurso'>Ministério</a></td><td>123</td></tr>"
        "</tbody></table><h2>Concursos previstos</h2><table><tbody>"
        "<tr><td><a href='/concursos/2026/11/19/previsto/'>Previsto</a></td><td>99</td></tr>"
        "</tbody></table></main>",
    )
    snap = parse_concursos_html(html,"BR")
    assert {x.organization for x in snap.contests} == {"IBGE", "Ministério"}


def test_regression_changed_layout_still_preserves_database_history(tmp_path):
    store=Store(tmp_path/"t.sqlite")
    first=parse_concursos_html(DF,"DF")
    store.ingest_contests(1,first)
    before=store.contest_counts(1,"DF")
    with pytest.raises(ConcursoError):
        parse_concursos_html("<main class='taxonomy'><h1>Concursos Distrito Federal</h1>"
            "<h2>Concursos Públicos Abertos Distrito Federal</h2>"
            "<script>window.loading=true</script></main>","DF")
    assert store.contest_counts(1,"DF") == before
    store.close()


def test_regression_avoid_navigation_as_contest():
    html = CARD_LAYOUT.replace(
        "<h2>Concursos Públicos Previstos",
        "<a href='/concursos/df/page/2/'>Próxima página</a>"
        "<a href='/concursos/df/'>Ver todos</a>"
        "<h2>Concursos Públicos Previstos",
    )
    assert len(parse_concursos_html(html, "DF").contests) == 2


@pytest.mark.parametrize("scope, html, expected", [("BR", NATIONAL, 1), ("DF", CARD_LAYOUT, 2)])
def test_client_fetch_end_to_end_fake_http(monkeypatch, scope, html, expected):
    from radar_dou.concursos import ConcursoClient, listing_url

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=UTF-8"}
        text = html
        content = html.encode("utf-8")
        url = listing_url(scope)

        def raise_for_status(self):
            return None

    client = ConcursoClient()
    seen = []

    def get(url, timeout):
        seen.append(url)
        return FakeResponse()

    monkeypatch.setattr(client.session, "get", get)
    result = client.fetch(scope)
    assert result.scope == scope
    assert len(result.contests) == expected
    assert seen == [listing_url(scope)]


def test_browser_fallback_when_html_changes(monkeypatch):
    from radar_dou.concursos import ConcursoClient
    client = ConcursoClient(browser_fallback=True)
    events = []
    def http(_):
        events.append("http")
        raise ConcursoError("HTML incompleto")
    def browser(_):
        events.append("browser")
        return parse_concursos_html(CARD_LAYOUT,"DF")
    monkeypatch.setattr(client, "_fetch_http", http)
    monkeypatch.setattr(client, "_fetch_browser", browser)
    result = client.fetch("DF")
    assert events == ["http", "browser"]
    assert len(result.contests) == 2


def test_android_http_only_does_not_attempt_browser(monkeypatch):
    from radar_dou.concursos import ConcursoClient
    client = ConcursoClient(browser_fallback=False)
    monkeypatch.setattr(client, "_fetch_http", lambda _:
                        (_ for _ in ()).throw(ConcursoError("layout mudou")))
    monkeypatch.setattr(client, "_fetch_browser", lambda _:
                        (_ for _ in ()).throw(AssertionError("não pode abrir browser")))
    with pytest.raises(ConcursoError, match="layout mudou"):
        client.fetch("DF")


def test_failed_browser_does_not_return_fake_zero(monkeypatch):
    from radar_dou.concursos import ConcursoClient
    client = ConcursoClient(browser_fallback=True)
    monkeypatch.setattr(client, "_fetch_http", lambda _:
                        (_ for _ in ()).throw(ConcursoError("portal bloqueou HTML")))
    monkeypatch.setattr(client, "_fetch_browser", lambda _:
                        (_ for _ in ()).throw(ConcursoError("Edge indisponível")))
    with pytest.raises(ConcursoError, match="Histórico preservado"):
        client.fetch("BR")
