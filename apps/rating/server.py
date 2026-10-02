"""Blind human-rating app: stdlib only (http.server + sqlite3), no install needed.

  python -m poc.human_eval_build          # once: builds data/human_eval/
  python -m apps.rating.server            # then open http://localhost:8770

The page shows the original page (rendered, scripts removed, or HTML source) and four extractor outputs
labelled A-D in a random order per page. The key to which tool is which stays on the server until the
export. Ratings go to data/human_eval/ratings.sqlite and can be changed until you export.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "human_eval"
STATIC = Path(__file__).parent / "static"
DB = DATA / "ratings.sqlite"
PORT = 8770

SCHEMA = """
CREATE TABLE IF NOT EXISTS ratings (
  item_id TEXT PRIMARY KEY, best TEXT, scores TEXT, note TEXT, skipped INTEGER DEFAULT 0, updated REAL
)"""


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute(SCHEMA)
    return con


def load_items() -> list[dict]:
    return json.loads((DATA / "items.json").read_text(encoding="utf-8"))["items"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # quiet
        pass

    def _send(self, body: bytes, ctype: str = "application/json", code: int = 200, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(json.dumps(obj).encode(), code=code)

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        items = load_items()
        by_id = {i["id"]: i for i in items}
        if not parts:
            return self._send((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if parts == ["api", "items"]:
            with db() as con:
                done = {r[0]: r for r in con.execute("SELECT item_id, best, skipped FROM ratings")}
            return self._json([{"id": i["id"], "type": i["type"], "done": i["id"] in done} for i in items])
        if len(parts) == 3 and parts[:2] == ["api", "item"] and parts[2] in by_id:
            it = by_id[parts[2]]
            with db() as con:
                row = con.execute("SELECT best, scores, note, skipped FROM ratings WHERE item_id=?", (it["id"],)).fetchone()
            outs = {k: {"text": v, "words": len(v.split())} for k, v in it["outputs"].items()}
            rating = {"best": row[0], "scores": json.loads(row[1] or "{}"), "note": row[2], "skipped": bool(row[3])} if row else None
            return self._json({"id": it["id"], "type": it["type"], "url": it["url"], "outputs": outs, "rating": rating})
        if len(parts) == 2 and parts[0] == "html" and parts[1] in by_id:
            body = (DATA / "html" / f"{parts[1]}.html").read_bytes()
            return self._send(body, "text/html; charset=utf-8",
                              extra={"Content-Security-Policy": "script-src 'none'"})
        if len(parts) == 2 and parts[0] == "source" and parts[1] in by_id:
            body = (DATA / "raw" / f"{parts[1]}.html").read_bytes()[:400_000]
            return self._send(body, "text/plain; charset=utf-8")
        if parts == ["api", "export"]:
            with db() as con:
                rows = con.execute("SELECT item_id, best, scores, note, skipped FROM ratings").fetchall()
            force = parse_qs(url.query).get("force") == ["1"]
            if len(rows) < len(items) and not force:
                return self._json({"error": f"{len(rows)} of {len(items)} rated; finish first or add ?force=1"}, 409)
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["item_id", "type", "url", "best_label", "best_tool", "label", "tool", "content", "chrome", "note", "skipped"])
            for item_id, best, scores, note, skipped in rows:
                it = by_id[item_id]
                sc = json.loads(scores or "{}")
                for lab in "ABCD":
                    s = sc.get(lab, {})
                    w.writerow([item_id, it["type"], it["url"], best or "", it["key"].get(best or "", ""), lab, it["key"][lab],
                                s.get("content", ""), s.get("chrome", ""), note or "", skipped])
            return self._send(buf.getvalue().encode(), "text/csv; charset=utf-8",
                              extra={"Content-Disposition": "attachment; filename=human_ratings.csv"})
        self._send(b"not found", "text/plain", 404)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/rate":
            return self._send(b"not found", "text/plain", 404)
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if data.get("id") not in {i["id"] for i in load_items()}:
            return self._json({"error": "unknown id"}, 400)
        with db() as con:
            con.execute(
                "INSERT INTO ratings(item_id,best,scores,note,skipped,updated) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(item_id) DO UPDATE SET best=excluded.best, scores=excluded.scores, note=excluded.note, "
                "skipped=excluded.skipped, updated=excluded.updated",
                (data["id"], data.get("best"), json.dumps(data.get("scores", {})), data.get("note", ""),
                 1 if data.get("skipped") else 0, time.time()),
            )
        self._json({"ok": True})


def main() -> None:
    if not (DATA / "items.json").exists():
        sys.exit("Run `python -m poc.human_eval_build` first.")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Blind rating app: http://localhost:{PORT}  (Ctrl+C to stop). Ratings: {DB}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
