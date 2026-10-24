"""The bridge from the school mailbox to the laptop: Power Automate mails each exported .eml, as an attachment,
to a separate Gmail account, and this copies the attachments into the watch folder over IMAP.

Why Gmail: the school tenant blocks third-party apps (Graph gave 401, rclone needed admin consent), I did not
want the OneDrive client running on the laptop, and Outlook.com no longer allows password IMAP. A Gmail
account used only for this, with an app password, needs nothing outside the standard library.
"""
import email
import hashlib
import imaplib
import os
from email import policy
from pathlib import Path

HOST = "imap.gmail.com"
SUBJECT = "posting-watcher"  # what the flow puts in the subject; anything else in that inbox is left alone


def eml_attachments(raw: bytes) -> list[tuple[str, bytes]]:
    """(file name, bytes) of every .eml attached to one message, whether sent as a file or as message/rfc822."""
    out = []
    for part in email.message_from_bytes(raw, policy=policy.default).iter_attachments():
        if part.get_content_type() == "message/rfc822":
            data = part.get_payload(0).as_bytes()
        elif (part.get_filename() or "").lower().endswith(".eml"):
            data = part.get_payload(decode=True)
        else:
            continue
        name = Path(part.get_filename() or "").name  # .name: an attachment must not choose where it is written
        if not name.lower().endswith(".eml"):
            name = hashlib.sha1(data).hexdigest()[:16] + ".eml"
        out.append((name, data))
    return out


def fetch(folder: Path, imap: imaplib.IMAP4 | None = None) -> int:
    """Copy the .eml attachments of unread bridge mails into `folder`, then mark those mails read."""
    folder.mkdir(parents=True, exist_ok=True)
    imap = imap or imaplib.IMAP4_SSL(HOST)
    imap.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
    try:
        imap.select("INBOX")
        _, found = imap.search(None, "UNSEEN", "SUBJECT", f'"{SUBJECT}"')
        saved = 0
        for num in found[0].split():
            _, parts = imap.fetch(num, "(BODY.PEEK[])")  # PEEK: the mail stays unread until its files are on disk
            for name, data in eml_attachments(parts[0][1]):
                (folder / name).write_bytes(data)
                saved += 1
            imap.store(num, "+FLAGS", "\\Seen")
        return saved
    finally:
        imap.logout()
