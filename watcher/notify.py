"""Telegram messages: one HTTPS call to the Bot API. The token and chat id come from .env, never from code."""
import json
import os
import urllib.parse
import urllib.request
from datetime import date

from watcher.extract import Posting

API = "https://api.telegram.org/bot{token}/{method}"
KIND = {"coop": "CO-OP", "internship": "Staj", "program": "Program", "job": "İş"}
MODE = {"physical": "fiziksel", "hybrid": "hibrit", "online": "online", "unknown": "çalışma şekli yazmıyor"}
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def send(text: str) -> None:
    data = urllib.parse.urlencode({"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text,
                                   "disable_web_page_preview": "true"}).encode()
    url = API.format(token=os.environ["TELEGRAM_TOKEN"], method="sendMessage")
    with urllib.request.urlopen(url, data, timeout=30) as r:
        if not json.load(r).get("ok"):
            raise RuntimeError("Telegram refused the message")


def chat_ids() -> set[str]:
    """Chats that have messaged the bot; used once, to fill TELEGRAM_CHAT_ID."""
    with urllib.request.urlopen(API.format(token=os.environ["TELEGRAM_TOKEN"], method="getUpdates"), timeout=30) as r:
        return {str(u["message"]["chat"]["id"]) for u in json.load(r)["result"] if "message" in u}


def when(deadline: date, today: date) -> str:
    left = (deadline - today).days
    rel = "bugün" if left == 0 else "yarın" if left == 1 else f"{left} gün var"
    return f"{deadline.day} {MONTHS[deadline.month - 1]} {DAYS[deadline.weekday()]} ({rel})"


def format_posting(p: Posting, deadline: date | None, today: date) -> str:
    lines = [f"🆕 {KIND[p.kind]} · {p.title} · {p.company}",
             "📍 " + " · ".join(x for x in (p.location, MODE[p.mode]) if x)]
    if deadline:
        lines.append(f"⏰ son gün: {when(deadline, today)}")
    if p.apply_to:
        lines.append(f"✉️ {p.apply_to}" + (f' · konu: "{p.subject_line}"' if p.subject_line else ""))
    return "\n".join(lines)


if __name__ == "__main__":  # setup: python -m watcher.notify
    from watcher.run import load_env
    load_env()
    if os.environ.get("TELEGRAM_CHAT_ID"):
        send("✅ posting-watcher bağlandı.")
        print("Test message sent.")
    else:
        print("\n".join(f"TELEGRAM_CHAT_ID={i}" for i in chat_ids())
              or "No messages yet: send your bot any message in Telegram, then run this again.")
