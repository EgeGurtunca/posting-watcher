"""The CO-OP mail export (Markdown, one "## N. <subject>" section per mail) -> mails for the eval.

Text that the export's author transcribed from poster images is dropped: the live system gets the image,
not a transcription, and reading posters is not in v1.
"""
import re
from datetime import date
from pathlib import Path

SECTION = re.compile(r"\n## (?=\d+\. )")
DATE = re.compile(r"\*\*Tarih:\*\* (\d\d)\.(\d\d)\.(\d{4})")
POSTER = re.compile(r"\*\*Görseldeki metin.*?(?=\*\*Linkler:\*\*|\Z)", re.DOTALL)


def load(path: Path) -> list[dict]:
    mails = []
    for section in SECTION.split(path.read_text(encoding="utf-8"))[1:]:
        head, _, rest = section.partition("\n")
        n, subject = head.split(". ", 1)
        d, m, y = DATE.search(rest).groups()
        body = "\n".join(line for line in rest.split("\n---")[0].splitlines() if not line.startswith("- **"))
        body = POSTER.sub("", body).replace("_(Mail metni yok; içerik görselde.)_", "").strip()
        mails.append({"n": int(n), "subject": subject.strip(), "received": date(int(y), int(m), int(d)),
                      "text": body, "image_only": not body or body.startswith("**Linkler:**")})
    return mails
