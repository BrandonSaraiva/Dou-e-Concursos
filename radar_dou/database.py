"""SQLite persistente para a referência de monitoramento e fila de entrega."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .scraper import Snapshot


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS watches (
          id INTEGER PRIMARY KEY, telegram_id INTEGER NOT NULL UNIQUE,
          term TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          seeded INTEGER NOT NULL DEFAULT 0, result_total INTEGER,
          last_success TEXT, last_error TEXT, search_url TEXT
        );
        CREATE TABLE IF NOT EXISTS publications (
          watch_id INTEGER NOT NULL REFERENCES watches(id), uid TEXT NOT NULL,
          title TEXT NOT NULL, url TEXT NOT NULL, pub_date TEXT,
          section TEXT, edition TEXT, page TEXT, organization TEXT,
          hierarchy_json TEXT, act_type TEXT, snippet TEXT, raw_json TEXT,
          first_seen TEXT NOT NULL, PRIMARY KEY (watch_id, uid)
        );
        CREATE TABLE IF NOT EXISTS notifications (
          watch_id INTEGER NOT NULL, uid TEXT NOT NULL, created_at TEXT NOT NULL,
          delivered_at TEXT, attempts INTEGER NOT NULL DEFAULT 0,
          last_error TEXT, PRIMARY KEY (watch_id, uid),
          FOREIGN KEY (watch_id, uid) REFERENCES publications(watch_id, uid)
        );
        CREATE INDEX IF NOT EXISTS ix_pub_watch_date ON publications(watch_id, pub_date);
        CREATE TABLE IF NOT EXISTS contest_watches (
          telegram_id INTEGER NOT NULL, scope TEXT NOT NULL, seeded INTEGER NOT NULL DEFAULT 0,
          result_total INTEGER, last_success TEXT, last_error TEXT,
          PRIMARY KEY (telegram_id, scope)
        );
        CREATE TABLE IF NOT EXISTS contest_entries (
          telegram_id INTEGER NOT NULL, scope TEXT NOT NULL, url TEXT NOT NULL,
          organization TEXT NOT NULL, vacancies TEXT NOT NULL, title TEXT NOT NULL,
          first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
          current INTEGER NOT NULL DEFAULT 1,
          PRIMARY KEY (telegram_id, scope, url)
        );
        CREATE TABLE IF NOT EXISTS contest_notifications (
          telegram_id INTEGER NOT NULL, scope TEXT NOT NULL, url TEXT NOT NULL,
          created_at TEXT NOT NULL, delivered_at TEXT,
          attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
          PRIMARY KEY (telegram_id, scope, url)
        );
        CREATE INDEX IF NOT EXISTS ix_contests_current
          ON contest_entries(telegram_id, scope, current);
        """)
        self.conn.commit()

    def register_admin(self, telegram_id: int, term: str) -> None:
        term = " ".join(term.split())
        old = self.conn.execute("SELECT id,term FROM watches WHERE telegram_id=?", (telegram_id,)).fetchone()
        with self.conn:
            # Este aplicativo é de uma pessoa por instalação, não um bot público multiusuário.
            self.conn.execute("UPDATE watches SET active=0")
            if old is None:
                self.conn.execute("INSERT INTO watches(telegram_id,term,active) VALUES(?,?,1)", (telegram_id, term))
            elif old["term"] != term:
                self.conn.execute("DELETE FROM notifications WHERE watch_id=?", (old["id"],))
                self.conn.execute("DELETE FROM publications WHERE watch_id=?", (old["id"],))
                self.conn.execute("""UPDATE watches SET term=?,active=1,seeded=0,result_total=NULL,
                  last_success=NULL,last_error=NULL,search_url=NULL WHERE id=?""", (term, old["id"]))
            else:
                self.conn.execute("UPDATE watches SET active=1 WHERE id=?", (old["id"],))

    def watch(self, telegram_id: int):
        return self.conn.execute("SELECT * FROM watches WHERE telegram_id=?", (telegram_id,)).fetchone()

    def watches(self):
        return self.conn.execute("SELECT * FROM watches WHERE active=1 ORDER BY id").fetchall()

    def ingest(self, watch_id: int, snapshot: Snapshot) -> tuple[int, bool]:
        watch = self.conn.execute("SELECT seeded FROM watches WHERE id=?", (watch_id,)).fetchone()
        if watch is None:
            raise ValueError("Monitor não cadastrado")
        baseline = not bool(watch["seeded"])
        added = 0
        with self.conn:
            for p in snapshot.publications:
                args = (watch_id, p.uid, p.title, p.url, p.pub_date, p.section,
                        p.edition, p.page, p.organization,
                        json.dumps(p.hierarchy, ensure_ascii=False), p.act_type, p.snippet,
                        json.dumps(p.raw, ensure_ascii=False), now_utc())
                cursor = self.conn.execute("""INSERT OR IGNORE INTO publications
                   (watch_id,uid,title,url,pub_date,section,edition,page,organization,
                    hierarchy_json,act_type,snippet,raw_json,first_seen)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", args)
                if cursor.rowcount:
                    added += 1
                    if not baseline:
                        self.conn.execute("""INSERT OR IGNORE INTO notifications
                             (watch_id,uid,created_at) VALUES(?,?,?)""", (watch_id, p.uid, now_utc()))
                else:
                    self.conn.execute("""UPDATE publications SET title=?,pub_date=?,section=?,edition=?,
                      page=?,organization=?,hierarchy_json=?,act_type=?,snippet=?,raw_json=?
                      WHERE watch_id=? AND uid=?""",
                      (p.title, p.pub_date, p.section, p.edition, p.page,
                       p.organization, json.dumps(p.hierarchy, ensure_ascii=False), p.act_type,
                       p.snippet, json.dumps(p.raw, ensure_ascii=False), watch_id, p.uid))
            self.conn.execute("""UPDATE watches SET seeded=1,result_total=?,last_success=?,
                last_error=NULL,search_url=? WHERE id=?""",
                (snapshot.total, now_utc(), snapshot.search_url, watch_id))
        return added, baseline

    def set_error(self, watch_id: int, detail: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE watches SET last_error=? WHERE id=?", (detail[:600], watch_id))

    def pending(self, watch_id: int, limit: int = 100):
        return self.conn.execute("""SELECT p.* FROM notifications n JOIN publications p USING(watch_id,uid)
           WHERE n.watch_id=? AND n.delivered_at IS NULL
           ORDER BY n.created_at ASC LIMIT ?""", (watch_id, limit)).fetchall()

    def mark_sent(self, watch_id: int, uid: str) -> None:
        with self.conn:
            self.conn.execute("""UPDATE notifications SET delivered_at=?,attempts=attempts+1,
                last_error=NULL WHERE watch_id=? AND uid=?""", (now_utc(), watch_id, uid))

    def mark_send_error(self, watch_id: int, uid: str, detail: str) -> None:
        with self.conn:
            self.conn.execute("""UPDATE notifications SET attempts=attempts+1,last_error=?
                WHERE watch_id=? AND uid=?""", (detail[:300], watch_id, uid))

    def latest(self, watch_id: int, limit: int = 10):
        return self.conn.execute("""SELECT * FROM publications WHERE watch_id=? ORDER BY
           substr(pub_date,7,4)||substr(pub_date,4,2)||substr(pub_date,1,2) DESC,
           first_seen DESC LIMIT ?""", (watch_id, limit)).fetchall()

    def counts(self, watch_id: int) -> tuple[int, int]:
        stored = self.conn.execute("SELECT COUNT(*) FROM publications WHERE watch_id=?", (watch_id,)).fetchone()[0]
        pending = self.conn.execute("SELECT COUNT(*) FROM notifications WHERE watch_id=? AND delivered_at IS NULL", (watch_id,)).fetchone()[0]
        return stored, pending

    def deactivate_watches(self):
        with self.conn:
            self.conn.execute("UPDATE watches SET active=0")

    def ingest_contests(self, telegram_id: int, snapshot) -> tuple[int, bool]:
        """Commit atômico: snapshot íntegro ou histórico intacto."""
        from .concursos import listing_url
        scope = snapshot.scope.upper()
        listing_url(scope)  # validar escopo, sem aceitar arbitrários
        seen = set()
        for item in snapshot.contests:
            if item.url in seen:
                raise ValueError("URLs de concursos repetidas na consulta")
            seen.add(item.url)
        old = self.conn.execute(
            "SELECT seeded FROM contest_watches WHERE telegram_id=? AND scope=?",
            (telegram_id, scope)).fetchone()
        baseline = not (old and old["seeded"])
        added = 0
        stamp = now_utc()
        with self.conn:
            self.conn.execute("""INSERT OR IGNORE INTO contest_watches(telegram_id,scope)
                VALUES(?,?)""", (telegram_id,scope))
            self.conn.execute("""UPDATE contest_entries SET current=0
                WHERE telegram_id=? AND scope=?""", (telegram_id,scope))
            for item in snapshot.contests:
                # Se uma URL já apareceu em outra categoria, não emitir alerta
                # duplicado quando o portal a realocar entre nacional/estado.
                known_elsewhere = self.conn.execute("""SELECT 1 FROM contest_entries
                    WHERE telegram_id=? AND url=? LIMIT 1""", (telegram_id,item.url)).fetchone()
                cursor = self.conn.execute("""INSERT OR IGNORE INTO contest_entries
                    (telegram_id,scope,url,organization,vacancies,title,first_seen,last_seen,current)
                    VALUES(?,?,?,?,?,?,?,?,1)""",
                    (telegram_id,scope,item.url,item.organization,item.vacancies,
                     item.title,stamp,stamp))
                if cursor.rowcount:
                    added += 1
                    if not baseline and not known_elsewhere:
                        self.conn.execute("""INSERT OR IGNORE INTO contest_notifications
                            (telegram_id,scope,url,created_at) VALUES(?,?,?,?)""",
                            (telegram_id,scope,item.url,stamp))
                else:
                    self.conn.execute("""UPDATE contest_entries SET organization=?,vacancies=?,
                        title=?,last_seen=?,current=1 WHERE telegram_id=? AND scope=? AND url=?""",
                        (item.organization,item.vacancies,item.title,stamp,telegram_id,scope,item.url))
            self.conn.execute("""UPDATE contest_watches SET seeded=1,result_total=?,
                last_success=?,last_error=NULL WHERE telegram_id=? AND scope=?""",
                (len(seen),stamp,telegram_id,scope))
        return added, baseline

    def set_contests_error(self, telegram_id: int, scope: str, detail: str):
        with self.conn:
            self.conn.execute("""INSERT OR IGNORE INTO contest_watches(telegram_id,scope)
                VALUES(?,?)""", (telegram_id,scope))
            self.conn.execute("""UPDATE contest_watches SET last_error=?
                WHERE telegram_id=? AND scope=?""", (detail[:500],telegram_id,scope))

    def contest_status(self, telegram_id: int, scope: str):
        return self.conn.execute("SELECT * FROM contest_watches WHERE telegram_id=? AND scope=?",
                                 (telegram_id,scope)).fetchone()

    def contest_list(self, telegram_id: int, scope: str, *, limit: int = 5, offset: int = 0):
        return self.conn.execute("""SELECT * FROM contest_entries
            WHERE telegram_id=? AND scope=? AND current=1
            ORDER BY organization COLLATE NOCASE, title COLLATE NOCASE
            LIMIT ? OFFSET ?""", (telegram_id,scope,limit,offset)).fetchall()

    def contest_counts(self, telegram_id: int, scope: str) -> tuple[int,int]:
        total = self.conn.execute("""SELECT COUNT(*) FROM contest_entries
            WHERE telegram_id=? AND scope=? AND current=1""", (telegram_id,scope)).fetchone()[0]
        pending = self.conn.execute("""SELECT COUNT(*) FROM contest_notifications
            WHERE telegram_id=? AND scope=? AND delivered_at IS NULL""", (telegram_id,scope)).fetchone()[0]
        return total,pending

    def pending_contests(self, telegram_id: int, limit: int = 70, scopes: tuple[str, ...] | None = None):
        # Não enviar alertas de uma UF anteriormente escolhida quando outra UF
        # está selecionada neste momento. Filtrar sem interpolar dados pessoais.
        from .concursos import UF_NAMES
        requested = scopes if scopes is not None else ("BR",*UF_NAMES.keys())
        allowed = tuple(s for s in requested if s == "BR" or s in UF_NAMES)
        if not allowed:
            return []
        placeholders = ",".join("?" for _ in allowed)
        return self.conn.execute(f"""SELECT e.* FROM contest_notifications n
            JOIN contest_entries e USING(telegram_id,scope,url)
            WHERE n.telegram_id=? AND n.delivered_at IS NULL
              AND n.scope IN ({placeholders})
            ORDER BY n.created_at ASC LIMIT ?""", (telegram_id,*allowed,limit)).fetchall()

    def mark_contest_sent(self, telegram_id: int, scope: str, url: str):
        with self.conn:
            self.conn.execute("""UPDATE contest_notifications SET delivered_at=?,
                attempts=attempts+1,last_error=NULL
                WHERE telegram_id=? AND scope=? AND url=?""",
                (now_utc(),telegram_id,scope,url))

    def mark_contest_send_error(self, telegram_id: int, scope: str, url: str, detail: str):
        with self.conn:
            self.conn.execute("""UPDATE contest_notifications SET attempts=attempts+1,
                last_error=? WHERE telegram_id=? AND scope=? AND url=?""",
                (detail[:250],telegram_id,scope,url))

    def close(self):
        self.conn.close()


def read_dashboard(database_path: Path, telegram_id: int) -> dict:
    """Leitura de outra conexão para o thread da GUI, sem compartilhar cursors."""
    if not database_path.exists():
        return {}
    db = sqlite3.connect(database_path, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        row = db.execute("SELECT * FROM watches WHERE telegram_id=?", (telegram_id,)).fetchone()
        if not row:
            return {}
        result = dict(row)
        result["saved"] = db.execute("SELECT COUNT(*) FROM publications WHERE watch_id=?", (row["id"],)).fetchone()[0]
        result["pending"] = db.execute("""SELECT COUNT(*) FROM notifications WHERE watch_id=?
                     AND delivered_at IS NULL""", (row["id"],)).fetchone()[0]
        return result
    except sqlite3.Error:
        return {}
    finally:
        db.close()


def read_contest_dashboard(database_path: Path, telegram_id: int) -> dict:
    """Resumo independente do DOU; seguro para leitura em outra thread/processo."""
    if not database_path.exists():
        return {}
    conn = sqlite3.connect(database_path, timeout=2)
    conn.row_factory = sqlite3.Row
    try:
        scopes = {}
        for item in conn.execute("SELECT * FROM contest_watches WHERE telegram_id=?", (telegram_id,)):
            scope = item["scope"]
            current = conn.execute("""SELECT COUNT(*) FROM contest_entries WHERE telegram_id=?
                AND scope=? AND current=1""",(telegram_id,scope)).fetchone()[0]
            pending = conn.execute("""SELECT COUNT(*) FROM contest_notifications
                WHERE telegram_id=? AND scope=? AND delivered_at IS NULL""",
                (telegram_id,scope)).fetchone()[0]
            scopes[scope] = {**dict(item), "current": current, "pending": pending}
        return scopes
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
