from dataclasses import replace
from datetime import date

from watcher.extract import Posting
from watcher.rules import should_notify

IT = Posting(company="X", title="IT Cooper", kind="coop", technical=True, mode="physical", location=None,
             paid="unknown", deadline_text=None, apply_to=None, subject_line=None)
TODAY = date(2026, 9, 24)


def test_technical_coop_internship_and_program_are_notified():
    for kind in ("coop", "internship", "program"):
        assert should_notify(replace(IT, kind=kind), None, TODAY)


def test_full_time_jobs_and_non_technical_postings_are_not():
    assert not should_notify(replace(IT, kind="job"), None, TODAY)
    assert not should_notify(replace(IT, technical=False), None, TODAY)


def test_a_passed_deadline_is_not_notified_but_today_still_is():
    assert not should_notify(IT, date(2026, 9, 23), TODAY)
    assert should_notify(IT, TODAY, TODAY)
