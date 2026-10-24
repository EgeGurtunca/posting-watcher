from email.message import EmailMessage

from watcher import gmail
from watcher.inbox import read_eml


def bridge_mail(*attachments) -> bytes:
    msg = EmailMessage()
    msg["Subject"], msg["From"] = "posting-watcher", "Ege <ege@school.example>"
    msg.set_content("posting-watcher")
    for a in attachments:
        if isinstance(a, EmailMessage):
            msg.add_attachment(a)  # message/rfc822
        else:
            name, data = a
            msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return bytes(msg)


def posting(subject="COOP:// Örnek - IT Cooper") -> EmailMessage:
    m = EmailMessage()
    m["Subject"], m["From"], m["Message-ID"] = subject, "Coop <coop@coop.bau.edu.tr>", "<p1@bau>"
    m.set_content("Lokasyon: Levent")
    return m


class FakeIMAP:
    def __init__(self, mails):
        self.mails, self.calls = mails, []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            if name == "search":
                return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self.mails)))]
            if name == "fetch":
                return "OK", [(b"1 (BODY[] {n}", self.mails[int(args[0]) - 1])]
            return "OK", [b""]
        return call


def test_eml_attachments_are_saved_and_the_mail_marked_read_after(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "bot@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "x")
    imap = FakeIMAP([bridge_mail(("20261024-1.eml", bytes(posting()))), bridge_mail(posting("COOP:// Diğer"))])
    assert gmail.fetch(tmp_path / "mail", imap) == 2
    files = sorted((tmp_path / "mail").iterdir())
    assert files[0].name == "20261024-1.eml"
    assert sorted(read_eml(f).subject for f in files) == ["COOP:// Diğer", "COOP:// Örnek - IT Cooper"]
    names = [c[0] for c in imap.calls]
    assert names.index("store") > names.index("fetch") and names[-1] == "logout"
    assert ("fetch", (b"1", "(BODY.PEEK[])")) in imap.calls


def test_only_eml_files_are_taken_and_names_cannot_escape_the_folder():
    raw = bridge_mail(("notes.txt", b"hi"), ("..\\..\\evil.eml", b"From: x\n\nhi"))
    assert gmail.eml_attachments(raw) == [("evil.eml", b"From: x\n\nhi")]
