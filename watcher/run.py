"""One pass, run every 15 minutes by Windows Task Scheduler: python -m watcher.run

Reads new mail files, notifies technical postings, sends the 21:00 digest and the Monday heartbeat, and
turns any failure into a Telegram alert, because a watcher that fails silently looks exactly like a quiet week.
"""
import os
import subprocess
import time
import traceback
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from watcher import extract, llm, notify
from watcher.deadline import parse_deadline
from watcher.inbox import Mail, new_mails
from watcher.rules import should_notify
from watcher.store import Store

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIGEST_HOUR = 21


def load_env(path: Path = ROOT / ".env") -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(llm.OLLAMA_URL + "/api/tags", timeout=2)
        return True
    except OSError:
        return False


@contextmanager
def ollama():
    """Start Ollama only when there is mail to read, and stop it only if this run started it."""
    proc = None
    if not _ollama_up():
        proc = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            if _ollama_up():
                break
            time.sleep(1)
        else:
            raise RuntimeError("Ollama did not start")
    try:
        yield
    finally:
        if proc:
            proc.terminate()


def process(mail: Mail, store: Store, now: datetime) -> None:
    # ponytail: at-least-once: a crash between send() and save() repeats that message on the next run
    today, rows = now.date(), []
    for p in extract.extract(mail.subject, mail.text):
        deadline = parse_deadline(p.deadline_text, mail.received.date())
        hit = should_notify(p, deadline, today)
        if hit:
            notify.send(notify.format_posting(p, deadline, today))
        rows.append((p, deadline, hit))
    store.save(mail, rows, now)


def digest(store: Store, now: datetime) -> None:
    day = now.date().isoformat()
    if now.hour < DIGEST_HOUR or store.get("digest") == day:
        return
    rows = store.postings_on(now.date())
    if rows:
        hits = [r for r in rows if r[3]]
        notify.send("\n".join([f"📋 Bugünün özeti: {len(hits)} teknik ilan, {len(rows) - len(hits)} diğer"]
                              + [f"• {notify.KIND[kind]} · {title} · {company}" for kind, title, company, _ in hits]))
    store.set("digest", day)


def heartbeat(store: Store, now: datetime) -> None:
    week = now.strftime("%G-W%V")
    if now.weekday() != 0 or store.get("heartbeat") == week:
        return
    mails, postings, notified = store.counts_since(now.date() - timedelta(days=7))
    text = f"✅ posting-watcher çalışıyor. Son 7 gün: {mails} mail, {postings} ilan, {notified} bildirim."
    last = store.last_received()
    if not last or datetime.fromisoformat(last) < now - timedelta(days=7):
        text += "\n⚠️ 7 gündür yeni mail dosyası gelmedi: Power Automate akışını ve OneDrive'ı kontrol et."
    notify.send(text)
    store.set("heartbeat", week)


def alert(store: Store, now: datetime, err: Exception) -> None:
    key, day = f"alert:{type(err).__name__}", now.date().isoformat()
    if store.get(key) != day:  # at most one alert per kind of failure per day, not one every 15 minutes
        notify.send(f"⚠️ posting-watcher çalışmadı: {type(err).__name__}: {str(err)[:300]}")
        store.set(key, day)


def run_once(store: Store, folder: Path, senders: set[str], now: datetime) -> None:
    if not folder.is_dir():  # an unsynced folder would otherwise look like "no new mail" forever
        raise FileNotFoundError(f"watch folder not found: {folder}")
    mails = new_mails(folder, store.seen())
    for m in mails:
        if m.sender not in senders:
            store.save(m, [], now)
    ours = [m for m in mails if m.sender in senders]
    if ours:
        with ollama():
            for m in ours:
                process(m, store, now)
    digest(store, now)
    heartbeat(store, now)


def main() -> None:
    load_env()
    DATA.mkdir(exist_ok=True)
    store, now = Store(DATA / "watcher.db"), datetime.now().astimezone()
    senders = {s.strip().lower() for s in os.environ.get("SENDERS", "coop@coop.bau.edu.tr").split(",")}
    def log() -> None:
        with open(DATA / "watcher.log", "a", encoding="utf-8") as f:
            f.write(f"{now.isoformat()}\n{traceback.format_exc()}\n")

    try:
        run_once(store, Path(os.environ["WATCH_FOLDER"]), senders, now)  # KeyError if unset: an alert, not "."
    except Exception as err:
        log()
        try:
            alert(store, now, err)
        except Exception:
            log()  # Telegram itself is down: the log is all that is left
        raise SystemExit(1)


if __name__ == "__main__":
    main()
