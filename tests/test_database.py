from radar_dou.database import Store, read_dashboard
from radar_dou.scraper import parse_search_html
from tests.test_scraper import HTML


def test_baseline_restart_and_new_alert(tmp_path):
    dbpath = tmp_path / "radar.sqlite3"
    s = Store(dbpath)
    s.register_admin(1000, "Joana Silva")
    watch = s.watch(1000)
    assert s.ingest(watch["id"], parse_search_html(HTML)) == (2, True)
    assert s.counts(watch["id"]) == (2, 0)
    s.close()
    s = Store(dbpath)
    watch = s.watch(1000)
    assert s.ingest(watch["id"], parse_search_html(HTML)) == (0, False)
    new = HTML.replace("2 resultados", "3 resultados").replace(
        "]}</script>", ',{"urlTitle":"edital-003","title":"NOVA LEI", "pubDate":"20/11/2026",'
        ' "pubName":"DO3","hierarchyList":["Órgão Novo"],"classPK":"3",'
        ' "displayDateSortable":"3","score":0}]}</script>')
    assert s.ingest(watch["id"], parse_search_html(new)) == (1, False)
    assert s.counts(watch["id"]) == (3, 1)
    queued = s.pending(watch["id"])
    assert len(queued) == 1
    s.mark_sent(watch["id"], queued[0]["uid"])
    assert s.counts(watch["id"]) == (3, 0)
    s.close()
    assert read_dashboard(dbpath, 1000)["saved"] == 3


def test_name_change_resets_only_that_monitor(tmp_path):
    s = Store(tmp_path / "sample.sqlite")
    s.register_admin(1111, "Nome Antigo")
    watch = s.watch(1111)
    s.ingest(watch["id"], parse_search_html(HTML))
    s.register_admin(1111, "Nome Novo")
    assert s.watch(1111)["seeded"] == 0
    assert s.counts(watch["id"]) == (0, 0)
    s.close()


def test_changing_chat_id_deactivates_old_monitor(tmp_path):
    s = Store(tmp_path / "sample.sqlite")
    s.register_admin(1111, "Nome A")
    s.register_admin(2222, "Nome B")
    assert len(s.watches()) == 1
    assert s.watches()[0]["telegram_id"] == 2222
    s.close()


def test_error_does_not_erase_previous_success(tmp_path):
    s = Store(tmp_path / "sample.sqlite")
    s.register_admin(1111, "Nome A")
    watch = s.watch(1111)
    s.ingest(watch["id"], parse_search_html(HTML))
    s.set_error(watch["id"], "DOU fora do ar")
    assert s.watch(1111)["result_total"] == 2
    assert s.counts(watch["id"]) == (2, 0)
    s.close()
