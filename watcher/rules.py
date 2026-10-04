"""Whether a posting gets a Telegram message. Decided here in code; the model only reports the facts."""
from datetime import date

from watcher.extract import Posting

NOTIFY_KINDS = {"coop", "internship", "program"}  # full-time jobs are not what I am looking for yet


def should_notify(p: Posting, deadline: date | None, today: date) -> bool:
    return p.technical and p.kind in NOTIFY_KINDS and not (deadline and deadline < today)
