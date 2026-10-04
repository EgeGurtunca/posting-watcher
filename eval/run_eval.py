"""Score extraction + the notify rule against hand-checked labels for the exported CO-OP mails.

Run: python -m eval.run_eval [--systems keywords,gemma4:12b] [--export PATH]
"""
import argparse
import json
import time
from datetime import date
from pathlib import Path

from eval import baseline
from eval.export import load
from watcher import extract
from watcher.deadline import parse_deadline
from watcher.rules import should_notify

ROOT = Path(__file__).parent
DEFAULT_EXPORT = Path.home() / "Downloads" / "BAU_Coop_Mailleri_Temmuz-Eylul_2026.md"


def predict(system: str, mail: dict) -> dict:
    run = baseline.extract if system == "keywords" else extract.extract
    t0 = time.perf_counter()
    postings = run(mail["subject"], mail["text"], model=None if system == "keywords" else system)
    secs = time.perf_counter() - t0
    scored = [(p, parse_deadline(p.deadline_text, mail["received"])) for p in postings]
    hits = [(p, d) for p, d in scored if should_notify(p, d, mail["received"])]
    main, deadline = (hits or scored or [(None, None)])[0]  # the posting the notification would be about
    return {"n": mail["n"], "notify": bool(hits), "kind": main and main.kind, "technical": main and main.technical,
            "mode": main and main.mode, "deadline": deadline.isoformat() if deadline else None, "secs": secs}


def score(preds: list[dict], gold: dict[int, dict]) -> dict:
    tp = sum(p["notify"] and gold[p["n"]]["notify"] for p in preds)
    fp = sum(p["notify"] and not gold[p["n"]]["notify"] for p in preds)
    fn = sum(not p["notify"] and gold[p["n"]]["notify"] for p in preds)
    clear = [p for p in preds if not gold[p["n"]].get("borderline")]

    def acc(field: str, rows: list[dict]) -> float:
        rows = [p for p in rows if gold[p["n"]].get(field) is not None or field == "deadline"]
        rows = [p for p in rows if gold[p["n"]]["kind"] is not None]
        return round(sum(p[field] == gold[p["n"]][field] for p in rows) / len(rows), 3) if rows else 0.0

    return {
        "notify_recall": round(tp / (tp + fn), 3) if tp + fn else 1.0,
        "notify_precision": round(tp / (tp + fp), 3) if tp + fp else 1.0,
        "missed": [p["n"] for p in preds if not p["notify"] and gold[p["n"]]["notify"]],
        "false_alarms": [p["n"] for p in preds if p["notify"] and not gold[p["n"]]["notify"]],
        "notify_acc_without_borderline": round(sum(p["notify"] == gold[p["n"]]["notify"] for p in clear) / len(clear), 3),
        **{f"{f}_acc": acc(f, preds) for f in ("kind", "technical", "mode", "deadline")},
        "secs_per_mail": round(sum(p["secs"] for p in preds) / len(preds), 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="keywords,gemma4:12b")
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    args = ap.parse_args()
    mails = load(args.export)
    gold = {g["n"]: g for g in map(json.loads, (ROOT / "gold.jsonl").read_text(encoding="utf-8").splitlines()) if g}
    out = {}
    for system in args.systems.split(","):
        preds = [predict(system, m) for m in mails]
        out[system] = score(preds, gold)
        print(system, json.dumps(out[system], ensure_ascii=False), flush=True)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / f"{date.today()}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
