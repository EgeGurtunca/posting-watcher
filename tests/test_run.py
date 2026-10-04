import os
from contextlib import nullcontext
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from test_inbox import write_eml

from watcher import extract, notify, run
from watcher.extract import Posting
from watcher.store import Store

TZ = timezone(timedelta(hours=3))
NOW = datetime(2026, 9, 23, 17, 0, tzinfo=TZ)  # a Wednesday afternoon
COOP = "coop@coop.bau.edu.tr"
IT = Posting(company="Örnek Lojistik", title="IT Cooper", kind="coop", technical=True, mode="physical",
             location="Levent", paid="unknown", deadline_text="26 Eylül CUMARTESİ tarihinden önce",
             apply_to="ik@example.com", subject_line="Örnek Lojistik-IT")


@pytest.fixture
def env(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    sent = []
    monkeypatch.setattr(notify, "send", sent.append)
    monkeypatch.setattr(extract, "extract", lambda subject, text: [IT] if "IT" in subject else [replace(IT, technical=False)])
    monkeypatch.setattr(run, "ollama", nullcontext)
    return inbox, Store(tmp_path / "w.db"), sent


def test_a_technical_posting_is_notified_once(env):
    inbox, store, sent = env
    write_eml(inbox, "a.eml", subject="COOP:// Örnek - IT Cooper", sender=f"Coop <{COOP}>", plain="x")
    write_eml(inbox, "b.eml", subject="COOP:// Quick - Operasyon", sender=COOP, message_id="<b@bau>", plain="x")
    run.run_once(store, inbox, {COOP}, NOW)
    run.run_once(store, inbox, {COOP}, NOW + timedelta(minutes=15))
    assert len(sent) == 1
    assert sent[0].splitlines()[0] == "🆕 CO-OP · IT Cooper · Örnek Lojistik"
    assert "son gün: 25 Eylül Cum (2 gün var)" in sent[0] and 'konu: "Örnek Lojistik-IT"' in sent[0]


def test_other_senders_are_marked_seen_without_starting_the_model(env, monkeypatch):
    inbox, store, sent = env
    monkeypatch.setattr(run, "ollama", lambda: (_ for _ in ()).throw(AssertionError("ollama started")))
    write_eml(inbox, "a.eml", sender="someone@hotmail.com", plain="x")
    run.run_once(store, inbox, {COOP}, NOW)
    run.run_once(store, inbox, {COOP}, NOW)  # nothing new at all: no model either
    assert store.seen() == {"<a1@bau>"} and sent == []


def test_a_crash_leaves_the_mail_unread_for_the_next_run(env, monkeypatch):
    inbox, store, sent = env
    write_eml(inbox, "a.eml", subject="COOP:// Örnek - IT Cooper", sender=COOP, plain="x")
    monkeypatch.setattr(extract, "extract", lambda *_a: (_ for _ in ()).throw(ConnectionError("ollama down")))
    with pytest.raises(ConnectionError):
        run.run_once(store, inbox, {COOP}, NOW)
    assert store.seen() == set()


def test_a_missing_folder_is_an_error_not_an_empty_inbox(env, tmp_path):
    _, store, _ = env
    with pytest.raises(FileNotFoundError):
        run.run_once(store, tmp_path / "not-synced", {COOP}, NOW)


def test_alerts_go_out_once_per_kind_per_day(env):
    _, store, sent = env
    for _ in range(3):
        run.alert(store, NOW, ConnectionError("ollama down"))
    run.alert(store, NOW, FileNotFoundError("folder"))
    run.alert(store, NOW + timedelta(days=1), ConnectionError("ollama down"))
    assert len(sent) == 3


def test_digest_after_21_once_and_only_with_postings(env):
    inbox, store, sent = env
    write_eml(inbox, "a.eml", subject="COOP:// Örnek - IT Cooper", sender=COOP, plain="x")
    run.run_once(store, inbox, {COOP}, NOW)
    sent.clear()
    run.digest(store, NOW.replace(hour=20))
    run.digest(store, NOW.replace(hour=21))
    run.digest(store, NOW.replace(hour=22))
    assert sent == ["📋 Bugünün özeti: 1 teknik ilan, 0 diğer\n• CO-OP · IT Cooper · Örnek Lojistik"]
    run.digest(store, NOW.replace(hour=21) + timedelta(days=1))  # a day without postings: no message
    assert len(sent) == 1


def test_monday_heartbeat_once_and_it_warns_when_nothing_arrived(env):
    _, store, sent = env
    monday = datetime(2026, 9, 28, 9, 0, tzinfo=TZ)
    run.heartbeat(store, monday - timedelta(days=1))  # Sunday: nothing
    run.heartbeat(store, monday)
    run.heartbeat(store, monday.replace(hour=10))
    assert len(sent) == 1 and "0 mail" in sent[0] and "7 gündür yeni mail dosyası gelmedi" in sent[0]


def test_load_env_reads_key_values_and_ignores_comments(tmp_path, monkeypatch):
    monkeypatch.delenv("WATCH_FOLDER", raising=False)
    (tmp_path / ".env").write_text("# comment\nWATCH_FOLDER = C:/x\n", encoding="utf-8")
    run.load_env(tmp_path / ".env")

    assert os.environ["WATCH_FOLDER"] == "C:/x"


def test_when_says_today_and_tomorrow():
    assert notify.when(date(2026, 9, 25), date(2026, 9, 25)).endswith("(bugün)")
    assert notify.when(date(2026, 9, 26), date(2026, 9, 25)) == "26 Eylül Cmt (yarın)"
