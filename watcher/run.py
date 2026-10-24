"""One pass, run every hour by Windows Task Scheduler: python -m watcher.run

Reads new mail files, notifies technical postings, sends the 21:00 digest and the Monday heartbeat, and
turns any failure into a Telegram alert, because a watcher that fails silently looks exactly like a quiet week.
"""
import os
import subprocess
import time
import traceback
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from watcher import extract, gmail, llm, notify
from watcher.deadline import parse_deadline
from watcher.inbox import Mail, new_mails
from watcher.rules import should_notify
from watcher.store import Store

IS_WINDOWS = os.name == "nt"
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
        proc = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # no console pop-up under pythonw
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
            stop(proc)


def stop(proc: subprocess.Popen) -> None:
    """Stop `ollama serve` with its llama-server children: terminate() alone left them holding 8 GB of VRAM."""
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
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


def model_due(now: datetime) -> bool:
    """READ_AFTER=21 in .env: posting mails wait until 21:00, so the GPU stays free all day. Unset: every run."""
    after = os.environ.get("READ_AFTER", "").strip()
    return not after or now.hour >= int(after)


def digest(store: Store, now: datetime) -> None:
    day = now.date().isoformat()
    if now.hour < DIGEST_HOUR or not model_due(now) or store.get("digest") == day:
        return
    rows = store.postings_on(now.date())
    if rows:
        hits, others = [r for r in rows if r[3]], [r for r in rows if not r[3]]
        lines = [f"📋 Bugünün özeti: {len(hits)} teknik ilan, {len(others)} diğer"]
        for kind, title, company, _, mode, deadline in hits:
            lines += ["", f"🆕 {notify.KIND[kind]} · {title} · {company}", f"📍 {notify.MODE[mode]}"
                      + (f" · ⏰ son gün: {notify.when(date.fromisoformat(deadline), now.date())}" if deadline else "")]
        if others:
            lines += ["", "Diğer:"] + [f"• {notify.KIND[kind]} · {title} · {company}" for kind, title, company, *_ in others]
        notify.send("\n".join(lines))
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
    if store.get(key) != day:  # at most one alert per kind of failure per day, not one every hour
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
    if ours and model_due(now):  # not due: they stay unread and wait for the evening run
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
        folder = Path(os.environ["WATCH_FOLDER"])  # KeyError if unset: an alert, not "."
        if os.environ.get("GMAIL_USER"):
            gmail.fetch(folder)  # IMAP or login failures land in the alert below like any other
        run_once(store, folder, senders, now)
    except Exception as err:
        log()
        try:
            alert(store, now, err)
        except Exception:
            log()  # Telegram itself is down: the log is all that is left
        raise SystemExit(1)


if __name__ == "__main__":
    main()
