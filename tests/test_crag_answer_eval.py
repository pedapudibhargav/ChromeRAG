"""Offline tests for poc.crag_answer_eval — fake LLM, synthetic CRAG jsonl, no network."""

from __future__ import annotations

import bz2
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from poc import crag_answer_eval as m

HTML_A = """<!DOCTYPE html><html><body>
<main><h1>Paris Facts</h1><p>The capital of France is Paris. It has the Eiffel Tower.</p></main>
<nav>Home About Cookies Subscribe</nav>
</body></html>"""

HTML_B = """<!DOCTYPE html><html><body>
<main><h1>River</h1><p>The Seine river flows through Paris.</p></main>
<footer>Privacy policy Newsletter</footer>
</body></html>"""

HTML_NOISE = """<!DOCTYPE html><html><body>
<nav>Buy now Sign up Accept all cookies Related products</nav>
<main><p>Unrelated filler text about sports scores and weather.</p></main>
</body></html>"""


def _rec(
    *,
    iid: str,
    query: str,
    answer: str,
    split: int = 0,
    popularity: str = "",
    question_type: str = "simple",
    static_or_dynamic: str = "static",
    domain: str = "open",
    alt_ans: list | None = None,
    pages: list[tuple[str, str]] | None = None,
    query_time: str | None = None,
) -> dict:
    pages = pages or [
        ("https://example.com/a", HTML_A),
        ("https://example.com/b", HTML_B),
        ("https://example.com/c", HTML_NOISE),
        ("https://example.com/d", HTML_A),
        ("https://example.com/e", HTML_B),
    ]
    row = {
        "interaction_id": iid,
        "split": split,
        "popularity": popularity,
        "question_type": question_type,
        "static_or_dynamic": static_or_dynamic,
        "query": query,
        "answer": answer,
        "alt_ans": alt_ans or [],
        "domain": domain,
        "search_results": [
            {
                "page_url": url,
                "page_result": html,
                "page_name": url,
                "page_snippet": "",
                "page_last_modified": None,
            }
            for url, html in pages
        ],
    }
    if query_time is not None:
        row["query_time"] = query_time
    return row


