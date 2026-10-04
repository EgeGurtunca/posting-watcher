"""The no-LLM baseline the model has to beat: subject tags, title keywords and a deadline regex.

Same interface as watcher.extract.extract, so the eval runs both the same way.
"""
import re

from watcher.deadline import tr_lower
from watcher.extract import Posting

COOP = re.compile(r"co-?op\s*(\([^)]*\))?\s*:?\s*/")           # "COOP://", "COOP(HİBRİT)://", "CO-OP //"
PROGRAM = re.compile(r"program|akademi\b|hackathon|yaz okulu|eğitim")  # not "akademik"
INTERNSHIP = re.compile(r"staj")
TECHNICAL = re.compile(r"\b(it|bilgi teknolojileri|yazılım|yapay zeka|ai|network|security|bilgisayar mühendisliği|"
                       r"qa|tester|data|analytics|veri|entegrasyon|ar-ge|sistem destek|hackathon)\b")
MODES = [(re.compile(r"hibrit|hybrid"), "hybrid"), (re.compile(r"online|remote"), "online"),
         (re.compile(r"fiziksel"), "physical")]
DEADLINE = re.compile(r"[^\n]*(tarih(?:ine|inden)\s+(?:kadar|önce)|son\s+başvuru)[^\n]*")


def extract(subject: str, text: str, model: str | None = None) -> list[Posting]:
    # Turkish lowercase for "FİZİKSEL"/"HİBRİT", plain lowercase for English: tr_lower("IT") is "ıt", "ONLINE" "onlıne"
    s = tr_lower(subject) + "\n" + subject.lower()
    if COOP.search(s):
        kind = "coop"
    elif PROGRAM.search(s):
        kind = "program"
    elif INTERNSHIP.search(s):
        kind = "internship"
    else:
        return []  # treated as an announcement
    deadline = DEADLINE.search(tr_lower(subject + "\n" + text))
    return [Posting(company=subject, title=subject, kind=kind, technical=bool(TECHNICAL.search(s)),
                    mode=next((m for rx, m in MODES if rx.search(s)), "unknown"), location=None, paid="unknown",
                    deadline_text=deadline.group(0).strip() if deadline else None, apply_to=None, subject_line=None)]
