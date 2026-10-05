from datetime import datetime, timezone
from email.message import EmailMessage

from watcher.inbox import new_mails, read_eml


def write_eml(folder, name, *, subject="COOP:// X - IT Cooper", sender="Coop <coop@coop.bau.edu.tr>",
              date="Wed, 23 Sep 2026 16:48:00 +0300", message_id="<a1@bau>", plain=None, html=None):
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["Date"] = subject, sender, date
    if message_id:
        msg["Message-ID"] = message_id
    if plain is not None:
        msg.set_content(plain)
        if html is not None:
            msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(html or "", subtype="html")
    path = folder / name
    path.write_bytes(bytes(msg))
    return path


def test_reads_headers_and_the_plain_body(tmp_path):
    m = read_eml(write_eml(tmp_path, "a.eml", plain="Merhaba,\nLokasyon: Levent", html="<p>ignored</p>"))
    assert (m.message_id, m.sender, m.subject) == ("<a1@bau>", "coop@coop.bau.edu.tr", "COOP:// X - IT Cooper")
    assert m.received == datetime(2026, 9, 23, 13, 48, tzinfo=timezone.utc)
    assert "Lokasyon: Levent" in m.text and "ignored" not in m.text


def test_html_only_mail_becomes_readable_text(tmp_path):
    html = "<div>Görev ve sorumluluklar</div><ul><li>Bilgisayar kurulumları</li><li>Ram &amp; disk</li></ul>"
    m = read_eml(write_eml(tmp_path, "a.eml", html=html))
    assert m.text.splitlines() == ["Görev ve sorumluluklar", "Bilgisayar kurulumları", "Ram & disk"]


def test_missing_message_id_falls_back_to_the_file_name(tmp_path):
    assert read_eml(write_eml(tmp_path, "20260923-x.eml", message_id=None, plain="x")).message_id == "20260923-x.eml"


def test_new_mails_skips_seen_ones_and_sorts_by_time(tmp_path):
    write_eml(tmp_path, "late.eml", message_id="<late>", date="Thu, 24 Sep 2026 10:00:00 +0300", plain="x")
    write_eml(tmp_path, "early.eml", message_id="<early>", date="Tue, 22 Sep 2026 10:00:00 +0300", plain="x")
    write_eml(tmp_path, "old.eml", message_id="<old>", plain="x")
    (tmp_path / "notes.txt").write_text("not a mail")
    assert [m.message_id for m in new_mails(tmp_path, seen={"<old>"})] == ["<early>", "<late>"]