def write_synthetic_bz2(path: Path, records: list[dict]) -> Path:
    with bz2.open(path, "wt", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return path


@pytest.fixture
def synthetic_data(tmp_path: Path) -> Path:
    records = [
        _rec(iid="q_ok_1", query="What is the capital of France?", answer="Paris"),
        _rec(iid="q_ok_2", query="Which river flows through Paris?", answer="Seine"),
        _rec(
            iid="q_split1",
            query="ignored split",
            answer="x",
            split=1,
        ),
        _rec(
            iid="q_pop",
            query="head question",
            answer="x",
            popularity="head",
        ),
        _rec(
            iid="q_fp",
            query="false premise",
            answer="x",
            question_type="false_premise",
        ),
        _rec(
            iid="q_fast",
            query="fast",
            answer="x",
            static_or_dynamic="fast-changing",
        ),
        _rec(
            iid="q_rt",
            query="realtime",
            answer="x",
            static_or_dynamic="real-time",
        ),
        _rec(
            iid="q_inv",
            query="bad",
            answer="invalid question",
        ),
        _rec(
            iid="q_ok_3",
            query="Where is the Eiffel Tower?",
            answer="Paris",
            domain="travel",
        ),
    ]
    return write_synthetic_bz2(tmp_path / "crag_synth.jsonl.bz2", records)


class FakeClient:
    """Deterministic stand-in for OpenAIClient; no network."""

    def __init__(
        self,
        *,
        max_usd: float = 100.0,
        fail_after: int | None = None,
        unparseable_times: int = 0,
        starting_spend_usd: float = 0.0,
    ) -> None:
        self.max_usd = max_usd
        self.spend_usd = float(starting_spend_usd)
        self.spend_this_run = 0.0
        self.calls = 0
        self.fail_after = fail_after
        self.seen_prompts: list[tuple[str, str]] = []
        self.lock = threading.Lock()
        self.price_in = 0.20
        self.price_out = 0.75
        self.unparseable_times = unparseable_times
        self._unparseable_left = unparseable_times
        self.temperature_dropped_generate = False
        self.temperature_dropped_judge = False
        self.last_max_completion_tokens: int | None = None
        self.seen_kwargs: list[dict] = []

    def chat(
        self,
        model: str,
        system: str,
        user: str,
        *,
        temperature: float | None = 0.0,
        json_mode: bool = False,
        max_completion_tokens: int | None = None,
        purpose: str = "generate",
    ) -> tuple[str, float, dict]:
        with self.lock:
            self.calls += 1
            self.seen_prompts.append((system, user))
            self.seen_kwargs.append(
                {
                    "max_completion_tokens": max_completion_tokens,
                    "purpose": purpose,
                    "json_mode": json_mode,
                }
            )
            self.last_max_completion_tokens = max_completion_tokens
            if self.fail_after is not None and self.calls > self.fail_after:
                raise m.BudgetExceeded("fake budget")
            cost = 0.001
            self.spend_usd = round(self.spend_usd + cost, 6)
            self.spend_this_run = round(self.spend_this_run + cost, 6)
            if self.spend_usd > self.max_usd:
                raise m.BudgetExceeded("fake budget")
            tin, tout = 10, 5
        if json_mode:
            assert "trafilatura" not in user.lower()
            assert "markitdown" not in user.lower()
            assert "chromerag" not in user.lower()
            assert "Context:" not in user
            if self._unparseable_left > 0:
                self._unparseable_left -= 1
                return "NOT JSON", cost, {
                    "prompt_tokens": tin,
                    "completion_tokens": tout,
                    "finish_reason": "stop",
                }
            gen = user.split("Generated answer:", 1)[-1].strip().lower()
            gold = user.split("Gold answer:", 1)[-1].split("\n", 1)[0].strip().lower()
            if gold and gold in gen:
                label = "accurate"
            elif "wrong" in gen:
                label = "incorrect"
            else:
                label = "missing"
            payload: dict = {"label": label, "reason": "fake"}
            # v2 rubric requires rule_id; map labels to a stable rule.
            if "rule_id" in system or "R-PART" in system:
                payload["rule_id"] = {
                    "accurate": "R-REQ",
                    "incorrect": "R-WRONG",
                    "missing": "R-MISS",
                }[label]
            return json.dumps(payload), cost, {
                "prompt_tokens": tin,
                "completion_tokens": tout,
                "finish_reason": "stop",
            }
        ctx = user.lower()
        if "capital of france" in user.lower() and "paris" in ctx:
            return "Paris", cost, {
                "prompt_tokens": tin,
                "completion_tokens": tout,
                "finish_reason": "stop",
            }
        if "seine" in ctx and "river" in user.lower():
            return "Seine", cost, {
                "prompt_tokens": tin,
                "completion_tokens": tout,
                "finish_reason": "stop",
            }
        if "eiffel" in user.lower() and "paris" in ctx:
            return "Paris", cost, {
                "prompt_tokens": tin,
                "completion_tokens": tout,
                "finish_reason": "stop",
            }
        return "I don't know", cost, {
            "prompt_tokens": tin,
            "completion_tokens": tout,
            "finish_reason": "stop",
        }


def _args(synthetic_data: Path, tmp_path: Path, **over) -> SimpleNamespace:
    base = dict(
        data=synthetic_data,
        cache_dir=tmp_path / "cache",
        out=tmp_path / "out.json",
        n=2,
        seed=0,
        limit=None,
        split=0,
        model=m.MODEL,
        max_usd=50.0,
        price_in=0.2,
        price_out=0.75,
        ca_bundle=None,
        workers=2,
        extract_workers=2,
        page_timeout=0.0,
        dry_run=False,
        max_completion_tokens_generate=4096,
        max_completion_tokens_judge=1024,
        rejudge_only=False,
        from_cache=None,
        prior_out=None,
        rubric="v1",
        calibrate=None,
        locked_split_1=False,
    )
    base.update(over)
    return SimpleNamespace(**base)


@pytest.mark.baselines
def test_rejudge_dry_run_reads_from_cache(synthetic_data: Path, tmp_path: Path):
    args = _args(
        synthetic_data,
        tmp_path,
        n=2,
        dry_run=True,
        rejudge_only=True,
        rubric="v2",
        from_cache=tmp_path / "old_cache",
        cache_dir=tmp_path / "new_cache",
        out=tmp_path / "rejudge.json",
        prior_out=tmp_path / "base.json",
    )
    client = FakeClient()
    m.run(
        _args(synthetic_data, tmp_path, n=2, cache_dir=tmp_path / "old_cache", out=tmp_path / "base.json"),
        client_factory=lambda: client,
    )
    report = m.run_rejudge_only(args)
    assert report["dry_run"] is True
    assert report["rubric"] == "v2"
    assert report["judge"]["judge_calls"] >= 0


@pytest.mark.baselines
def test_rejudge_only_answers_from_old_cache_no_tool_names(synthetic_data: Path, tmp_path: Path):
    old_cache = tmp_path / "old_cache"
    new_cache = tmp_path / "new_cache"
    base_out = tmp_path / "base.json"
    m.run(
        _args(synthetic_data, tmp_path, n=2, cache_dir=old_cache, out=base_out),
        client_factory=lambda: FakeClient(),
    )
    # Snapshot original cache tree; rejudge must not mutate it.
    before = {
        p.relative_to(old_cache).as_posix(): p.read_bytes()
        for p in old_cache.rglob("*")
        if p.is_file()
    }
    client = FakeClient()
    report = m.run_rejudge_only(
        _args(
            synthetic_data,
            tmp_path,
            n=2,
            rejudge_only=True,
            rubric="v2",
            from_cache=old_cache,
            cache_dir=new_cache,
            out=tmp_path / "rejudge.json",
            prior_out=base_out,
        ),
        client_factory=lambda: client,
    )
    assert report["model"] == m.MODEL
    assert report["rubric"] == "v2"
    assert "label_changes_v1_v2_by_tool" in report
    after = {
        p.relative_to(old_cache).as_posix(): p.read_bytes()
        for p in old_cache.rglob("*")
        if p.is_file()
    }
    assert after == before
    for system, user in client.seen_prompts:
        if "Generated answer:" not in user:
            continue
        low = user.lower()
        assert "trafilatura" not in low
        assert "markitdown" not in low
        assert "chromerag" not in low
        assert "rule_id" in system or "R-PART" in system


@pytest.mark.baselines
def test_rejudge_identical_qa_graded_once(synthetic_data: Path, tmp_path: Path):
    old_cache = tmp_path / "old_cache"
    m.run(
        _args(synthetic_data, tmp_path, n=1, cache_dir=old_cache, out=tmp_path / "base.json"),
        client_factory=lambda: FakeClient(),
    )
    client = FakeClient()
    m.run_rejudge_only(
        _args(
            synthetic_data,
            tmp_path,
            n=1,
            rejudge_only=True,
            rubric="v2",
            from_cache=old_cache,
            cache_dir=tmp_path / "new_cache",
            out=tmp_path / "rejudge.json",
            prior_out=tmp_path / "base.json",
        ),
        client_factory=lambda: client,
    )
    judge_calls = sum(1 for _s, u in client.seen_prompts if "Generated answer:" in u)
    # One unique question+answer across tools → one LLM judge call.
    assert judge_calls == 1


@pytest.mark.baselines
def test_rejudge_idk_same_v1_v2_change_table(tmp_path: Path, synthetic_data: Path):
    old_cache = tmp_path / "old_cache"
    base_out = tmp_path / "base.json"
    m.run(
        _args(synthetic_data, tmp_path, n=1, cache_dir=old_cache, out=base_out),
        client_factory=lambda: FakeClient(),
    )
    questions = [
        r for r in m.load_crag_records(synthetic_data) if r["interaction_id"] == "q_ok_1"
    ][:1]
    qid = m.question_id(questions[0])
    extracts = m.load_cached_extracts(questions, from_cache=old_cache)
    retrievals = m.load_cached_retrievals(questions, extracts, from_cache=old_cache)
    for tool in m.TOOLS:
        chunks = retrievals[qid][tool].get("chunks") or []
        system, _ = m.generate_prompt(questions[0]["query"], chunks)
        key = m.generate_cache_key(
            query=questions[0]["query"],
            chunks=chunks,
            model=m.MODEL,
            prompt_system=system,
        )
        m.write_json_cache(
            m.cache_path(old_cache, "generate", key[:2], f"{key}.json"),
            {"answer": "I don't know", "finish_reason": "stop", "cost_usd": 0.0, "usage": {}},
        )
    # Remove any prior rule labels so v1 load must synthesize the same IDK rule as v2.
    rule_root = old_cache / "judge" / "rule"
    if rule_root.exists():
        for p in rule_root.rglob("*.json"):
            p.unlink()
    client = FakeClient()
    report = m.run_rejudge_only(
        _args(
            synthetic_data,
            tmp_path,
            n=1,
            rejudge_only=True,
            rubric="v2",
            from_cache=old_cache,
            cache_dir=tmp_path / "new_cache_idk",
            out=tmp_path / "rejudge_idk.json",
            prior_out=base_out,
        ),
        client_factory=lambda: client,
    )
    assert client.calls == 0
    assert all(not c for c in report["label_changes_v1_v2_by_tool"].values())


@pytest.mark.baselines
def test_rejudge_budget_keeps_earned_labels(synthetic_data: Path, tmp_path: Path):
    old_cache = tmp_path / "old_cache"
    m.run(
        _args(synthetic_data, tmp_path, n=2, cache_dir=old_cache, out=tmp_path / "base.json"),
        client_factory=lambda: FakeClient(),
    )
    new_cache = tmp_path / "new_cache_budget"
    client = FakeClient(max_usd=0.001, fail_after=1)
    report = m.run_rejudge_only(
        _args(
            synthetic_data,
            tmp_path,
            n=2,
            rejudge_only=True,
            rubric="v2",
            from_cache=old_cache,
            cache_dir=new_cache,
            out=tmp_path / "rejudge_budget.json",
            prior_out=tmp_path / "base.json",
            max_usd=0.001,
        ),
        client_factory=lambda: client,
    )
    assert report["partial"] is True
    assert (tmp_path / "rejudge_budget.json").exists()
    assert any(new_cache.joinpath("judge").rglob("*.json"))
    assert isinstance(report["label_changes_v1_v2_by_tool"], dict)


def test_rejudge_rejects_same_from_cache_and_cache_dir(synthetic_data: Path, tmp_path: Path):
    shared = tmp_path / "shared"
    shared.mkdir()
    with pytest.raises(SystemExit, match="differ"):
        m.run_rejudge_only(
            _args(
                synthetic_data,
                tmp_path,
                rejudge_only=True,
                rubric="v2",
                from_cache=shared,
                cache_dir=shared,
                out=tmp_path / "out.json",
            )
        )


def test_locked_split_1_required_for_rejudge(synthetic_data: Path, tmp_path: Path):
    with pytest.raises(ValueError, match="only split"):
        m.run_rejudge_only(
            _args(
                synthetic_data,
                tmp_path,
                split=1,
                locked_split_1=False,
                rejudge_only=True,
                rubric="v2",
                from_cache=tmp_path / "old",
                cache_dir=tmp_path / "new",
                out=tmp_path / "out.json",
            )
        )


def test_enforce_split_raises():
    with pytest.raises(ValueError, match="only split==0"):
        m.enforce_split(1)
    with pytest.raises(ValueError, match="only split==0"):
        m.load_crag_records(Path("/dev/null"), split=2)


def test_load_only_split0(synthetic_data: Path):
    rows = m.load_crag_records(synthetic_data, split=0)
    assert all(int(r["split"]) == 0 for r in rows)
    assert not any(r["interaction_id"] == "q_split1" for r in rows)


def test_filter_exclusion_counts(synthetic_data: Path):
    rows = m.load_crag_records(synthetic_data, split=0)
    kept, counts = m.filter_web_static(rows)
    ids = {r["interaction_id"] for r in kept}
    assert ids == {"q_ok_1", "q_ok_2", "q_ok_3"}
    assert counts["excluded_nonempty_popularity"] == 1
    assert counts["excluded_false_premise"] == 1
    assert counts["excluded_fast_or_realtime"] == 2
    assert counts["excluded_invalid_question"] == 1


def test_sample_seed_stable(synthetic_data: Path):
    rows = m.load_crag_records(synthetic_data)
    kept, _ = m.filter_web_static(rows)
    a = [m.question_id(r) for r in m.sample_questions(kept, 2, seed=7)]
    b = [m.question_id(r) for r in m.sample_questions(kept, 2, seed=7)]
    c = [m.question_id(r) for r in m.sample_questions(kept, 2, seed=8)]
    assert a == b
    assert a != c


def test_idk_labelled_missing_without_llm(tmp_path: Path):
    client = FakeClient()
    questions = [_rec(iid="q1", query="Who?", answer="Nobody")]
    generations = {"q1": {"trafilatura": {"answer": "I don't know"}}}
    judgements, _ = m.run_judge(
        questions,
        generations,
        tools=("trafilatura",),
        cache_dir=tmp_path / "cache",
        client=client,
        model="fake",
        seed=0,
        workers=1,
    )
    assert judgements["q1"]["trafilatura"]["label"] == "missing"
    assert judgements["q1"]["trafilatura"]["reason"] == "idk_rule"
    assert client.calls == 0


def test_judge_dedup_shared_cache(tmp_path: Path):
    client = FakeClient()
    q = "What is the capital of France?"
    questions = [
        _rec(iid="a", query=q, answer="Paris"),
        _rec(iid="b", query=q, answer="Paris"),
    ]
    generations = {
        "a": {"trafilatura": {"answer": "Paris"}},
        "b": {"trafilatura": {"answer": "Paris"}},
    }
    judgements, info = m.run_judge(
        questions,
        generations,
        tools=("trafilatura",),
        cache_dir=tmp_path / "cache",
        client=client,
        model="fake",
        seed=0,
        workers=1,
    )
    assert client.calls == 1
    assert judgements["a"]["trafilatura"]["label"] == "accurate"
    assert judgements["b"]["trafilatura"]["label"] == "accurate"
    assert info["judge_calls"] == 1


def test_gold_in_top5_short_only():
    assert m.gold_in_top5("Paris", ["The capital is Paris today"]) is True
    assert m.gold_in_top5("Paris", ["No capital here"]) is False
    assert m.gold_in_top5("a b c d e f", ["a b c d e f"]) is None


def test_retrieve_bm25_top_chunks():
    pages = [
        "The capital of France is Paris and it is beautiful.",
        "Unrelated sports content about basketball scores tonight.",
    ]
    result = m.retrieve_for_tool("capital of France Paris", pages, top_k=2)
    assert result["chunks"]
    assert "Paris" in result["chunks"][0]


@pytest.mark.baselines
def test_dry_run_token_estimate(synthetic_data: Path, tmp_path: Path, capsys):
    args = _args(synthetic_data, tmp_path, dry_run=True, n=2, price_in=1.0, price_out=2.0)
    report = m.run(args, client_factory=lambda: FakeClient())
    assert report["dry_run"] is True
    te = report["token_estimate"]
    assert te["generate"]["generate_calls"] >= 1
    assert te["total_est_usd"] > 0
    printed = capsys.readouterr().out
    assert "est_prompt_tokens=" in printed
    assert "est_usd=" in printed


@pytest.mark.baselines
def test_end_to_end_fake_client(synthetic_data: Path, tmp_path: Path):
    args = _args(synthetic_data, tmp_path, n=3, model="fake-model", out=tmp_path / "report.json")
    report = m.run(args, client_factory=lambda: FakeClient())
    assert args.out.exists()
    assert set(report["chosen_question_ids"]) <= {"q_ok_1", "q_ok_2", "q_ok_3"}
    assert "excluded_false_premise" in report["exclusion_counts"]
    assert report["model"] == "fake-model"
    assert "git_commit" in report
    assert "spend_this_run" in report and "spend_total" in report
    for tool in m.TOOLS:
        row = report["tools"][tool]
        assert row["n"] == 3
        assert row["accurate"] is not None
        assert row["crag_score"] is not None
        assert "by_domain" in row
        assert row["mean_words_per_page_including_failed"] is not None
        assert row["mean_words_per_page_excluding_failed"] is not None
        assert "n_pages_empty" in row
        assert "extractor_config" in row
    comps = {b["comparison"] for b in report["paired_bootstrap_crag"]}
    assert "markitdown - trafilatura" in comps
    assert "chromerag_coverage - chromerag_balanced" in comps
    report2 = m.run(args, client_factory=lambda: FakeClient())
    assert report2["tools"]["trafilatura"]["n"] == 3


@pytest.mark.baselines
def test_budget_stops_partial(synthetic_data: Path, tmp_path: Path):
    """1: BudgetExceeded during judge/generate reports partial=True."""
    args = _args(
        synthetic_data,
        tmp_path,
        n=2,
        max_usd=0.001,
        cache_dir=tmp_path / "cache_budget",
        out=tmp_path / "partial.json",
        workers=1,
    )
    report = m.run(args, client_factory=lambda: FakeClient(max_usd=0.001, fail_after=1))
    assert args.out.exists()
    assert report.get("partial") is True


def test_intersection_rates_drop_unlabelled(tmp_path: Path):
    """2: rates use only fully-labelled intersection; unlabelled never scores 0."""
    questions = [
        _rec(iid="q1", query="Q1", answer="A"),
        _rec(iid="q2", query="Q2", answer="B"),
    ]
    judgements = {
        "q1": {
            "trafilatura": {"label": "accurate"},
            "markitdown": {"label": "incorrect"},
        },
        "q2": {
            "trafilatura": {"label": "accurate"},
            # markitdown missing → drop q2
        },
    }
    extracts = {
        "q1": {
            "trafilatura": [{"ok": True, "words": 10, "empty": False}],
            "markitdown": [{"ok": True, "words": 10, "empty": False}],
        },
        "q2": {
            "trafilatura": [{"ok": True, "words": 10, "empty": False}],
            "markitdown": [{"ok": True, "words": 10, "empty": False}],
        },
    }
    retrievals = {
        "q1": {"trafilatura": {"chunks": ["A"]}, "markitdown": {"chunks": ["A"]}},
        "q2": {"trafilatura": {"chunks": ["B"]}, "markitdown": {"chunks": ["B"]}},
    }
    tools = ("trafilatura", "markitdown")
    report = m.summarize(
        questions,
        extracts,
        retrievals,
        judgements,
        tools=tools,
        seed=0,
        model="fake",
        spend_usd=0.0,
        exclusion_counts={},
        chosen_ids=["q1", "q2"],
        partial=True,
    )
    assert report["n_scored"] == 1
    assert report["n_dropped_incomplete_labels"] == 1
    assert report["tools"]["trafilatura"]["n"] == 1
    # Bootstrap vectors length matches intersection only.
    boot = report["paired_bootstrap_crag"]
    assert boot[0]["mean_diff"] is not None


def test_judge_unparseable_retries_then_error(tmp_path: Path):
    """3: unparseable judge output retries twice, then judge_error, not cached as label."""
    client = FakeClient(unparseable_times=3)  # initial + 2 retries all bad
    questions = [_rec(iid="q1", query="Capital?", answer="Paris")]
    generations = {"q1": {"trafilatura": {"answer": "Paris"}}}
    judgements, info = m.run_judge(
        questions,
        generations,
        tools=("trafilatura",),
        cache_dir=tmp_path / "cache",
        client=client,
        model="fake",
        seed=0,
        workers=1,
    )
    assert client.calls == 3
    assert "trafilatura" not in judgements.get("q1", {})
    assert info["judge_errors"] == 1
    # Nothing cached as a label under judge/
    judge_files = list((tmp_path / "cache" / "judge").rglob("*.json"))
    assert judge_files == []


def test_mid_batch_caches_successes(tmp_path: Path):
    """4: each future handled alone; successes cached when a later future fails."""
    client = FakeClient(fail_after=1)
    questions = [
        _rec(iid="q1", query="What is the capital of France?", answer="Paris"),
        _rec(iid="q2", query="Which river flows through Paris?", answer="Seine"),
    ]
    retrievals = {
        "q1": {"trafilatura": {"chunks": ["The capital of France is Paris"]}},
        "q2": {"trafilatura": {"chunks": ["The Seine river flows through Paris"]}},
    }
    with pytest.raises(m.BudgetExceeded):
        m.run_generate(
            questions,
            retrievals,
            tools=("trafilatura",),
            cache_dir=tmp_path / "cache",
            client=client,
            model="fake",
            workers=1,
        )
    cached = list((tmp_path / "cache" / "generate").rglob("*.json"))
    assert len(cached) >= 1


def test_charge_keeps_over_cap_response():
    """5: crossing cap keeps the response; next call raises; counters locked."""
    client = m.OpenAIClient.__new__(m.OpenAIClient)
    client.max_usd = 0.000001
    client.price_in = 1.0
    client.price_out = 1.0
    client.spend_usd = 0.0
    client.spend_this_run = 0.0
    client.tokens_in = 0
    client.tokens_out = 0
    client.calls = 0
    client._reserved = 0.0
    client._lock = threading.Lock()
    cost = client._charge(1000, 1000)  # large enough to exceed tiny cap
    assert cost > 0
    assert client.spend_usd > client.max_usd
    assert client.calls == 1
    with pytest.raises(m.BudgetExceeded):
        client._reserve(0.000001)


def test_max_completion_tokens_and_empty_answer(tmp_path: Path):
    """6: max_completion_tokens passed; empty answer → missing; length empty separate."""
    client = FakeClient()
    questions = [_rec(iid="q1", query="Who?", answer="X")]
    generations = {
        "q1": {
            "trafilatura": {"answer": "", "finish_reason": "stop"},
            "markitdown": {"answer": "", "finish_reason": "length"},
        }
    }
    judgements, info = m.run_judge(
        questions,
        generations,
        tools=("trafilatura", "markitdown"),
        cache_dir=tmp_path / "cache",
        client=client,
        model="fake",
        seed=0,
        workers=1,
        max_completion_tokens=512,
    )
    assert judgements["q1"]["trafilatura"]["reason"] == "empty_answer"
    assert judgements["q1"]["markitdown"]["reason"] == "empty_answer_length"
    assert info["empty_answer"] == 1
    assert info["empty_answer_length"] == 1
    assert client.calls == 0

    # generate path records finish_reason / max tokens
    retrievals = {"q1": {"trafilatura": {"chunks": ["hello paris capital of france"]}}}
    questions = [_rec(iid="q1", query="What is the capital of France?", answer="Paris")]
    gens, _ = m.run_generate(
        questions,
        retrievals,
        tools=("trafilatura",),
        cache_dir=tmp_path / "cache2",
        client=client,
        model="fake",
        workers=1,
        max_completion_tokens=2048,
    )
    assert client.last_max_completion_tokens == 2048
    assert gens["q1"]["trafilatura"]["finish_reason"] == "stop"


def test_retry_usage_from_error_body():
    """7: usage in any response body is counted."""
    client = m.OpenAIClient.__new__(m.OpenAIClient)
    client.max_usd = 100.0
    client.price_in = 1.0
    client.price_out = 1.0
    client.spend_usd = 0.0
    client.spend_this_run = 0.0
    client.tokens_in = 0
    client.tokens_out = 0
    client.calls = 0
    client._reserved = 0.0
    client._lock = threading.Lock()
    body = json.dumps({"usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0}})
    client._maybe_charge_response_body(body)
    assert client.spend_usd == pytest.approx(1.0)


def test_persisted_spend_across_runs(tmp_path: Path):
    """8: spend persisted in cache dir; max-usd enforced across resumes."""
    cache = tmp_path / "cache"
    m.save_persisted_spend(cache, 4.5)
    assert m.load_persisted_spend(cache) == pytest.approx(4.5)
    client = m.OpenAIClient.__new__(m.OpenAIClient)
    client.max_usd = 5.0
    client.spend_usd = 4.5
    client._reserved = 0.0
    client._lock = threading.Lock()
    with pytest.raises(m.BudgetExceeded):
        client._reserve(1.0)


@pytest.mark.baselines
def test_dry_run_judge_no_tool_dedup(synthetic_data: Path, tmp_path: Path):
    """9: dry-run judge estimate assumes no dedup across tools."""
    args = _args(synthetic_data, tmp_path, dry_run=True, n=2)
    report = m.run(args, client_factory=lambda: FakeClient())
    n_q = len(report["chosen_question_ids"])
    # Placeholder answers differ per tool → one estimated call per (q, tool).
    assert report["token_estimate"]["judge"]["judge_calls"] == n_q * len(m.TOOLS)


def test_markitdown_missing_raises_at_startup(monkeypatch):
    """10: harness verifies tools importable before work."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "markitdown" or name.startswith("markitdown."):
            raise ImportError("simulated missing markitdown")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="not importable"):
        m.verify_tools_importable(("markitdown",))


def test_page_timeout_kills_worker():
    """11: real per-page timeout kills the worker process."""
    result = m.run_extract_job_with_timeout(
        {"tool": "trafilatura", "html": "<p>x</p>", "url": None, "_sleep": 5},
        page_timeout=0.4,
    )
    assert result["timeout"] is True
    assert "page_timeout" in result["error"]


def test_infra_failure_not_cached(tmp_path: Path):
    """12: BrokenProcessPool-style failures are not cached."""
    assert m.is_infrastructure_failure({"error": "BrokenProcessPool: boom"})
    cache = tmp_path / "cache"
    questions = [
        _rec(
            iid="q1",
            query="Q",
            answer="A",
            pages=[("https://example.com", HTML_A)],
        )
    ]

    def boom(_payload):
        return {
            "ok": False,
            "text": "",
            "empty": True,
            "error": "BrokenProcessPool: boom",
            "timeout": False,
            "words": 0,
            "seconds": 0.0,
        }

    import unittest.mock as um

    with um.patch.object(m.ExtractWorkerPool, "run", side_effect=boom):
        out = m.run_extract(
            questions, tools=("trafilatura",), cache_dir=cache, page_timeout=1.0
        )
    cached = list((cache / "extract").rglob("*.json"))
    assert cached == []
    assert out["q1"]["trafilatura"][0]["error"] == "missing_cache"


def test_cache_keys_hash_full_inputs():
    """13: cache keys include html/tool/version/config/model/prompts."""
    k1 = m.extract_cache_key(html="<p>a</p>", tool="trafilatura", url="http://a")
    k2 = m.extract_cache_key(html="<p>b</p>", tool="trafilatura", url="http://a")
    k3 = m.extract_cache_key(html="<p>a</p>", tool="markitdown", url="http://a")
    assert k1 != k2 and k1 != k3
    j1 = m.judge_cache_key_full(
        query="q",
        query_time="t1",
        gold="g",
        alt_ans=[],
        answer="a",
        model="m",
    )
    j2 = m.judge_cache_key_full(
        query="q",
        query_time="t2",
        gold="g",
        alt_ans=[],
        answer="a",
        model="m",
    )
    assert j1 != j2


def test_page_stats_report_fields():
    """14: empty/error/timeout counts; words with and without failed pages."""
    pages = [
        {"ok": True, "empty": False, "error": None, "timeout": False, "words": 100},
        {"ok": False, "empty": True, "error": "boom", "timeout": False, "words": 0},
        {"ok": False, "empty": True, "error": "page_timeout:1", "timeout": True, "words": 0},
        {"ok": True, "empty": True, "error": None, "timeout": False, "words": 0},
    ]
    ps = m.page_stats(pages)
    assert ps["n_pages_empty"] == 1
    assert ps["n_pages_error"] == 1
    assert ps["n_pages_timeout"] == 1
    assert ps["mean_words_per_page_including_failed"] == 25.0
    assert ps["mean_words_per_page_excluding_failed"] == 50.0  # only the ok non-error page w/ 100? 
    # ok_pages = ok and not timeout and not error → page0 (100) and page3 (0 empty but ok)
    assert ps["mean_words_per_page_excluding_failed"] == 50.0


def test_trafilatura_receives_url(monkeypatch):
    """15: trafilatura gets url like ChromeRAG; report notes the input difference."""
    seen = {}

    def fake_traf(html, url=None):
        seen["url"] = url
        return "text"

    monkeypatch.setitem(m.BASELINES, "trafilatura", fake_traf)
    m.extract_with_tool("<p>x</p>", "trafilatura", url="https://example.com/p")
    assert seen["url"] == "https://example.com/p"
    note_tools = {t: m.extractor_config_for_tool(t) for t in ("trafilatura", "markitdown")}
    assert note_tools["trafilatura"]["url_passed"] is True
    assert note_tools["markitdown"]["url_passed"] is False


def test_cli_split_rejected(synthetic_data: Path, tmp_path: Path):
    with pytest.raises(ValueError, match="only split==0"):
        m.main(
            [
                "--data",
                str(synthetic_data),
                "--cache-dir",
                str(tmp_path / "c"),
                "--out",
                str(tmp_path / "o.json"),
                "--split",
                "1",
                "--dry-run",
            ]
        )


def test_empty_extract_contributes_no_chunks(tmp_path: Path):
    result = m.retrieve_for_tool("paris", ["", "   ", ""], top_k=5)
    assert result["chunks"] == []
    assert result["n_chunks_indexed"] == 0


def test_httpx_timeout_retries(monkeypatch):
    """4b: httpx timeout/connect errors are retried with backoff."""
    client = m.OpenAIClient.__new__(m.OpenAIClient)
    client.max_usd = 100.0
    client.price_in = 0.2
    client.price_out = 0.75
    client.spend_usd = 0.0
    client.spend_this_run = 0.0
    client.tokens_in = 0
    client.tokens_out = 0
    client.calls = 0
    client._reserved = 0.0
    client._lock = threading.Lock()
    client.temperature_dropped_generate = False
    client.temperature_dropped_judge = False

    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        text = json.dumps(
            {
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            }
        )

        def json(self):
            return json.loads(self.text)

    class FakeHttpx:
        def post(self, path, json=None):  # noqa: A002
            calls["n"] += 1
            if calls["n"] < 3:
                raise m.httpx.ConnectError("boom")
            return FakeResp()

    client._client = FakeHttpx()
    sleeps: list[float] = []
    monkeypatch.setattr(m.time, "sleep", lambda s: sleeps.append(s))
    data = client._post("/chat/completions", {"model": "x"})
    assert data["choices"][0]["message"]["content"] == "ok"
    assert calls["n"] == 3
    assert sleeps == [1, 2]


def test_large_extract_result_no_false_timeout():
    """Bug1: parent drains queue before join so >64KB results do not false-timeout."""
    big = "word " * 20_000  # ~100KB
    result = m.run_extract_job_with_timeout(
        {"tool": "trafilatura", "html": "<p>x</p>", "url": None, "_force_text": big},
        page_timeout=30.0,
    )
    assert result["timeout"] is False
    assert result["ok"] is True
    assert len(result["text"]) > 64_000


@pytest.mark.baselines
def test_extract_pool_reuses_worker_reports_seconds(tmp_path: Path):
    """Bug2: long-lived workers; seconds_per_page recorded."""
    questions = [
        _rec(
            iid="q1",
            query="Q",
            answer="A",
            pages=[
                ("https://example.com/a", HTML_A),
                ("https://example.com/b", HTML_B),
            ],
        )
    ]
    out = m.run_extract(
        questions,
        tools=("trafilatura",),
        cache_dir=tmp_path / "cache",
        workers=1,
        page_timeout=30.0,
    )
    pages = out["q1"]["trafilatura"]
    assert len(pages) == 2
    assert all(pages[i]["ok"] for i in range(2))
    assert all(isinstance(pages[i].get("seconds"), float) for i in range(2))


def test_rule_label_cache_hashes_answer_and_finish_reason(tmp_path: Path):
    """Bug3: rule cache at judge/rule/<qid>/<tool>.json invalidates on answer/finish_reason."""
    cache = tmp_path / "cache"
    questions = [_rec(iid="q1", query="Who?", answer="X")]
    gens1 = {"q1": {"trafilatura": {"answer": "I don't know", "finish_reason": "stop"}}}
    j1, _ = m.run_judge(
        questions, gens1, tools=("trafilatura",), cache_dir=cache, client=FakeClient(),
        model="fake", seed=0, workers=1,
    )
    assert j1["q1"]["trafilatura"]["reason"] == "idk_rule"
    rule_path = cache / "judge" / "rule" / "q1" / "trafilatura.json"
    assert rule_path.exists()
    assert "input_hash" in json.loads(rule_path.read_text())

    gens2 = {"q1": {"trafilatura": {"answer": "", "finish_reason": "length"}}}
    j2, info = m.run_judge(
        questions, gens2, tools=("trafilatura",), cache_dir=cache, client=FakeClient(),
        model="fake", seed=0, workers=1,
    )
    assert j2["q1"]["trafilatura"]["reason"] == "empty_answer_length"
    assert info["empty_answer_length"] == 1


def test_worker_infra_errors_not_cached(tmp_path: Path):
    """Bug4: worker_exitcode / worker_queue / spawn_OSError are infrastructure (uncached)."""
    for err in (
        "worker_exitcode:1",
        "worker_queue: Empty: empty",
        "spawn_OSError: too many processes",
    ):
        assert m.is_infrastructure_failure({"error": err})

    cache = tmp_path / "cache"
    questions = [
        _rec(iid="q1", query="Q", answer="A", pages=[("https://example.com", HTML_A)])
    ]

    def boom(_payload):
        return {
            "ok": False,
            "text": "",
            "empty": True,
            "error": "worker_exitcode:9",
            "timeout": False,
            "words": 0,
            "seconds": 0.0,
        }

    import unittest.mock as um

    with um.patch.object(m.ExtractWorkerPool, "run", side_effect=boom):
        out = m.run_extract(
            questions, tools=("trafilatura",), cache_dir=cache, page_timeout=1.0
        )
    assert list((cache / "extract").rglob("*.json")) == []
    assert out["q1"]["trafilatura"][0]["error"] == "missing_cache"


@pytest.mark.baselines
def test_save_persisted_spend_runs_on_corrupt_cache(synthetic_data: Path, tmp_path: Path):
    """Bug5: try/finally persists spend even when a stage raises non-budget errors."""
    import unittest.mock as um

    cache = tmp_path / "cache_spend"
    args = _args(
        synthetic_data, tmp_path, n=1, cache_dir=cache, out=tmp_path / "out_spend.json"
    )
    m.run(args, client_factory=lambda: FakeClient(max_usd=100.0))
    prior = m.load_persisted_spend(cache)
    assert prior > 0

    held: dict = {}

    def factory():
        c = FakeClient(starting_spend_usd=prior)
        held["c"] = c
        return c

    def boom_generate(*_a, **_kw):
        held["c"].spend_usd = round(prior + 0.02, 6)
        held["c"].spend_this_run = 0.02
        raise RuntimeError("corrupt cache boom")

    args2 = _args(
        synthetic_data,
        tmp_path,
        n=1,
        cache_dir=cache,
        out=tmp_path / "out_spend2.json",
    )
    with um.patch.object(m, "run_generate", side_effect=boom_generate):
        with pytest.raises(RuntimeError, match="corrupt cache boom"):
            m.run(args2, client_factory=factory)
    assert m.load_persisted_spend(cache) == pytest.approx(prior + 0.02)


@pytest.mark.baselines
def test_budget_stop_loads_rule_labels(synthetic_data: Path, tmp_path: Path):
    """Bug6: budget-stop reload includes judge/rule labels so IDK stays in intersection."""
    import unittest.mock as um

    cache = tmp_path / "cache_budget_rule"
    args = _args(
        synthetic_data,
        tmp_path,
        n=1,
        cache_dir=cache,
        out=tmp_path / "budget_rule.json",
        page_timeout=0.0,
        workers=1,
    )
    # Warm extract/retrieve caches.
    m.run(args, client_factory=lambda: FakeClient(max_usd=100.0))
    sampled = m.sample_questions(
        m.filter_web_static(m.load_crag_records(synthetic_data, split=0))[0],
        1,
        0,
    )
    qid = m.question_id(sampled[0])
    # Overwrite generations to IDK for every tool and seed matching rule labels.
    for tool in m.TOOLS:
        chunks = (m.run_retrieve(sampled, m.run_extract(
            sampled, cache_dir=cache, page_timeout=0.0
        ), cache_dir=cache)[qid][tool].get("chunks") or [])
        qt = sampled[0].get("query_time")
        system, _ = m.generate_prompt(sampled[0]["query"], chunks, query_time=qt)
        gkey = m.generate_cache_key(
            query=sampled[0]["query"],
            chunks=chunks,
            tool=tool,
            model=args.model,
            prompt_system=system,
            max_completion_tokens=args.max_completion_tokens_generate,
            temperature=0.0,
            query_time=qt,
        )
        m.write_json_cache(
            m.cache_path(cache, "generate", gkey[:2], f"{gkey}.json"),
            {
                "answer": "I don't know",
                "finish_reason": "stop",
                "cost_usd": 0.0,
                "usage": {"finish_reason": "stop"},
            },
        )
        ih = m.rule_label_input_hash("I don't know", "stop")
        m.write_json_cache(
            m.cache_path(cache, "judge", "rule", qid, f"{tool}.json"),
            {
                "label": "missing",
                "reason": "idk_rule",
                "cost_usd": 0.0,
                "input_hash": ih,
            },
        )
    # Drop LLM judge cache files so only rule labels remain.
    for p in (cache / "judge").rglob("*.json"):
        if "rule" not in p.parts:
            p.unlink()

    def gen_then_budget(questions, retrievals, **kw):
        out = {m.question_id(r): {} for r in questions}
        for rec in questions:
            qid_ = m.question_id(rec)
            for tool in m.TOOLS:
                chunks = retrievals[qid_][tool].get("chunks") or []
                qt = rec.get("query_time")
                system, _ = m.generate_prompt(rec["query"], chunks, query_time=qt)
                gkey = m.generate_cache_key(
                    query=rec["query"],
                    chunks=chunks,
                    tool=tool,
                    model=kw["model"],
                    prompt_system=system,
                    max_completion_tokens=kw.get(
                        "max_completion_tokens", m.DEFAULT_MAX_COMPLETION_GENERATE
                    ),
                    temperature=0.0,
                    query_time=qt,
                )
                hit = m.read_json_cache(
                    m.cache_path(kw["cache_dir"], "generate", gkey[:2], f"{gkey}.json")
                )
                if hit:
                    out[qid_][tool] = hit
        raise m.BudgetExceeded("generate stage stopped on budget")

    with um.patch.object(m, "run_generate", side_effect=gen_then_budget):
        report = m.run(args, client_factory=lambda: FakeClient(max_usd=100.0))
    assert report["partial"] is True
    assert qid in report["scored_question_ids"]
    assert report["n_scored"] == 1
    assert report["tools"]["trafilatura"]["missing"] == 1.0


def test_generate_cache_key_includes_max_tokens_and_temperature():
    """Bug7: generate cache key hashes max_completion_tokens and temperature."""
    base = dict(query="q", chunks=["c"], model="m")
    k1 = m.generate_cache_key(**base, max_completion_tokens=1024, temperature=0.0)
    k2 = m.generate_cache_key(**base, max_completion_tokens=4096, temperature=0.0)
    k3 = m.generate_cache_key(**base, max_completion_tokens=1024, temperature=0.2)
    assert k1 != k2
    assert k1 != k3
    k_traf = m.generate_cache_key(**base, tool="trafilatura")
    k_mark = m.generate_cache_key(**base, tool="markitdown")
    assert k_traf == k_mark


def test_generate_dedup_same_context_across_tools(tmp_path: Path):
    client = FakeClient()
    q = "What is the capital of France?"
    questions = [_rec(iid="q1", query=q, answer="Paris")]
    ctx = ["The capital of France is Paris."]
    retrievals = {
        "q1": {
            "trafilatura": {"chunks": ctx},
            "markitdown": {"chunks": ctx},
        }
    }
    gens, info = m.run_generate(
        questions,
        retrievals,
        tools=("trafilatura", "markitdown"),
        cache_dir=tmp_path / "cache",
        client=client,
        model="fake",
        workers=1,
    )
    assert client.calls == 1
    assert gens["q1"]["trafilatura"]["answer"] == gens["q1"]["markitdown"]["answer"]
    assert info["generate_calls"] == 1
    assert info["generate_calls_saved"] == 1


def test_strip_yaml_not_horizontal_rule():
    hr = "---\n\n# Article\n\nThe body stays."
    assert "Article" in m.strip_chromerag_yaml_front_matter(hr)
    yaml = "---\ntitle: Page\n---\n\n# Article\n\nThe body stays."
    stripped = m.strip_chromerag_yaml_front_matter(yaml)
    assert stripped.startswith("# Article")
    assert "---" not in stripped.split("\n", 1)[0]


def test_chunk_harness_bm25_tokens_and_newlines():
    table = "| col a | col b |\n| --- | --- |\n| x | y |"
    assert m.bm25_token_count(table) == m.bm25_token_count("col a col b x y")
    md = table + "\n\n" + ("word " * 400)
    chunks = m.chunk_markdown_harness(md, max_tokens=50)
    assert chunks
    assert "\n" in chunks[0]
    assert "|" in chunks[0]


def test_cap_context_keeps_newlines():
    chunks = ["line one\nline two", "chunk two"]
    ctx = m._cap_context(chunks, token_cap=10_000)
    assert "\n" in ctx
    assert "line one" in ctx


def test_mean_words_indexed_aggregates_pages_not_questions():
    questions = [
        _rec(iid="q1", query="Q1", answer="A", pages=[("https://a", HTML_A)]),
        _rec(iid="q2", query="Q2", answer="B", pages=[("https://b", HTML_B)]),
    ]
    long_text = "alpha " * 300
    extracts = {
        "q1": {
            "trafilatura": [
                {"ok": True, "words": 300, "empty": False, "error": None, "timeout": False},
            ],
        },
        "q2": {
            "trafilatura": [
                {"ok": True, "words": 10, "empty": False, "error": None, "timeout": False},
            ],
        },
    }
    extracts["q1"]["trafilatura"][0]["text"] = long_text
    extracts["q2"]["trafilatura"][0]["text"] = "beta beta"
    retrievals = {
        "q1": {"trafilatura": {"chunks": ["x"]}},
        "q2": {"trafilatura": {"chunks": ["y"]}},
    }
    judgements = {
        "q1": {"trafilatura": {"label": "accurate"}},
        "q2": {"trafilatura": {"label": "accurate"}},
    }
    report = m.summarize(
        questions,
        extracts,
        retrievals,
        judgements,
        tools=("trafilatura",),
        seed=0,
        model="fake",
        spend_usd=0.0,
        exclusion_counts={},
        chosen_ids=["q1", "q2"],
    )
    t1 = m.page_indexed_token_count(long_text)
    t2 = m.page_indexed_token_count("beta beta")
    expected = round((t1 + t2) / 2, 2)
    assert report["tools"]["trafilatura"]["mean_words_indexed_per_page"] == expected


def test_mean_words_per_page_aggregates_over_pages_not_questions():
    """Uneven page counts must not be mean-of-per-question-means."""
    questions = [
        _rec(
            iid="q1",
            query="Q1",
            answer="A",
            pages=[("https://a", HTML_A), ("https://a2", HTML_A), ("https://a3", HTML_A)],
        ),
        _rec(iid="q2", query="Q2", answer="B", pages=[("https://b", HTML_B)]),
    ]
    extracts = {
        "q1": {
            "trafilatura": [
                {"ok": True, "words": 10, "empty": False, "error": None, "timeout": False, "text": "a"},
                {"ok": True, "words": 10, "empty": False, "error": None, "timeout": False, "text": "b"},
                {"ok": True, "words": 10, "empty": False, "error": None, "timeout": False, "text": "c"},
            ],
        },
        "q2": {
            "trafilatura": [
                {"ok": True, "words": 100, "empty": False, "error": None, "timeout": False, "text": "d"},
            ],
        },
    }
    retrievals = {
        "q1": {"trafilatura": {"chunks": ["x"]}},
        "q2": {"trafilatura": {"chunks": ["y"]}},
    }
    judgements = {
        "q1": {"trafilatura": {"label": "accurate"}},
        "q2": {"trafilatura": {"label": "accurate"}},
    }
    report = m.summarize(
        questions,
        extracts,
        retrievals,
        judgements,
        tools=("trafilatura",),
        seed=0,
        model="fake",
        spend_usd=0.0,
        exclusion_counts={},
        chosen_ids=["q1", "q2"],
    )
    # Page-weighted: (10+10+10+100)/4 = 32.5; mean-of-means would be (10+100)/2 = 55.
    assert report["tools"]["trafilatura"]["mean_words_per_page_including_failed"] == 32.5
    assert report["tools"]["trafilatura"]["mean_words_per_page_excluding_failed"] == 32.5


def test_rule_label_cache_resume_counts(tmp_path: Path):
    cache = tmp_path / "cache"
    questions = [_rec(iid="q1", query="Who?", answer="X")]
    gens = {
        "q1": {
            "trafilatura": {"answer": "I don't know", "finish_reason": "stop"},
            "markitdown": {"answer": "", "finish_reason": "length"},
        }
    }
    c1 = FakeClient()
    j1, info1 = m.run_judge(
        questions, gens, tools=("trafilatura", "markitdown"), cache_dir=cache,
        client=c1, model="fake", seed=0, workers=1,
    )
    assert info1["idk_rule_labels"] == 1
    assert info1["empty_answer_length"] == 1
    assert c1.calls == 0

    c2 = FakeClient()
    j2, info2 = m.run_judge(
        questions, gens, tools=("trafilatura", "markitdown"), cache_dir=cache,
        client=c2, model="fake", seed=0, workers=1,
    )
    assert j2 == j1
    assert info2["idk_rule_labels"] == info1["idk_rule_labels"]
    assert info2["empty_answer_length"] == info1["empty_answer_length"]
    assert c2.calls == 0


def test_markitdown_missing_is_extract_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "markitdown" or name.startswith("markitdown."):
            raise ImportError("simulated missing markitdown")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = m._extract_job({"tool": "markitdown", "html": "<p>x</p>", "url": None})
    assert result["ok"] is False
    assert "markitdown not installed" in (result.get("error") or "")


def test_horizontal_rule_not_stripped_in_retrieve():
    text = "---\n\n# Headline\n\nImportant fact about Paris."
    chunks = m.chunk_markdown_harness(text)
    joined = "\n\n".join(chunks)
    assert "Important fact" in joined
    assert "# Headline" in joined


def test_run_retrieval_eval_chunk_keeps_hr_and_tokenize_budget():
    from poc.run_retrieval_eval import chunk_markdown, strip_yaml_front_matter, tokenize

    hr = "---\n\n# Headline\n\nImportant fact about Paris."
    assert "Important fact" in strip_yaml_front_matter(hr)
    chunks = chunk_markdown(hr)
    joined = "\n\n".join(chunks)
    assert "Important fact" in joined
    assert "\n" in chunks[0] or "# Headline" in joined

    yaml = "---\ntitle: Page\n---\n\n# Body\n\nKept."
    assert strip_yaml_front_matter(yaml).startswith("# Body")
    assert "title:" not in strip_yaml_front_matter(yaml)

    table = "| col a | col b |\n| --- | --- |\n| x | y |"
    assert len(tokenize(table)) == len(tokenize("col a col b x y"))
    md = table + "\n\n" + ("word " * 400)
    out = chunk_markdown(md, words=50)
    assert out
    assert "|" in out[0]
    assert "\n" in out[0]


def test_failure_stats_use_scored_plus_all_sampled_block():
    """Bug8: per-tool failure/word stats use scored_questions; all_sampled is separate."""
    questions = [
        _rec(iid="q1", query="Q1", answer="A", pages=[("https://a", HTML_A)]),
        _rec(iid="q2", query="Q2", answer="B", pages=[("https://b", HTML_B)]),
    ]
    judgements = {
        "q1": {
            "trafilatura": {"label": "accurate"},
            "markitdown": {"label": "incorrect"},
        },
        "q2": {
            "trafilatura": {"label": "accurate"},
            # markitdown missing → q2 dropped from scored
        },
    }
    extracts = {
        "q1": {
            "trafilatura": [
                {"ok": True, "words": 10, "empty": False, "error": None, "timeout": False}
            ],
            "markitdown": [
                {
                    "ok": False,
                    "words": 0,
                    "empty": True,
                    "error": "boom",
                    "timeout": False,
                }
            ],
        },
        "q2": {
            "trafilatura": [
                {
                    "ok": False,
                    "words": 0,
                    "empty": True,
                    "error": "boom",
                    "timeout": False,
                }
            ],
            "markitdown": [
                {"ok": True, "words": 5, "empty": False, "error": None, "timeout": False}
            ],
        },
    }
    retrievals = {
        "q1": {"trafilatura": {"chunks": ["A"]}, "markitdown": {"chunks": ["A"]}},
        "q2": {"trafilatura": {"chunks": []}, "markitdown": {"chunks": ["B"]}},
    }
    tools = ("trafilatura", "markitdown")
    report = m.summarize(
        questions,
        extracts,
        retrievals,
        judgements,
        tools=tools,
        seed=0,
        model="fake",
        spend_usd=0.0,
        exclusion_counts={},
        chosen_ids=["q1", "q2"],
        partial=True,
    )
    assert report["n_scored"] == 1
    # Scored population only (q1): trafilatura has 0 errors; markitdown has 1.
    assert report["tools"]["trafilatura"]["n_pages_error"] == 0
    assert report["tools"]["markitdown"]["n_pages_error"] == 1
    # all_sampled includes q2's trafilatura error.
    assert report["all_sampled"]["tools"]["trafilatura"]["n_pages_error"] == 1
    assert report["all_sampled"]["n_questions"] == 2


def test_markitdown_missing_returns_clear_error_text(monkeypatch):
    """Bug9: missing markitdown yields clear text so callers without try/except continue."""
    import builtins

    from poc import baselines as b

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "markitdown" or name.startswith("markitdown."):
            raise ImportError("simulated missing markitdown")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    text = b.baseline_markitdown("<html><body><p>hi</p></body></html>")
    assert text == "[markitdown not installed]"


def test_page_timeout_not_cached_but_counted_on_resume(tmp_path: Path):
    """Timeouts are not cached (resume retries) but still counted in this run's extract."""
    cache = tmp_path / "cache"
    questions = [
        _rec(
            iid="q1",
            query="Q",
            answer="A",
            pages=[("https://example.com", HTML_A)],
        )
    ]
    timeout_row = {
        "ok": False,
        "text": "",
        "empty": True,
        "error": "page_timeout:1.0",
        "timeout": True,
        "words": 0,
        "seconds": 1.0,
    }
    ok_row = {
        "ok": True,
        "text": "Paris",
        "empty": False,
        "error": None,
        "timeout": False,
        "words": 1,
        "seconds": 0.01,
    }
    import unittest.mock as um

    with um.patch.object(m.ExtractWorkerPool, "run", return_value=timeout_row):
        out1 = m.run_extract(
            questions, tools=("trafilatura",), cache_dir=cache, page_timeout=1.0
        )
    assert list((cache / "extract").rglob("*.json")) == []
    assert out1["q1"]["trafilatura"][0]["timeout"] is True
    assert m.page_stats(out1["q1"]["trafilatura"])["n_pages_timeout"] == 1

    with um.patch.object(m.ExtractWorkerPool, "run", return_value=ok_row) as run_mock:
        out2 = m.run_extract(
            questions, tools=("trafilatura",), cache_dir=cache, page_timeout=1.0
        )
    assert run_mock.call_count == 1
    assert out2["q1"]["trafilatura"][0]["timeout"] is False
    assert list((cache / "extract").rglob("*.json"))


def test_generate_errors_counted_partial_and_messages(tmp_path: Path):
    """Generate exceptions are counted, sampled, and mark the report partial."""

    class BoomClient(FakeClient):
        def chat(self, *a, **kw):
            raise RuntimeError("generate boom")

    questions = [
        _rec(iid="q1", query="What is the capital of France?", answer="Paris"),
        _rec(iid="q2", query="Which river flows through Paris?", answer="Seine"),
    ]
    retrievals = {
        "q1": {"trafilatura": {"chunks": ["The capital of France is Paris"]}},
        "q2": {"trafilatura": {"chunks": ["The Seine river flows through Paris"]}},
    }
    gens, info = m.run_generate(
        questions,
        retrievals,
        tools=("trafilatura",),
        cache_dir=tmp_path / "cache",
        client=BoomClient(),
        model="fake",
        workers=1,
    )
    assert gens == {}
    assert info["generate_errors"] == 2
    assert len(info["generate_error_messages"]) == 2
    assert "RuntimeError: generate boom" in info["generate_error_messages"][0]

    report = m.summarize(
        questions,
        {"q1": {"trafilatura": []}, "q2": {"trafilatura": []}},
        retrievals,
        {},
        tools=("trafilatura",),
        seed=0,
        model="fake",
        spend_usd=0.0,
        exclusion_counts={},
        chosen_ids=["q1", "q2"],
        partial=True,
        generate_errors=info["generate_errors"],
        generate_error_messages=info["generate_error_messages"],
    )
    assert report["generate_errors"] == 2
    assert report["generate_error_messages"]
    assert report["partial"] is True


def test_generate_prompt_and_cache_key_include_query_time():
    """query_time is added to the generate prompt and cache key; empty omits the line."""
    chunks = ["ctx"]
    _, user_qt = m.generate_prompt("last year?", chunks, query_time="2023-06-01")
    assert "Query time: 2023-06-01" in user_qt
    assert "Question: last year?" in user_qt
    _, user_empty = m.generate_prompt("last year?", chunks, query_time="")
    assert "Query time:" not in user_empty
    _, user_none = m.generate_prompt("last year?", chunks, query_time=None)
    assert "Query time:" not in user_none
    assert user_empty == user_none

    base = dict(query="q", chunks=chunks, tool="trafilatura", model="m")
    k_qt = m.generate_cache_key(**base, query_time="2023-06-01")
    k_none = m.generate_cache_key(**base, query_time=None)
    k_blank = m.generate_cache_key(**base, query_time="  ")
    assert k_qt != k_none
    assert k_none == k_blank


def test_long_single_line_is_split_into_bounded_chunks():
    from poc.run_retrieval_eval import chunk_markdown, tokenize

    chunks = chunk_markdown(" ".join(f"word{i}" for i in range(1000)), words=200)
    assert len(chunks) >= 5
    assert all(len(tokenize(c)) <= 200 for c in chunks)
    assert sum(len(tokenize(c)) for c in chunks) == 1000


def test_harness_splits_long_line_and_cap_keeps_text():
    import poc.crag_answer_eval as m

    chunks = m.chunk_markdown_harness(" ".join(f"word{i}" for i in range(1300)), max_tokens=200)
    assert len(chunks) >= 7
    assert sum(m.bm25_token_count(c) for c in chunks) == 1300
    assert all(m.bm25_token_count(c) <= 200 for c in chunks)
    assert m.bm25_token_count(m._cap_context(chunks, token_cap=1200)) == 1200
    assert m.bm25_token_count(m._cap_context([" ".join(f"w{i}" for i in range(500))], token_cap=100)) == 100
