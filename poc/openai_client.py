"""Minimal OpenAI client for the evaluation (judge + embeddings) with a hard spending cap.

The API key comes from OPENAI_API_KEY (or a .env file passed via CHROMERAG_ENV_FILE) and is
never logged. Every call's cost is computed from the returned token usage at the list prices
below and added to data/outputs/openai_spend.json; a call that would exceed the cap is
refused, so repeated runs cannot overspend.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import httpx

from poc.fetch_pages import _ssl_verify
from poc.run_corpus_comparison import OUT

API = "https://api.openai.com/v1"
# USD per 1M tokens (OpenAI list prices, September 2026): (input, output)
PRICES = {
    "gpt-5.6-luna": (0.20, 0.75),
    "gpt-5.6-terra": (5.00, 25.00),  # assumed; used for one manuscript review
    "text-embedding-3-small": (0.02, 0.0),
}
SPEND_FILE = OUT / "openai_spend.json"
DEFAULT_CAP_USD = float(os.environ.get("CHROMERAG_OPENAI_CAP_USD", "1.80"))
_LOCK = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    env_file = os.environ.get("CHROMERAG_ENV_FILE")
    if not key and env_file and Path(env_file).exists():
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit("Set OPENAI_API_KEY (or CHROMERAG_ENV_FILE pointing at a .env file).")
    return key


def spent() -> float:
    if SPEND_FILE.exists():
        return float(json.loads(SPEND_FILE.read_text(encoding="utf-8"))["usd"])
    return 0.0


def _charge(model: str, tokens_in: int, tokens_out: int, cap: float) -> float:
    price_in, price_out = PRICES[model]
    cost = tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out
    with _LOCK:
        data = {"usd": 0.0, "calls": 0, "by_model": {}}
        if SPEND_FILE.exists():
            data = json.loads(SPEND_FILE.read_text(encoding="utf-8"))
        data["usd"] = round(data["usd"] + cost, 6)
        data["calls"] += 1
        m = data["by_model"].setdefault(model, {"usd": 0.0, "tokens_in": 0, "tokens_out": 0})
        m["usd"] = round(m["usd"] + cost, 6)
        m["tokens_in"] += tokens_in
        m["tokens_out"] += tokens_out
        SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
        SPEND_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if data["usd"] > cap:
        raise BudgetExceeded(f"OpenAI spend ${data['usd']:.3f} passed the ${cap:.2f} cap")
    return cost


class OpenAI:
    def __init__(self, *, cap_usd: float = DEFAULT_CAP_USD) -> None:
        self.cap = cap_usd
        self.client = httpx.Client(
            base_url=API,
            timeout=httpx.Timeout(120.0, connect=20.0),
            verify=_ssl_verify(),
            headers={"Authorization": f"Bearer {_api_key()}"},
        )

    def _post(self, path: str, payload: dict) -> dict:
        if spent() >= self.cap:
            raise BudgetExceeded(f"OpenAI spend already at ${spent():.3f} (cap ${self.cap:.2f})")
        for attempt in range(5):
            r = self.client.post(path, json=payload)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"OpenAI {path} {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError(f"OpenAI {path} kept failing after retries")

    def chat_json(self, model: str, system: str, user: str, *, effort: str = "low") -> tuple[dict, float]:
        data = self._post(
            "/chat/completions",
            {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
                "reasoning_effort": effort,
            },
        )
        usage = data.get("usage", {})
        cost = _charge(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), self.cap)
        return json.loads(data["choices"][0]["message"]["content"]), cost

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        data = self._post("/embeddings", {"model": model, "input": texts})
        _charge(model, data.get("usage", {}).get("prompt_tokens", 0), 0, self.cap)
        return [row["embedding"] for row in sorted(data["data"], key=lambda r: r["index"])]
