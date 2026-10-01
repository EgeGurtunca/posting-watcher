"""Turkish deadline phrases from internship mails -> a date.

The model copies the sentence word for word; this turns it into a date, because the rules are easy to get
wrong and easy to test:
- "27 Eylül PAZAR tarihine kadar" includes that day; "26 Eylül CUMARTESİ tarihinden önce" means the 25th.
- The year is usually missing: take the nearest such date to the day the mail arrived.
- The day number is sometimes missing ("Eylül CUMARTESİ tarihinden önce"): take the first such weekday of
  that month on or after the mail date.
- Other senders write "18 Ekim 2026" or "09.09.2026".
"""
import re
from datetime import date, timedelta

MONTHS = ["ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"]
WEEKDAYS = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]  # date.weekday() order


def _alternation(words: list[str]) -> str:
    return "|".join(sorted(words, key=len, reverse=True))  # "cumartesi" before "cuma", "pazartesi" before "pazar"


NUMERIC = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
WORDS = re.compile(rf"(?:\b(\d{{1,2}})\s+)?\b({_alternation(MONTHS)})\b(?:\s+(\d{{4}}))?(?:\s+({_alternation(WEEKDAYS)})\b)?")


def _lower(text: str) -> str:
    # str.lower() turns "SALI" into "sali" and "İ" into "i" plus a combining dot; Turkish needs ı and i.
    return text.replace("I", "ı").replace("İ", "i").lower()


def _nearest(day: int, month: int, received: date) -> date | None:
    candidates = []
    for year in (received.year - 1, received.year, received.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:  # 29 February in a non-leap year
            pass
    return min(candidates, key=lambda d: abs(d - received), default=None)


def _first_weekday(weekday: int, month: int, received: date) -> date | None:
    year = received.year if month >= received.month else received.year + 1
    start = max(date(year, month, 1), received)
    d = start + timedelta(days=(weekday - start.weekday()) % 7)
    return d if d.month == month else None


def parse_deadline(text: str | None, received: date) -> date | None:
    if not text:
        return None
    t = _lower(text)
    if m := NUMERIC.search(t):
        d = date(int(m[3]), int(m[2]), int(m[1]))
    elif m := WORDS.search(t):
        day, month_name, year, weekday = m.groups()
        month = MONTHS.index(month_name) + 1
        if day and year:
            d = date(int(year), month, int(day))
        elif day:
            d = _nearest(int(day), month, received)
        elif weekday:
            d = _first_weekday(WEEKDAYS.index(weekday), month, received)
        else:
            return None
    else:
        return None
    if d and "önce" in t:
        d -= timedelta(days=1)
    return d
