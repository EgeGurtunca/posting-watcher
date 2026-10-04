from eval import baseline
from eval.run_eval import score


def test_baseline_reads_subject_tags_and_the_deadline_line():
    [p] = baseline.extract("ÜCRETLİ (HİBRİT) COOP:// Örnek Fintech- AR-GE Cooper",
                           "Merhaba,\n24 TEMMUZ CUMA tarihinden önce;\nMaillerinizin konu kısmına ...")
    assert (p.kind, p.technical, p.mode, p.deadline_text) == ("coop", True, "hybrid", "24 temmuz cuma tarihinden önce;")
    assert baseline.extract("CO-OP Yeni Akademik Dönem Maili", "Hoş geldin") == []  # not "CO-OP //"
    assert baseline.extract("ÜCRETLİ COOP(FİZİKSEL):// Örnek Yazılım Danışmanlık", "")[0].technical  # its known trap
    [p] = baseline.extract("ONLINE COOP:// Örnek-AI Expert Cooper", "")  # English words survive Turkish lowercasing
    assert (p.technical, p.mode) == (True, "online")


def test_score_counts_misses_false_alarms_and_skips_unlabelled_fields():
    gold = {1: {"notify": True, "kind": "coop", "technical": True, "mode": None, "deadline": "2026-09-25"},
            2: {"notify": False, "kind": "coop", "technical": False, "mode": "physical", "deadline": None},
            3: {"notify": True, "kind": "coop", "technical": True, "mode": "online", "deadline": None, "borderline": True}}
    row = {"kind": "coop", "secs": 1.0}
    preds = [{**row, "n": 1, "notify": True, "technical": True, "mode": "hybrid", "deadline": "2026-09-25"},
             {**row, "n": 2, "notify": True, "technical": True, "mode": "physical", "deadline": None},
             {**row, "n": 3, "notify": False, "technical": False, "mode": "online", "deadline": None}]
    s = score(preds, gold)
    assert (s["notify_recall"], s["notify_precision"], s["missed"], s["false_alarms"]) == (0.5, 0.5, [3], [2])
    assert s["notify_acc_without_borderline"] == 0.5
    assert s["mode_acc"] == 1.0  # n=1 has no gold mode, so it is not counted
    assert s["deadline_acc"] == 1.0
