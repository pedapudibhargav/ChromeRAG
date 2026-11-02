"""Tests for the blind rating kit (stdlib; demo + synthetic corpora; no real data)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluators import run as rating  # noqa: E402
from evaluators.author import analyze as analyze_mod  # noqa: E402
from evaluators.author import build_bundle as build_mod  # noqa: E402

DEMO = ROOT / "evaluators" / "demo" / "bundle.json"
FORBIDDEN = ("chromerag", "trafilatura", "readability", "markitdown")
TOOLS = ["chromerag", "trafilatura", "readability"]


def _long_text(tag: str, n: int = 40) -> str:
    words = [f"{tag}word{i}" for i in range(n)]
    return " ".join(words)


def _write_synthetic_corpus(base: Path, *, n_article: int, n_forum: int) -> None:
    pages = []
    (base / "html").mkdir(parents=True)
    for tool in TOOLS:
        (base / "outputs" / tool).mkdir(parents=True)
    idx = 0
    for ptype, n in (("article", n_article), ("forum", n_forum)):
        for _ in range(n):
            pid = f"{ptype}{idx:02d}"
            idx += 1
            url = f"https://example.com/{pid}"
            html = (
                "<!doctype html><html><head><title>"
                f"{pid}</title></head><body><h1>{pid}</h1>"
                f"<p>{_long_text(pid, 30)}</p>"
                "<nav>menu chrome links</nav></body></html>"
            )
            rel = f"html/{pid}.html"
            (base / rel).write_text(html, encoding="utf-8")
            for i, tool in enumerate(TOOLS):
                # Distinct but long-enough outputs; no tool name in text.
                body = _long_text(f"{pid}out{i}", 40)
                (base / "outputs" / tool / f"{pid}.md").write_text(body, encoding="utf-8")
            pages.append({"id": pid, "url": url, "page_type": ptype, "html": rel})
    (base / "pages.json").write_text(json.dumps(pages, indent=2) + "\n", encoding="utf-8")


class TestDemoBundle(unittest.TestCase):
    def test_demo_has_no_tool_names(self) -> None:
        blob = DEMO.read_text(encoding="utf-8").lower()
        for bad in FORBIDDEN:
            self.assertNotIn(bad, blob)
        data = json.loads(DEMO.read_text(encoding="utf-8"))
        self.assertIn("bundle_id", data)
        self.assertGreaterEqual(len(data["items"]), 1)
        self.assertGreaterEqual(len(data["calibration"]), 1)
        for it in data["calibration"] + data["items"]:
            self.assertGreaterEqual(len(it["outputs"]), 2)


class TestBlinding(unittest.TestCase):
    def test_order_differs_by_rater_and_is_stable(self) -> None:
        bundle = json.loads(DEMO.read_text(encoding="utf-8"))
        o1, s1 = rating.plan_order(bundle, "alice")
        o1b, s1b = rating.plan_order(bundle, "alice")
        o2, s2 = rating.plan_order(bundle, "bob")
        self.assertEqual(o1, o1b)
        self.assertEqual(s1, s1b)
        cal = [it["item_id"] for it in bundle["calibration"]]
        self.assertEqual(o1[: len(cal)], cal)
        self.assertEqual(o2[: len(cal)], cal)
        self.assertTrue(o1 != o2 or any(s1[i] != s2[i] for i in s1))


class TestAtomicResume(unittest.TestCase):
    def test_atomic_write_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "alice_demo.json"
            res = rating.load_or_create_results(path, "alice", "demo-examples-site")
            res["items"]["x"] = {
                "item_id": "x",
                "best": ["A", "B"],
                "all_same": False,
                "none_good": False,
                "scores": {"A": {"content": 4, "chrome": 5}, "B": {"content": 4, "chrome": 4}},
                "skipped": False,
                "skip_reason": "",
                "seconds_spent": 1.5,
                "shown_order": ["B", "A"],
            }
            rating.atomic_write_json(path, res)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["items"]["x"]["best"], ["A", "B"])
            again = rating.load_or_create_results(path, "alice", "demo-examples-site")
            self.assertIn("x", again["items"])


class TestAppHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.mkdtemp()
        bundle = json.loads(DEMO.read_text(encoding="utf-8"))
        order, shown = rating.plan_order(bundle, "test")
        path = Path(cls._tmpdir) / "test_demo-examples-site.json"
        results = rating.load_or_create_results(path, "test", bundle["bundle_id"])
        rating.atomic_write_json(path, results)
        rating._STATE.clear()
        rating._STATE.update(
            {
                "rater": "test",
                "demo": True,
                "bundle": bundle,
                "by_id": rating._item_map(bundle),
                "order": order,
                "shown": shown,
                "results_path": path,
                "results": results,
                "lock": threading.Lock(),
            }
        )
        cls.httpd = rating.ThreadingHTTPServer(("127.0.0.1", 0), rating.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def _get(self, path: str) -> tuple[int, str]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        return resp.status, body

    def _post(self, path: str, payload: dict) -> tuple[int, dict]:
        raw = json.dumps(payload).encode("utf-8")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", path, body=raw, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return resp.status, body

    def test_index_and_session(self) -> None:
        code, html = self._get("/")
        self.assertEqual(code, 200)
        low = html.lower()
        for bad in FORBIDDEN:
            self.assertNotIn(bad, low)
        code, body = self._get("/api/session")
        self.assertEqual(code, 200)
        session = json.loads(body)
        self.assertTrue(session["items"][0]["is_calibration"])
        self.assertIn("rubric", session)

    def test_multiselect_saved(self) -> None:
        session = json.loads(self._get("/api/session")[1])
        iid = session["items"][0]["item_id"]
        item = json.loads(self._get(f"/api/item/{iid}")[1])
        labs = item["shown_order"]
        scores = {L: {"content": 3, "chrome": 4, "missing": "price table"} for L in labs}
        code, out = self._post(
            "/api/rate",
            {
                "item_id": iid,
                "best": labs[:2],
                "all_same": False,
                "none_good": False,
                "scores": scores,
                "skipped": False,
                "skip_reason": "",
                "seconds_spent": 2.0,
                "shown_order": labs,
            },
        )
        self.assertEqual(code, 200)
        self.assertTrue(out["ok"])
        saved = json.loads(Path(rating._STATE["results_path"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["items"][iid]["best"], labs[:2])
        self.assertEqual(saved["items"][iid]["scores"][labs[0]]["missing"], "price table")
        blob = json.dumps(saved).lower()
        for bad in FORBIDDEN:
            self.assertNotIn(bad, blob)

    def test_html_sandbox_headers(self) -> None:
        session = json.loads(self._get("/api/session")[1])
        iid = session["items"][0]["item_id"]
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/html/{iid}")
        resp = conn.getresponse()
        csp = resp.getheader("Content-Security-Policy") or ""
        body = resp.read().decode("utf-8").lower()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn("sandbox", csp.lower())
        for bad in FORBIDDEN:
            self.assertNotIn(bad, body)


class TestBuilderKeyPath(unittest.TestCase):
    def test_rejects_key_inside_bundle(self) -> None:
        with self.assertRaises(SystemExit):
            build_mod.forbid_key_path(ROOT / "evaluators" / "bundle" / "key.json")
        with self.assertRaises(SystemExit):
            build_mod.forbid_key_path(ROOT / "evaluators" / "results" / "key.json")
        build_mod.forbid_key_path(Path(tempfile.gettempdir()) / "rating_key.json")


class TestAnalyzerSynthetic(unittest.TestCase):
    def test_known_net_and_alpha(self) -> None:
        bundle = {
            "bundle_id": "syn",
            "calibration": [{"item_id": "cal1"}],
            "items": [{"item_id": "p1"}, {"item_id": "p2"}],
        }
        key = {
            "bundle_id": "syn",
            "tools": ["chromerag", "trafilatura"],
            "key": {
                "p1": {"A": "chromerag", "B": "trafilatura"},
                "p2": {"A": "trafilatura", "B": "chromerag"},
                "cal1": {"A": "chromerag", "B": "trafilatura"},
            },
        }

        def result(rater: str) -> dict:
            return {
                "schema_version": 1,
                "bundle_id": "syn",
                "rater": rater,
                "app_version": "1.0.0",
                "started": "t",
                "updated": "t",
                "items": {
                    "cal1": {
                        "item_id": "cal1",
                        "best": ["B"],
                        "all_same": False,
                        "none_good": False,
                        "scores": {"A": {"content": 1, "chrome": 1}, "B": {"content": 1, "chrome": 1}},
                        "skipped": False,
                        "seconds_spent": 1,
                        "shown_order": ["A", "B"],
                    },
                    "p1": {
                        "item_id": "p1",
                        "best": ["A"],
                        "all_same": False,
                        "none_good": False,
                        "scores": {"A": {"content": 5, "chrome": 5}, "B": {"content": 2, "chrome": 2}},
                        "skipped": False,
                        "seconds_spent": 3,
                        "shown_order": ["A", "B"],
                    },
                    "p2": {
                        "item_id": "p2",
                        "best": ["B"],
                        "all_same": False,
                        "none_good": False,
                        "scores": {"A": {"content": 2, "chrome": 2}, "B": {"content": 5, "chrome": 5}},
                        "skipped": False,
                        "seconds_spent": 4,
                        "shown_order": ["A", "B"],
                    },
                },
            }

        report = analyze_mod.analyse([result("r1"), result("r2")], bundle, key)
        focus = report["pairs"]["chromerag_vs_trafilatura"]
        self.assertEqual(focus["majority_net"]["net"], 1.0)
        self.assertEqual(focus["majority_net"]["wins_a"], 2)
        self.assertEqual(focus["majority_net"]["wins_b"], 0)
        self.assertEqual(focus["krippendorff_alpha"], 1.0)
        self.assertEqual(report["mean_scores"]["chromerag"]["n"], 4)
        self.assertEqual(report["missing_notes"], [])

    def test_missing_note_reported(self) -> None:
        """Analyzer surfaces a real missing-content note from a rating file."""
        bundle = {
            "bundle_id": "note-syn",
            "calibration": [],
            "items": [{"item_id": "p1"}],
        }
        key = {
            "bundle_id": "note-syn",
            "tools": ["chromerag", "trafilatura", "readability"],
            "key": {"p1": {"A": "chromerag", "B": "trafilatura", "C": "readability"}},
        }
        result = {
            "schema_version": 1,
            "bundle_id": "note-syn",
            "rater": "r1",
            "app_version": "1.0.0",
            "started": "t",
            "updated": "t",
            "items": {
                "p1": {
                    "item_id": "p1",
                    "best": ["A"],
                    "all_same": False,
                    "none_good": False,
                    "scores": {
                        "A": {"content": 4, "chrome": 5, "missing": ""},
                        "B": {"content": 2, "chrome": 3, "missing": "pricing table for Team plan"},
                        "C": {"content": 3, "chrome": 4, "missing": ""},
                    },
                    "skipped": False,
                    "seconds_spent": 5,
                    "shown_order": ["A", "B", "C"],
                }
            },
        }
        report = analyze_mod.analyse([result], bundle, key)
        self.assertEqual(len(report["missing_notes"]), 1)
        note = report["missing_notes"][0]
        self.assertEqual(note["rater"], "r1")
        self.assertEqual(note["item_id"], "p1")
        self.assertEqual(note["tool"], "trafilatura")
        self.assertEqual(note["note"], "pricing table for Team plan")


class TestFolderBundleBuilder(unittest.TestCase):
    def test_stratified_deterministic_and_blind(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            corpus = root / "corpus"
            _write_synthetic_corpus(corpus, n_article=8, n_forum=6)
            pages_out = root / "pages_out"
            out1 = root / "b1" / "bundle.json"
            key1 = root / "private" / "key.json"
            ord1 = root / "private" / "orders.json"
            kwargs = dict(
                tools=TOOLS,
                seed=42,
                n_pages=6,
                n_repeats=2,
                n_calibration=2,
                bundle_id="syn-folder",
                pages_out=pages_out,
                raters=["alice", "bob"],
            )
            b1, k1, o1 = build_mod.build_bundle_from_dir(corpus, **kwargs)
            build_mod.write_outputs(b1, k1, o1, out1, key1, ord1)
            b2, k2, o2 = build_mod.build_bundle_from_dir(corpus, **kwargs)
            self.assertEqual(b1, b2)
            self.assertEqual(k1["key"], k2["key"])
            self.assertEqual(o1, o2)
            self.assertEqual(len(b1["items"]), 6 + 2)  # main + repeats
            self.assertEqual(len(b1["calibration"]), 2)
            self.assertEqual(len(k1["repeat_of"]), 2)
            blob = out1.read_text(encoding="utf-8").lower()
            for bad in FORBIDDEN:
                self.assertNotIn(bad, blob)
            # page copies local only
            self.assertTrue(any(pages_out.glob("*.html")))
            # three outputs per item
            for it in b1["calibration"] + b1["items"]:
                self.assertEqual(sorted(it["outputs"]), ["A", "B", "C"])
            # orders saved separately and match app plan_order
            for rater, plan in o1.items():
                order, shown = rating.plan_order(b1, rater)
                self.assertEqual(plan["item_order"], order)
                self.assertEqual(plan["shown_order"], shown)


class TestSyntheticSessionEndToEnd(unittest.TestCase):
    def test_full_session_analyse_no_tool_leak(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            corpus = root / "corpus"
            _write_synthetic_corpus(corpus, n_article=5, n_forum=5)
            bundle, key_doc, orders = build_mod.build_bundle_from_dir(
                corpus,
                tools=TOOLS,
                seed=7,
                n_pages=4,
                n_repeats=1,
                n_calibration=1,
                bundle_id="e2e-syn",
                pages_out=root / "html_copies",
                raters=["e2e"],
            )
            out_bundle = root / "bundle.json"
            out_key = root / "key.json"
            out_orders = root / "orders.json"
            build_mod.write_outputs(bundle, key_doc, orders, out_bundle, out_key, out_orders)

            order, shown = rating.plan_order(bundle, "e2e")
            results_path = root / "e2e_e2e-syn.json"
            results = rating.load_or_create_results(results_path, "e2e", bundle["bundle_id"])
            rating.atomic_write_json(results_path, results)
            rating._STATE.clear()
            rating._STATE.update(
                {
                    "rater": "e2e",
                    "demo": False,
                    "bundle": bundle,
                    "by_id": rating._item_map(bundle),
                    "order": order,
                    "shown": shown,
                    "results_path": results_path,
                    "results": results,
                    "lock": threading.Lock(),
                }
            )
            httpd = rating.ThreadingHTTPServer(("127.0.0.1", 0), rating.Handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()

            def get(path: str) -> tuple[int, str]:
                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", path)
                resp = conn.getresponse()
                body = resp.read().decode("utf-8")
                conn.close()
                return resp.status, body

            def post(path: str, payload: dict) -> tuple[int, dict]:
                raw = json.dumps(payload).encode("utf-8")
                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("POST", path, body=raw, headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                body = json.loads(resp.read().decode("utf-8"))
                conn.close()
                return resp.status, body

            try:
                code, index_html = get("/")
                self.assertEqual(code, 200)
                code, session_raw = get("/api/session")
                self.assertEqual(code, 200)
                session = json.loads(session_raw)
                for bad in FORBIDDEN:
                    self.assertNotIn(bad, index_html.lower())
                    self.assertNotIn(bad, session_raw.lower())

                for meta in session["items"]:
                    iid = meta["item_id"]
                    code, item_raw = get(f"/api/item/{iid}")
                    self.assertEqual(code, 200)
                    for bad in FORBIDDEN:
                        self.assertNotIn(bad, item_raw.lower())
                    item = json.loads(item_raw)
                    labs = item["shown_order"]
                    scores = {
                        L: {
                            "content": 4,
                            "chrome": 4,
                            "missing": "team price row" if L == labs[0] else "",
                        }
                        for L in labs
                    }
                    code, out = post(
                        "/api/rate",
                        {
                            "item_id": iid,
                            "best": [labs[0]],
                            "all_same": False,
                            "none_good": False,
                            "scores": scores,
                            "skipped": False,
                            "skip_reason": "",
                            "seconds_spent": 1.0,
                            "shown_order": labs,
                        },
                    )
                    self.assertEqual(code, 200)
                    self.assertTrue(out["ok"])
                    for bad in FORBIDDEN:
                        self.assertNotIn(bad, json.dumps(out).lower())

                    code, html_body = get(f"/html/{iid}")
                    self.assertEqual(code, 200)
                    for bad in FORBIDDEN:
                        self.assertNotIn(bad, html_body.lower())
            finally:
                httpd.shutdown()

            saved = json.loads(results_path.read_text(encoding="utf-8"))
            for bad in FORBIDDEN:
                self.assertNotIn(bad, json.dumps(saved).lower())
            self.assertEqual(len(saved["items"]), len(order))

            report = analyze_mod.analyse([saved], bundle, key_doc)
            self.assertGreaterEqual(len(report["missing_notes"]), 1)
            cal_ids = {it["item_id"] for it in bundle["calibration"]}
            for n in report["missing_notes"]:
                self.assertNotIn(n["item_id"], cal_ids)


class TestNoSrcImportInApp(unittest.TestCase):
    def test_run_module_source_clean(self) -> None:
        src = (ROOT / "evaluators" / "run.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("chromerag", src)
        self.assertNotIn("from poc", src)
        self.assertNotIn("import poc", src)
        self.assertNotIn("sqlite", src)

    def test_handout_has_no_tool_names(self) -> None:
        text = (ROOT / "evaluators" / "HANDOUT.md").read_text(encoding="utf-8").lower()
        for bad in FORBIDDEN:
            self.assertNotIn(bad, text)
        self.assertIn("minutes each", text)
        self.assertNotIn("live site", text)


class TestSavedPagesAreOffline(unittest.TestCase):
    def test_sanitise_removes_everything_that_can_reach_a_site(self) -> None:
        from evaluators.author.build_bundle import sanitise

        html = (
            '<html><head><link rel="stylesheet" href="https://x.test/a.css"><base href="https://x.test/">'
            '<meta http-equiv="refresh" content="0;url=https://x.test/"><style>@import "https://x.test/b.css";'
            'p{background:url(https://x.test/c.png)}</style></head><body onload="go()">'
            '<a href="https://x.test/d">link text</a><img src="https://x.test/e.png" srcset="https://x.test/f.png 2x">'
            '<svg><image xlink:href="https://x.test/g.png"/></svg><form action="https://x.test/h"></form>'
            '<video poster="https://x.test/i.png"></video><p style="background:url(https://x.test/j.png)">kept</p>'
            '<script src="https://x.test/k.js"></script></body></html>'
        )
        out = sanitise(html, "https://x.test/")
        self.assertNotIn("x.test", out)
        self.assertIn("link text", out)
        self.assertIn("kept", out)


if __name__ == "__main__":
    unittest.main()
