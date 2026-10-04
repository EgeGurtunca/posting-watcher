"""Ollama over HTTP with the standard library.

127.0.0.1, not localhost: on Windows localhost tries ::1 first and every call waited ~2 s for nothing.
"""
import json
import os
import urllib.request

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("EXTRACT_MODEL", "gemma4:12b")


def generate_json(prompt: str, schema: dict, model: str | None = None) -> dict:
    """The answer is constrained to `schema` by Ollama itself (structured outputs), so it always parses."""
    body = {
        "model": model or MODEL, "prompt": prompt, "format": schema, "stream": False,
        "think": False,      # thinking models would spend the budget on hidden reasoning
        "keep_alive": "3s",  # free the GPU right after a mail is read
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    req = urllib.request.Request(OLLAMA_URL + "/api/generate", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(json.load(r)["response"])
