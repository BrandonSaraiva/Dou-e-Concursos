from radar_dou.messages import safe, friendly_timestamp, publication_card
from tests.test_scraper import HTML
from radar_dou.database import Store
from radar_dou.scraper import parse_search_html


def test_message_escapes_html(tmp_path):
    assert safe("<script>&") == "&lt;script&gt;&amp;"
    db = Store(tmp_path / "a.db")
    db.register_admin(123, "Nome Maria")
    w = db.watch(123)
    db.ingest(w["id"], parse_search_html(HTML))
    pub = db.latest(w["id"], 1)[0]
    assert "Abrir publicação original" in publication_card(pub)
    db.close()


def test_friendly_datetime():
    assert friendly_timestamp(None) == "Ainda não realizada"
    assert "2026" in friendly_timestamp("2026-11-19T14:00:00+00:00")
