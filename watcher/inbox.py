"""New mails from the folder a Power Automate flow fills with one .eml file per mail.

The flow (see the README) exports every mail from the configured senders to OneDrive; the OneDrive app syncs
that folder to this laptop. So reading mail is reading files: no mailbox login, no tokens.
"""
import html
import re
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

BLOCK_END = re.compile(r"<\s*(br|/p|/div|/li|/tr|/h\d)\b[^>]*>", re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")
SKIP = re.compile(r"<(style|script)\b.*?</\1>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Mail:
    message_id: str
    sender: str
    received: datetime
    subject: str
    text: str
    path: Path


def html_to_text(markup: str) -> str:
    # ponytail: regex tag stripping is enough for posting mails; swap for an HTML parser if a sender's markup breaks it
    text = BLOCK_END.sub("\n", SKIP.sub("", markup))
    text = html.unescape(TAG.sub("", text)).replace("\xa0", " ")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def read_eml(path: Path) -> Mail:
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    body = msg.get_body(preferencelist=("plain", "html"))
    content = body.get_content() if body else ""
    text = html_to_text(content) if body and body.get_content_subtype() == "html" else content.strip()
    received = msg["Date"].datetime if msg["Date"] else datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    return Mail(
        message_id=str(msg["Message-ID"] or path.name).strip(),
        sender=parseaddr(str(msg["From"] or ""))[1].lower(),
        received=received,
        subject=str(msg["Subject"] or ""),
        text=text,
        path=path,
    )


def new_mails(folder: Path, seen: set[str]) -> list[Mail]:
    mails = [read_eml(p) for p in folder.glob("*.eml")]
    return sorted((m for m in mails if m.message_id not in seen), key=lambda m: m.received)
