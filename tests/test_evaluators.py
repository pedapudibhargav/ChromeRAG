"""Tests for the blind rating kit (stdlib; demo bundle only; no real data)."""

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
        # calibration first
        cal = [it["item_id"] for it in bundle["calibration"]]
        self.assertEqual(o1[: len(cal)], cal)
        self.assertEqual(o2[: len(cal)], cal)
        # main order or at least some shown_order differs across raters
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
        # outside is fine (no raise)
        build_mod.forbid_key_path(Path(tempfile.gettempdir()) / "rating_key.json")


class TestAnalyzerSynthetic(unittest.TestCase):
    def test_known_net_and_alpha(self) -> None:
        # Two items, two raters, chromerag always sole best for both -> net=1, alpha=1
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
        # calibration must not affect means of chromerag content (only p1/p2)
        self.assertEqual(report["mean_scores"]["chromerag"]["n"], 4)  # 2 raters × 2 items
        self.assertEqual(report["missing_notes"], [])


class TestNoSrcImportInApp(unittest.TestCase):
    def test_run_module_source_clean(self) -> None:
        src = (ROOT / "evaluators" / "run.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("chromerag", src)
        self.assertNotIn("from poc", src)
        self.assertNotIn("import poc", src)
        self.assertNotIn("sqlite", src)


if __name__ == "__main__":
    unittest.main()
