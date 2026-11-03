#!/usr/bin/env python3
"""Blind human-rating app. Standard library only. Bind 127.0.0.1.

  python evaluators/run.py --rater <id>
  python evaluators/run.py --rater test --demo
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html.parser
import json
import os
import random
import re
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

APP_VERSION = "1.0.0"
DEFAULT_PORT = 8770
EVAL_DIR = Path(__file__).resolve().parent
STATIC = EVAL_DIR / "static"
BUNDLE_PATH = EVAL_DIR / "bundle" / "bundle.json"
DEMO_BUNDLE_PATH = EVAL_DIR / "demo" / "bundle.json"
RESULTS_DIR = EVAL_DIR / "results"

# Module state set in main() before the server starts.
_STATE: dict[str, Any] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _seed_rng(rater: str, bundle_id: str) -> random.Random:
    digest = hashlib.sha256(f"{rater}\0{bundle_id}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _labels_for(outputs: dict) -> list[str]:
    return sorted(outputs.keys())


def plan_order(bundle: dict, rater: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return display item order and per-item label display order (bundle labels)."""
    rng = _seed_rng(rater, bundle["bundle_id"])
    cal = [it["item_id"] for it in bundle.get("calibration", [])]
    main = [it["item_id"] for it in bundle.get("items", [])]
    rng.shuffle(main)
    order = cal + main

    by_id = {it["item_id"]: it for it in list(bundle.get("calibration", [])) + list(bundle.get("items", []))}
    shown: dict[str, list[str]] = {}
    for iid in order:
        labs = _labels_for(by_id[iid]["outputs"])
        rng.shuffle(labs)
        shown[iid] = labs
    return order, shown


def results_path(rater: str, bundle_id: str) -> Path:
    safe_rater = re.sub(r"[^A-Za-z0-9._-]+", "_", rater.strip()) or "rater"
    safe_bundle = re.sub(r"[^A-Za-z0-9._-]+", "_", bundle_id.strip()) or "bundle"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR / f"{safe_rater}_{safe_bundle}.json"


def atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def load_or_create_results(path: Path, rater: str, bundle_id: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "bundle_id": bundle_id,
        "rater": rater,
        "app_version": APP_VERSION,
        "started": _utc_now(),
        "updated": _utc_now(),
        "items": {},
    }


_BREAK_TAGS = frozenset(
    "a address article aside blockquote br button dd div dl dt figcaption footer form h1 h2 h3 h4 h5 h6 "
    "header hr li main nav ol option p pre section select table tbody td th thead tr ul".split()
)


