from datetime import date

import pytest

from watcher.deadline import parse_deadline

# Every phrasing in the July to September 2026 CO-OP export, with the date the mail arrived.
CASES = [
    ("27 Eylül PAZAR tarihine kadar", date(2026, 9, 24), date(2026, 9, 27)),          # "kadar" includes the day
    ("26 Eylül CUMARTESİ tarihinden önce", date(2026, 9, 22), date(2026, 9, 25)),     # "önce" is the day before
    ("18 EYLÜL CUMA tarihine kadar", date(2026, 9, 15), date(2026, 9, 18)),
    ("21 EYLÜL PAZARTESİ tarihinden önce", date(2026, 9, 17), date(2026, 9, 20)),
    ("20 Temmuz PAZARTESİ tarihinden önce", date(2026, 7, 16), date(2026, 7, 19)),
    ("4 EYLÜL CUMA tarihinden önce", date(2026, 9, 1), date(2026, 9, 3)),
    ("31 AĞUSTOS PAZARTESİ tarihinden önce", date(2026, 8, 27), date(2026, 8, 30)),
    # the day number is missing: first such weekday of that month on or after the mail date
    ("Eylül CUMARTESİ tarihinden önce", date(2026, 9, 23), date(2026, 9, 25)),
    ("Eylül PERŞEMBE tarihinden önce", date(2026, 9, 7), date(2026, 9, 9)),
    ("Ağustos Cumartesi tarihinden önce", date(2026, 8, 12), date(2026, 8, 14)),
    # other senders
    ("Programa Son Başvuru Tarihi : 18 Ekim 2026", date(2026, 9, 22), date(2026, 10, 18)),
    ("Son başvuru tarihi: 09.09.2026", date(2026, 8, 27), date(2026, 9, 9)),
    ("➡Son Başvuru Tarihi: 15 Temmuz 2026 - 23.59", date(2026, 7, 10), date(2026, 7, 15)),
]


@pytest.mark.parametrize("text, received, expected", CASES)
def test_export_phrasings(text, received, expected):
    assert parse_deadline(text, received) == expected


def test_no_year_means_the_nearest_such_date():
    assert parse_deadline("5 Ocak PAZARTESİ tarihine kadar", date(2026, 12, 20)) == date(2027, 1, 5)
    assert parse_deadline("18 Eylül tarihine kadar", date(2026, 9, 20)) == date(2026, 9, 18)  # sent late, not next year


def test_turkish_dotless_i():
    # "SALI".lower() is "sali" in Python; it has to become "salı"
    assert parse_deadline("Eylül SALI tarihinden önce", date(2026, 9, 14)) == date(2026, 9, 14)


def test_no_date():
    assert parse_deadline("Ücret görüşmede netleşecek", date(2026, 9, 1)) is None
    assert parse_deadline(None, date(2026, 9, 1)) is None
    assert parse_deadline("Eylül tarihinden önce", date(2026, 9, 1)) is None  # neither a day nor a weekday
