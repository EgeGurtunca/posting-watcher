"""What has been read and sent, in SQLite: a mail is processed once, the digest and heartbeat go out once."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
create table if not exists mails (message_id text primary key, received text, subject text, processed text);
create table if not exists postings (message_id text, company text, title text, kind text, technical integer,
                                     mode text, deadline text, notified integer, processed text);
create table if not exists state (key text primary key, value text);
"""


class Store:
    def __init__(self, path: Path | str):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def seen(self) -> set[str]:
        return {r[0] for r in self.db.execute("select message_id from mails")}

    def save(self, mail, rows: list[tuple], now: datetime) -> None:
        """rows: (posting, deadline, notified). One transaction, so a crash leaves the mail unread."""
        with self.db:
            self.db.executemany("insert into postings values (?,?,?,?,?,?,?,?,?)", [
                (mail.message_id, p.company, p.title, p.kind, p.technical, p.mode,
                 d.isoformat() if d else None, notified, now.isoformat()) for p, d, notified in rows])
            self.db.execute("insert into mails values (?,?,?,?)",
                            (mail.message_id, mail.received.isoformat(), mail.subject, now.isoformat()))

    def postings_on(self, day: date) -> list[tuple]:
        return self.db.execute("select kind, title, company, notified from postings where processed like ? "
                               "order by notified desc", (day.isoformat() + "%",)).fetchall()

    def counts_since(self, day: date) -> tuple[int, int, int]:
        mails = self.db.execute("select count(*) from mails where processed >= ?", (day.isoformat(),)).fetchone()[0]
        posts, notified = self.db.execute("select count(*), coalesce(sum(notified), 0) from postings "
                                          "where processed >= ?", (day.isoformat(),)).fetchone()
        return mails, posts, notified

    def last_received(self) -> str | None:
        return self.db.execute("select max(received) from mails").fetchone()[0]

    def get(self, key: str) -> str | None:
        row = self.db.execute("select value from state where key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        with self.db:
            self.db.execute("insert or replace into state values (?, ?)", (key, value))