class _TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip += 1
        elif tag.lower() in _BREAK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        elif tag.lower() in _BREAK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip and data:
            self._chunks.append(data)

    def text(self) -> str:
        raw = re.sub(r"\s*\n\s*\n\s*", "\n\n", "".join(self._chunks))
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def visible_text(page_html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(page_html)
        parser.close()
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", page_html)
    return parser.text()


def simple_diff(a: str, b: str) -> str:
    lines_a = a.splitlines()
    lines_b = b.splitlines()
    return "\n".join(
        difflib.unified_diff(lines_a, lines_b, fromfile="left", tofile="right", lineterm="")
    )


def is_complete(entry: dict | None, labels: list[str]) -> bool:
    """A rating counts only when skipped, or with a choice and both scores for every output."""
    if not entry:
        return False
    if entry.get("skipped"):
        return True
    chosen = entry.get("all_same") or entry.get("none_good") or entry.get("best")
    scores = entry.get("scores") or {}
    return bool(chosen) and all(
        (scores.get(lab) or {}).get("content") and (scores.get(lab) or {}).get("chrome") for lab in labels
    )


def _item_map(bundle: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for it in bundle.get("calibration", []):
        out[it["item_id"]] = {**it, "is_calibration": True}
    for it in bundle.get("items", []):
        out[it["item_id"]] = {**it, "is_calibration": False}
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # quiet
        pass

    def _send(self, body: bytes, ctype: str = "application/json", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(json.dumps(obj).encode("utf-8"), code=code)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        bundle = _STATE["bundle"]
        by_id = _STATE["by_id"]
        order = _STATE["order"]
        shown = _STATE["shown"]
        results = _STATE["results"]

        if not parts:
            return self._send((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")

        if parts == ["api", "session"]:
            done = set(results.get("items", {}))
            items = []
            for iid in order:
                it = by_id[iid]
                items.append(
                    {
                        "item_id": iid,
                        "is_calibration": it["is_calibration"],
                        "done": is_complete(results["items"].get(iid), list(_STATE["by_id"][iid]["outputs"])),
                        "n_outputs": len(it["outputs"]),
                        "seconds": float((results["items"].get(iid) or {}).get("seconds_spent") or 0),
                    }
                )
            return self._json(
                {
                    "rater": _STATE["rater"],
                    "bundle_id": bundle["bundle_id"],
                    "app_version": APP_VERSION,
                    "results_path": str(_STATE["results_path"]),
                    "demo": _STATE["demo"],
                    "rubric": (
                        "Imagine a search assistant that can only read this text. People ask questions "
                        "this page should answer. Which output would give right answers most reliably?"
                    ),
                    "items": items,
                }
            )

        if len(parts) == 3 and parts[:2] == ["api", "item"]:
            iid = parts[2]
            if iid not in by_id:
                return self._json({"error": "unknown item"}, 404)
            it = by_id[iid]
            labs = shown[iid]
            outs = {
                lab: {"text": it["outputs"][lab], "words": len(it["outputs"][lab].split())}
                for lab in labs
            }
            rating = results.get("items", {}).get(iid)
            return self._json(
                {
                    "item_id": iid,
                    "is_calibration": it["is_calibration"],
                    "shown_order": labs,
                    "outputs": outs,
                    "rating": rating,
                }
            )

        if len(parts) == 2 and parts[0] == "html" and parts[1] in by_id:
            body = (by_id[parts[1]].get("page_html") or "").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; sandbox")
            self.end_headers()
            self.wfile.write(body)
            return

        if len(parts) == 2 and parts[0] == "text" and parts[1] in by_id:
            body = visible_text(by_id[parts[1]].get("page_html") or "").encode("utf-8")
            return self._send(body, "text/plain; charset=utf-8")

        if parts == ["api", "diff"]:
            qs = parse_qs(url.query)
            iid = (qs.get("item") or [""])[0]
            left = (qs.get("a") or [""])[0]
            right = (qs.get("b") or [""])[0]
            if iid not in by_id:
                return self._json({"error": "unknown item"}, 404)
            outs = by_id[iid]["outputs"]
            if left not in outs or right not in outs:
                return self._json({"error": "unknown label"}, 400)
            return self._json({"diff": simple_diff(outs[left], outs[right])})

        self._send(b"not found", "text/plain", 404)

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path != "/api/rate":
            return self._send(b"not found", "text/plain", 404)
        data = self._read_json()
        iid = data.get("item_id")
        if iid not in _STATE["by_id"]:
            return self._json({"error": "unknown item"}, 400)

        with _STATE["lock"]:
            results = _STATE["results"]
            entry = {
                "item_id": iid,
                "best": list(data.get("best") or []),
                "all_same": bool(data.get("all_same")),
                "none_good": bool(data.get("none_good")),
                "scores": data.get("scores") or {},
                "skipped": bool(data.get("skipped")),
                "skip_reason": data.get("skip_reason") or "",
                "seconds_spent": float(data.get("seconds_spent") or 0),
                "shown_order": list(data.get("shown_order") or _STATE["shown"][iid]),
            }
            results["items"][iid] = entry
            results["updated"] = _utc_now()
            atomic_write_json(_STATE["results_path"], results)
            _STATE["results"] = results
        self._json({"ok": True, "results_path": str(_STATE["results_path"])})


def load_bundle(path: Path) -> dict:
    if not path.exists():
        sys.exit(
            f"Bundle not found: {path}\n"
            "Put the private bundle.json at evaluators/bundle/bundle.json "
            "(or pass --demo for the practice set)."
        )
    bundle = json.loads(path.read_text(encoding="utf-8"))
    if "bundle_id" not in bundle:
        sys.exit("bundle.json must include bundle_id")
    return bundle


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Blind rating kit (local only)")
    parser.add_argument("--rater", required=True, help="Your rater id (letters/numbers; no personal data)")
    parser.add_argument("--demo", action="store_true", help="Use the committed demo bundle")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--bundle", type=Path, default=None, help="Override bundle path")
    args = parser.parse_args(argv)

    bundle_path = args.bundle or (DEMO_BUNDLE_PATH if args.demo else BUNDLE_PATH)
    bundle = load_bundle(bundle_path)
    order, shown = plan_order(bundle, args.rater)
    path = results_path(args.rater, bundle["bundle_id"])
    results = load_or_create_results(path, args.rater, bundle["bundle_id"])
    if results.get("bundle_id") != bundle["bundle_id"]:
        sys.exit("Existing results file is for a different bundle_id; choose another --rater id.")
    atomic_write_json(path, results)

    _STATE.clear()
    _STATE.update(
        {
            "rater": args.rater,
            "demo": bool(args.demo),
            "bundle": bundle,
            "by_id": _item_map(bundle),
            "order": order,
            "shown": shown,
            "results_path": path,
            "results": results,
            "lock": threading.Lock(),
        }
    )

    host = "127.0.0.1"
    srv = ThreadingHTTPServer((host, args.port), Handler)
    url = f"http://{host}:{args.port}/"
    print(f"Blind rating app: {url}")
    print(f"Rater: {args.rater}  Bundle: {bundle['bundle_id']}  Results: {path}")
    print("Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
