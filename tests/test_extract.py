from watcher import extract as ex
from watcher import llm

ORNEK = {"company": "Örnek Lojistik", "title": "IT Cooper", "kind": "coop", "technical": True,
       "mode": "physical", "location": " Levent, Beşiktaş ", "paid": "unknown",
       "deadline_text": "26 Eylül CUMARTESİ tarihinden önce", "apply_to": "ik@example.com",
       "subject_line": ""}


def test_fields_come_back_typed_and_empty_strings_become_none(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "generate_json", lambda prompt, schema, model=None: calls.append(prompt) or {"postings": [ORNEK]})
    [p] = ex.extract("FİZİKSEL COOP:// Örnek Lojistik - IT Cooper", "Lokasyon: Levent")
    assert (p.company, p.technical, p.mode, p.location, p.subject_line) == (
        "Örnek Lojistik", True, "physical", "Levent, Beşiktaş", None)
    assert "FİZİKSEL COOP:// Örnek Lojistik - IT Cooper" in calls[0] and "Lokasyon: Levent" in calls[0]


def test_a_digest_mail_gives_several_postings_and_an_info_mail_none(monkeypatch):
    monkeypatch.setattr(llm, "generate_json", lambda *_a, **_k: {"postings": [ORNEK, {**ORNEK, "company": "B"}]})
    assert [p.company for p in ex.extract("s", "t")] == ["Örnek Lojistik", "B"]
    monkeypatch.setattr(llm, "generate_json", lambda *_a, **_k: {"postings": []})
    assert ex.extract("Yeni akademik yıl", "Hoş geldin") == []


def test_the_schema_only_allows_known_values():
    item = ex.SCHEMA["properties"]["postings"]["items"]
    assert item["properties"]["kind"]["enum"] == ["coop", "internship", "job", "program"]
    assert set(item["required"]) == {f.name for f in ex.Posting.__dataclass_fields__.values()}
