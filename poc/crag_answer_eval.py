"""CRAG answer-faithfulness eval: same questions/pages, only the extractor differs.

Stages (each resumable under --cache-dir): extract → retrieve → generate → judge.
Offline tests inject a fake LLM client; live runs need OPENAI_API_KEY and network.

Usage:
  python -m poc.crag_answer_eval --data PATH.jsonl.bz2 --cache-dir /tmp/crag-cache \\
      --out /tmp/crag_answer_eval.json --n 50 --seed 0 --max-usd 5 --dry-run
"""

from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import multiprocessing as mp
import os
import queue
import random
import re
import statistics
import subprocess
import threading
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any, Callable

import httpx

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES
from poc.eval_rubric import ANSWER_RULE_IDS, RULES_BY_LABEL, answer_judge_prompt_v2
from poc.run_retrieval_eval import BM25, CHUNK_WORDS, tokenize

MODEL = "gpt-5.6-luna"
TOOLS = (
    "markitdown",
    "trafilatura",
    "chromerag_precision",
    "chromerag_balanced",
    "chromerag_coverage",
)
CHROMERAG_PRIORITY = {
    "chromerag_precision": ContentPriority.PRECISION,
    "chromerag_balanced": ContentPriority.BALANCED,
    "chromerag_coverage": ContentPriority.COVERAGE,
}
TOP_K = 5
CONTEXT_WORD_CAP = 1200
BOOTSTRAP_ITERS = 2000
SHORT_GOLD_WORDS = 5
DEFAULT_MAX_COMPLETION_GENERATE = 4096
DEFAULT_MAX_COMPLETION_JUDGE = 1024
JUDGE_PARSE_RETRIES = 2
IDK_RE = re.compile(r"^\s*i\s+don'?t\s+know\.?\s*$", re.I)
_YAML_FM_LINE = re.compile(r"^[A-Za-z0-9_.-]+:\s*")
_MARKITDOWN_MISSING = "[markitdown not installed]"
_WS = re.compile(r"\s+")

GENERATE_SYSTEM = (
    "Answer the question using only the provided context. "
    'If the context is insufficient, reply exactly: I don\'t know'
)
JUDGE_SYSTEM = """You judge a RAG system's answer against a gold answer for the CRAG benchmark.
Labels (pick exactly one):
- accurate: the generated answer is correct and faithful to the gold (or an equivalent alt answer)
- missing: the system abstains or fails to provide the answer
- incorrect: the system gives a wrong answer
Reply with JSON only: {"label": "accurate"|"missing"|"incorrect", "reason": "one short sentence"}"""

JUDGE_RUBRIC_V2 = answer_judge_prompt_v2()

ALLOWED_SPLIT = 0
FAST_DYNAMIC = frozenset({"fast-changing", "real-time"})
VALID_LABELS = frozenset({"accurate", "missing", "incorrect"})
INFRA_ERROR_MARKERS = (
    "BrokenProcessPool",
    "BrokenThreadPool",
    "ProcessExpired",
    "CancelledError",
    "InterpreterError",
    "worker_exitcode:",
    "worker_queue:",
    "spawn_OSError:",
)

TRAFILATURA_EXTRACTOR_CONFIG = {
    "include_tables": True,
    "include_comments": False,
    "include_links": False,
    "output_format": "markdown",
    "url_passed": True,
}
MARKITDOWN_EXTRACTOR_CONFIG = {"converter": "MarkItDown", "url_passed": False}


# ---------------------------------------------------------------------------
# Data load / filter / sample (split==0 only, enforced here)
# ---------------------------------------------------------------------------


def enforce_split(split: int, *, locked_run: bool = False) -> None:
    """Split 0 by default. Split 1 is locked: one protocol run, requested with --locked-split-1."""
    if split == ALLOWED_SPLIT or (split == 1 and locked_run):
        return
    raise ValueError(f"only split=={ALLOWED_SPLIT} is supported, got --split={split}")


def load_crag_records(
    path: Path,
    *,
    split: int = ALLOWED_SPLIT,
    limit: int | None = None,
    locked_run: bool = False,
) -> list[dict]:
    """Load CRAG jsonl.bz2; keep only records of the requested split."""
    enforce_split(split, locked_run=locked_run)
    rows: list[dict] = []
    opener = bz2.open if str(path).endswith(".bz2") else open
    with opener(path, "rt", encoding="utf-8") as fh:  # type: ignore[arg-type]
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if int(rec.get("split", -1)) != split:
                continue
            rows.append(rec)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def filter_web_static(records: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Metadata-only cohort filter (before scoring)."""
    counts = Counter()
    kept: list[dict] = []
    for rec in records:
        counts["split0_loaded"] += 1
        if rec.get("popularity") not in ("", None):
            counts["excluded_nonempty_popularity"] += 1
            continue
        if rec.get("question_type") == "false_premise":
            counts["excluded_false_premise"] += 1
            continue
        sod = str(rec.get("static_or_dynamic") or "")
        if sod in FAST_DYNAMIC:
            counts["excluded_fast_or_realtime"] += 1
            continue
        if str(rec.get("answer") or "").strip().lower() == "invalid question":
            counts["excluded_invalid_question"] += 1
            continue
        counts["kept"] += 1
        kept.append(rec)
    return kept, dict(counts)


def sample_questions(records: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    pool = list(records)
    rng.shuffle(pool)
    return pool[: min(n, len(pool))]


def question_id(rec: dict) -> str:
    return str(rec.get("interaction_id") or hashlib.sha1(rec["query"].encode()).hexdigest()[:16])


# ---------------------------------------------------------------------------
# Versions / import checks / stable hashes
# ---------------------------------------------------------------------------


def _pkg_ver(name: str) -> str:
    try:
        return pkg_version(name)
    except PackageNotFoundError:
        return "unknown"


def tool_package_version(tool: str) -> str:
    if tool in CHROMERAG_PRIORITY:
        return _pkg_ver("chromerag")
    if tool == "markitdown":
        return _pkg_ver("markitdown")
    if tool == "trafilatura":
        return _pkg_ver("trafilatura")
    return "unknown"


def extractor_config_for_tool(tool: str) -> dict:
    if tool in CHROMERAG_PRIORITY:
        cfg = PipelineConfig.from_priority(CHROMERAG_PRIORITY[tool])
        return {
            "content_priority": str(cfg.content_priority.value),
            "dvdf_threshold": cfg.dvdf_threshold,
            "enable_dvdf": cfg.enable_dvdf,
            "enable_schema": cfg.enable_schema,
            "enable_stce": cfg.enable_stce,
            "enable_tables": cfg.enable_tables,
            "strictness": str(cfg.strictness.value),
            "url_passed": True,
        }
    if tool == "trafilatura":
        return dict(TRAFILATURA_EXTRACTOR_CONFIG)
    if tool == "markitdown":
        return dict(MARKITDOWN_EXTRACTOR_CONFIG)
    return {}


def verify_tools_importable(tools: tuple[str, ...] = TOOLS) -> None:
    """Fail fast before any paid/extract work if a requested tool cannot import."""
    errors: list[str] = []
    for tool in tools:
        try:
            if tool in CHROMERAG_PRIORITY:
                PipelineConfig.from_priority(CHROMERAG_PRIORITY[tool])
                ChromeRAG  # noqa: B018 — import already done; touch symbol
            elif tool == "markitdown":
                from markitdown import MarkItDown  # noqa: F401
            elif tool == "trafilatura":
                import trafilatura  # noqa: F401
            elif tool in BASELINES:
                # Exercise the callable path for other baselines if requested.
                BASELINES[tool]
            else:
                raise KeyError(f"unknown tool {tool}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{tool}: {type(exc).__name__}: {exc}")
    if errors:
        raise RuntimeError("requested tools not importable:\n" + "\n".join(errors))


def stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def html_hash(html: str) -> str:
    return hashlib.sha1((html or "").encode("utf-8")).hexdigest()


def extract_cache_key(
    *,
    html: str,
    tool: str,
    url: str | None,
    chunk_words: int = CHUNK_WORDS,
) -> str:
    return stable_hash(
        {
            "html": html_hash(html),
            "tool": tool,
            "package_version": tool_package_version(tool),
            "extractor_config": extractor_config_for_tool(tool),
            "url": url or "",
            # chunk settings live on retrieve keys too; include for extract identity
            "chunk_words": chunk_words,
        }
    )


def retrieve_cache_key(
    *,
    query: str,
    page_text_hashes: list[str],
    tool: str,
    top_k: int = TOP_K,
    chunk_words: int = CHUNK_WORDS,
) -> str:
    return stable_hash(
        {
            "query": query,
            "pages": page_text_hashes,
            "tool": tool,
            "top_k": top_k,
            "chunk_words": chunk_words,
        }
    )


def _normalized_query_time(query_time: Any) -> str | None:
    if query_time is None:
        return None
    text = str(query_time).strip()
    return text or None


def generate_cache_key(
    *,
    query: str,
    chunks: list[str],
    model: str,
    prompt_system: str = GENERATE_SYSTEM,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_GENERATE,
    temperature: float = 0.0,
    query_time: Any = None,
    tool: str | None = None,
) -> str:
    _ = tool  # legacy callers; generation is deduped across tools
    return stable_hash(
        {
            "query": query,
            "query_time": _normalized_query_time(query_time),
            "chunks": [html_hash(c) for c in chunks],
            "model": model,
            "prompt": prompt_system,
            "top_k": TOP_K,
            "context_token_cap": CONTEXT_WORD_CAP,
            "chunk_tokens": CHUNK_WORDS,
            "max_completion_tokens": max_completion_tokens,
            "temperature": temperature,
        }
    )


def rule_label_input_hash(answer: str, finish_reason: Any) -> str:
    return stable_hash(
        {
            "answer": (answer or "").strip(),
            "finish_reason": finish_reason,
        }
    )


def judge_cache_key_full(
    *,
    query: str,
    query_time: Any,
    gold: str,
    alt_ans: list,
    answer: str,
    model: str,
    prompt_system: str = JUDGE_SYSTEM,
) -> str:
    return stable_hash(
        {
            "query": query,
            "query_time": query_time,
            "gold": gold,
            "alt_ans": alt_ans or [],
            "answer": (answer or "").strip(),
            "prompt": prompt_system,
            "model": model,
        }
    )


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def strip_chromerag_yaml_front_matter(text: str) -> str:
    """Remove ChromeRAG YAML front matter only (key: value lines, no blanks, closed by ---)."""
    body = text or ""
    if not body.startswith("---\n"):
        return body
    lines = body.split("\n")
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            rest = "\n".join(lines[i + 1 :])
            return rest.lstrip("\n")
        if line == "" or not _YAML_FM_LINE.match(line):
            return body
        i += 1
    return body


def extract_with_tool(html: str, tool: str, url: str | None = None) -> str:
    if tool in CHROMERAG_PRIORITY:
        result = ChromeRAG(config=PipelineConfig.from_priority(CHROMERAG_PRIORITY[tool])).extract(
            html, url=url
        )
        return strip_chromerag_yaml_front_matter(result.markdown or "")
    if tool == "trafilatura":
        return BASELINES[tool](html, url=url) or ""
    if tool not in BASELINES:
        raise KeyError(f"unknown tool {tool}")
    return BASELINES[tool](html) or ""


def _extract_job(payload: dict) -> dict:
    """Picklable worker: extract one page with one tool."""
    # Test hook: return a forced payload without importing extractors (spawn-safe).
    if "_force_text" in payload:
        text = str(payload["_force_text"])
        return {
            "ok": True,
            "text": text,
            "empty": not bool(text.strip()),
            "error": None,
            "timeout": False,
            "words": len(text.split()),
        }
    tool = payload["tool"]
    html = payload["html"]
    url = payload.get("url")
    try:
        text = extract_with_tool(html, tool, url=url)
        if (text or "").strip() == _MARKITDOWN_MISSING:
            return {
                "ok": False,
                "text": text,
                "empty": True,
                "error": "extraction_error: markitdown not installed",
                "timeout": False,
                "words": 0,
            }
        return {
            "ok": True,
            "text": text,
            "empty": not bool(text.strip()),
            "error": None,
            "timeout": False,
            "words": len(text.split()),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "text": "",
            "empty": True,
            "error": f"{type(exc).__name__}: {exc}",
            "timeout": False,
            "trace": traceback.format_exc()[-400:],
            "words": 0,
        }


def _extract_job_queue(payload: dict, q: Any) -> None:
    # Optional test hook: sleep before work so timeout kill can be exercised.
    delay = payload.get("_sleep")
    if delay:
        time.sleep(float(delay))
    q.put(_extract_job(payload))


def _extract_worker_loop(job_q: Any, result_q: Any) -> None:
    """Long-lived worker: import once, process jobs until None sentinel."""
    while True:
        item = job_q.get()
        if item is None:
            break
        job_id, payload = item
        delay = payload.get("_sleep")
        if delay:
            time.sleep(float(delay))
        result_q.put((job_id, _extract_job(payload)))


def _failure_result(error: str, *, timeout: bool = False, seconds: float = 0.0) -> dict:
    return {
        "ok": False,
        "text": "",
        "empty": True,
        "error": error,
        "timeout": timeout,
        "words": 0,
        "seconds": round(seconds, 4),
    }


def _kill_process(proc: mp.Process) -> None:
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            proc.join(5)


class ExtractWorkerPool:
    """Reuse spawn workers across pages; replace a worker only when killed at deadline."""

    def __init__(self, n_workers: int, page_timeout: float) -> None:
        self.page_timeout = page_timeout
        self.ctx = mp.get_context("spawn")
        self._free: queue.Queue = queue.Queue()
        self._job_counter = 0
        self._counter_lock = threading.Lock()
        self._spawn_error: str | None = None
        for _ in range(max(1, n_workers)):
            worker = self._spawn_worker()
            if worker is None:
                break
            self._free.put(worker)

    def _spawn_worker(self) -> dict[str, Any] | None:
        job_q = self.ctx.Queue()
        result_q = self.ctx.Queue()
        proc = self.ctx.Process(
            target=_extract_worker_loop, args=(job_q, result_q), daemon=True
        )
        try:
            proc.start()
        except OSError as exc:
            self._spawn_error = f"spawn_OSError: {exc}"
            return None
        return {"proc": proc, "job_q": job_q, "result_q": result_q}

    def _replace_worker(self, worker: dict[str, Any]) -> None:
        proc = worker["proc"]
        _kill_process(proc)
        # Drain stale queue objects; replace with a fresh process pair.
        fresh = self._spawn_worker()
        if fresh is None:
            worker["proc"] = proc
            worker["dead"] = True
            return
        worker.clear()
        worker.update(fresh)

    def _next_job_id(self) -> int:
        with self._counter_lock:
            self._job_counter += 1
            return self._job_counter

    def run(self, payload: dict) -> dict:
        if self.page_timeout <= 0:
            t0 = time.perf_counter()
            result = _extract_job(payload)
            result["seconds"] = round(time.perf_counter() - t0, 4)
            return result
        if self._spawn_error and self._free.empty():
            return _failure_result(self._spawn_error)

        worker = self._free.get()
        try:
            if worker.get("dead") or not worker["proc"].is_alive():
                self._replace_worker(worker)
                if worker.get("dead") or self._spawn_error:
                    return _failure_result(self._spawn_error or "spawn_OSError: worker dead")
            job_id = self._next_job_id()
            t0 = time.perf_counter()
            try:
                worker["job_q"].put((job_id, payload))
            except Exception as exc:  # noqa: BLE001
                self._replace_worker(worker)
                return _failure_result(
                    f"worker_queue: {type(exc).__name__}: {exc}",
                    seconds=time.perf_counter() - t0,
                )
            try:
                # Read result before joining/waiting on process exit so large
                # payloads cannot fill the pipe and false-timeout.
                rid, result = worker["result_q"].get(timeout=self.page_timeout)
            except queue.Empty:
                self._replace_worker(worker)
                return _failure_result(
                    f"page_timeout:{self.page_timeout}",
                    timeout=True,
                    seconds=time.perf_counter() - t0,
                )
            except Exception as exc:  # noqa: BLE001
                self._replace_worker(worker)
                return _failure_result(
                    f"worker_queue: {type(exc).__name__}: {exc}",
                    seconds=time.perf_counter() - t0,
                )
            elapsed = round(time.perf_counter() - t0, 4)
            if rid != job_id:
                self._replace_worker(worker)
                return _failure_result(
                    f"worker_queue: mismatched job id {rid}!={job_id}",
                    seconds=elapsed,
                )
            if not worker["proc"].is_alive():
                # Result already drained; replace dead worker for the next job.
                self._replace_worker(worker)
            result = dict(result)
            result["seconds"] = elapsed
            return result
        finally:
            self._free.put(worker)

    def close(self) -> None:
        while True:
            try:
                worker = self._free.get_nowait()
            except queue.Empty:
                break
            try:
                worker["job_q"].put(None)
            except Exception:  # noqa: BLE001
                pass
            proc = worker.get("proc")
            if proc is not None:
                proc.join(2)
                _kill_process(proc)


def run_extract_job_with_timeout(payload: dict, page_timeout: float) -> dict:
    """Run extraction with a real per-page timeout (one-shot helper for tests).

    page_timeout <= 0 runs in-process (no kill); used by offline tests for speed.
    Parent reads the queue before join so large results do not false-timeout.
    """
    if page_timeout <= 0:
        t0 = time.perf_counter()
        result = _extract_job(payload)
        result["seconds"] = round(time.perf_counter() - t0, 4)
        return result
    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue(1)
    try:
        proc = ctx.Process(target=_extract_job_queue, args=(payload, q))
        proc.start()
    except OSError as exc:
        return _failure_result(f"spawn_OSError: {exc}")
    t0 = time.perf_counter()
    try:
        # Read before join: child q.put of large payloads blocks until drained.
        result = q.get(timeout=page_timeout)
    except queue.Empty:
        elapsed = time.perf_counter() - t0
        if not proc.is_alive() and proc.exitcode not in (0, None):
            return _failure_result(f"worker_exitcode:{proc.exitcode}", seconds=elapsed)
        _kill_process(proc)
        return _failure_result(
            f"page_timeout:{page_timeout}",
            timeout=True,
            seconds=elapsed,
        )
    except Exception as exc:  # noqa: BLE001
        _kill_process(proc)
        return _failure_result(
            f"worker_queue: {type(exc).__name__}: {exc}",
            seconds=time.perf_counter() - t0,
        )
    proc.join(5)
    if proc.is_alive():
        _kill_process(proc)
    result = dict(result)
    result["seconds"] = round(time.perf_counter() - t0, 4)
    return result


def cache_path(cache_dir: Path, *parts: str) -> Path:
    path = cache_dir.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_json_cache(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def write_json_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_infrastructure_failure(result: dict) -> bool:
    err = str(result.get("error") or "")
    return any(marker in err for marker in INFRA_ERROR_MARKERS)


def is_page_timeout(result: dict) -> bool:
    return bool(result.get("timeout"))


def should_skip_extract_cache(result: dict) -> bool:
    """Timeouts and infra failures must not stick in cache (resume retries them)."""
    return is_infrastructure_failure(result) or is_page_timeout(result)


def run_extract(
    questions: list[dict],
    tools: tuple[str, ...] = TOOLS,
    *,
    cache_dir: Path,
    workers: int = 4,
    page_timeout: float = 60.0,
) -> dict[str, dict[str, list[dict]]]:
    """Extract every page with every tool. Cache key hashes full extractor inputs."""
    out: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    jobs: list[tuple[str, str, int, str, dict]] = []
    key_paths: dict[tuple[str, str, int], Path] = {}
    live_results: dict[tuple[str, str, int], dict] = {}

    for rec in questions:
        qid = question_id(rec)
        pages = rec.get("search_results") or []
        for tool in tools:
            for pi, page in enumerate(pages):
                html = page.get("page_result") or ""
                url = page.get("page_url")
                key = extract_cache_key(html=html, tool=tool, url=url)
                cpath = cache_path(cache_dir, "extract", key[:2], f"{key}.json")
                key_paths[(qid, tool, pi)] = cpath
                hit = read_json_cache(cpath)
                if hit is not None and not should_skip_extract_cache(hit):
                    continue
                if hit is not None and should_skip_extract_cache(hit):
                    cpath.unlink(missing_ok=True)
                jobs.append(
                    (
                        qid,
                        tool,
                        pi,
                        key,
                        {"tool": tool, "html": html, "url": url},
                    )
                )

    page_seconds: list[float] = []
    if jobs:
        worker_pool = ExtractWorkerPool(max(1, workers), page_timeout)
        try:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futs = {
                    pool.submit(worker_pool.run, payload): (qid, tool, pi, key)
                    for qid, tool, pi, key, payload in jobs
                }
                for fut in as_completed(futs):
                    qid, tool, pi, key = futs[fut]
                    try:
                        result = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        result = _failure_result(f"{type(exc).__name__}: {exc}")
                    sec = result.get("seconds")
                    if isinstance(sec, (int, float)):
                        page_seconds.append(float(sec))
                    # Skip infra + timeouts (load-dependent); keep timeouts for this run's report.
                    if should_skip_extract_cache(result):
                        if is_page_timeout(result):
                            live_results[(qid, tool, pi)] = result
                        continue
                    cpath = cache_path(cache_dir, "extract", key[:2], f"{key}.json")
                    write_json_cache(cpath, result)
        finally:
            worker_pool.close()
        if page_seconds:
            mean_s = statistics.mean(page_seconds)
            print(
                f"extract: {len(page_seconds)} pages, "
                f"mean_seconds_per_page={mean_s:.3f} "
                f"(workers={workers}, timeout={page_timeout})"
            )

    for rec in questions:
        qid = question_id(rec)
        pages = rec.get("search_results") or []
        for tool in tools:
            rows = []
            for pi in range(len(pages)):
                live = live_results.get((qid, tool, pi))
                if live is not None:
                    rows.append(live)
                    continue
                cpath = key_paths.get((qid, tool, pi))
                hit = read_json_cache(cpath) if cpath else None
                if hit is None:
                    hit = {
                        "ok": False,
                        "text": "",
                        "empty": True,
                        "error": "missing_cache",
                        "timeout": False,
                        "words": 0,
                    }
                rows.append(hit)
            out[qid][tool] = rows
    return out


# ---------------------------------------------------------------------------
# Retrieve (harness-local chunker: BM25 tokens, newlines preserved, no FM strip)
# ---------------------------------------------------------------------------


def bm25_token_count(text: str) -> int:
    return len(tokenize(text or ""))


def chunk_markdown_harness(text: str, *, max_tokens: int = CHUNK_WORDS) -> list[str]:
    """Pack paragraphs into chunks bounded by BM25 alphanumeric tokens."""
    if not (text or "").strip():
        return []
    chunks: list[str] = []
    current_parts: list[str] = []
    current_n = 0

    def flush() -> None:
        nonlocal current_parts, current_n
        if not current_parts:
            return
        chunk = "\n\n".join(current_parts)
        if tokenize(chunk):
            chunks.append(chunk)
        current_parts = []
        current_n = 0

    def append_piece(piece: str) -> None:
        nonlocal current_n
        pt = bm25_token_count(piece)
        if pt == 0:
            return
        if current_n + pt > max_tokens and current_parts:
            flush()
        if pt > max_tokens:
            for line in piece.split("\n"):
                line = line.rstrip()
                if not line.strip():
                    continue
                # A single line longer than the budget is split by words.
                line_words = line.split()
                start = 0
                while start < len(line_words):
                    end, used = start, 0
                    while end < len(line_words):
                        wt = bm25_token_count(line_words[end])
                        if used + wt > max_tokens and end > start:
                            break
                        used += wt
                        end += 1
                    part = " ".join(line_words[start:end])
                    if current_n + used > max_tokens and current_parts:
                        flush()
                    current_parts.append(part)
                    current_n += used
                    start = end
            return
        current_parts.append(piece)
        current_n += pt

    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        append_piece(para)
    flush()
    return chunks


def page_indexed_token_count(page_text: str) -> int:
    return sum(bm25_token_count(c) for c in chunk_markdown_harness(page_text))


def retrieve_for_tool(query: str, page_texts: list[str], *, top_k: int = TOP_K) -> dict:
    chunks: list[str] = []
    for text in page_texts:
        if not (text or "").strip():
            continue
        chunks.extend(chunk_markdown_harness(text, max_tokens=CHUNK_WORDS))
    if not chunks:
        return {"chunks": [], "indices": [], "n_chunks_indexed": 0}
    docs = [tokenize(c) for c in chunks]
    bm25 = BM25(docs)
    indices = bm25.search(tokenize(query), top_k)
    return {
        "chunks": [chunks[i] for i in indices],
        "indices": indices,
        "n_chunks_indexed": len(chunks),
    }


def run_retrieve(
    questions: list[dict],
    extracts: dict[str, dict[str, list[dict]]],
    tools: tuple[str, ...] = TOOLS,
    *,
    cache_dir: Path,
) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in questions:
        qid = question_id(rec)
        query = rec["query"]
        for tool in tools:
            page_rows = extracts[qid][tool]
            page_texts = [row.get("text") or "" for row in page_rows]
            page_hashes = [html_hash(t) for t in page_texts]
            key = retrieve_cache_key(query=query, page_text_hashes=page_hashes, tool=tool)
            cpath = cache_path(cache_dir, "retrieve", key[:2], f"{key}.json")
            hit = read_json_cache(cpath)
            if hit is not None:
                out[qid][tool] = hit
                continue
            result = retrieve_for_tool(query, page_texts)
            write_json_cache(cpath, result)
            out[qid][tool] = result
    return out


def gold_in_top5(answer: str, chunks: list[str]) -> bool | None:
    """Secondary metric: gold string in top-5 chunks; only for answers ≤5 words."""
    words = answer.split()
    if len(words) == 0 or len(words) > SHORT_GOLD_WORDS:
        return None
    needle = _WS.sub(" ", answer).strip().lower()
    hay = _WS.sub(" ", " ".join(chunks)).lower()
    return needle in hay


# ---------------------------------------------------------------------------
# Spend persistence
# ---------------------------------------------------------------------------


def spend_path(cache_dir: Path) -> Path:
    return cache_dir / "spend_total.json"


def load_persisted_spend(cache_dir: Path) -> float:
    hit = read_json_cache(spend_path(cache_dir))
    if not hit:
        return 0.0
    return float(hit.get("spend_usd_total") or 0.0)


def save_persisted_spend(cache_dir: Path, total: float) -> None:
    write_json_cache(
        spend_path(cache_dir),
        {"spend_usd_total": round(total, 6)},
    )


# ---------------------------------------------------------------------------
# OpenAI client (key from environment only; no .env reads)
# ---------------------------------------------------------------------------


class BudgetExceeded(RuntimeError):
    """Spend cap hit. Optional ``partial_out`` / ``dry_info`` carry mid-stage progress."""

    def __init__(
        self,
        message: str = "",
        *,
        partial_out: dict | None = None,
        dry_info: dict | None = None,
        stage: str | None = None,
    ) -> None:
        super().__init__(message)
        self.partial_out = partial_out if partial_out is not None else {}
        self.dry_info = dry_info if dry_info is not None else {}
        self.stage = stage


class OpenAIClient:
    """Minimal chat client with spend tracking, retries, and optional CA bundle."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_usd: float = 5.0,
        ca_bundle: str | None = None,
        price_in: float = 0.20,
        price_out: float = 0.75,
        base_url: str = "https://api.openai.com/v1",
        starting_spend_usd: float = 0.0,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("Set OPENAI_API_KEY in the environment.")
        self.max_usd = max_usd
        self.price_in = price_in
        self.price_out = price_out
        self.spend_usd = float(starting_spend_usd)
        self.spend_this_run = 0.0
        self.tokens_in = 0
        self.tokens_out = 0
        self.calls = 0
        self._reserved = 0.0
        self._lock = threading.Lock()
        self.temperature_dropped_generate = False
        self.temperature_dropped_judge = False
        verify: str | bool = ca_bundle if ca_bundle else True
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(120.0, connect=20.0),
            verify=verify,
            headers={"Authorization": f"Bearer {key}"},
        )

    def _charge_usage_dict(self, usage: dict | None) -> float:
        if not usage:
            return 0.0
        tin = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        tout = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        if tin == 0 and tout == 0:
            return 0.0
        return self._charge(tin, tout)

    def _charge(self, tokens_in: int, tokens_out: int) -> float:
        """Account usage. Keep responses that cross the cap; stop before the next call."""
        cost = tokens_in / 1e6 * self.price_in + tokens_out / 1e6 * self.price_out
        with self._lock:
            self.spend_usd = round(self.spend_usd + cost, 6)
            self.spend_this_run = round(self.spend_this_run + cost, 6)
            self.tokens_in += tokens_in
            self.tokens_out += tokens_out
            self.calls += 1
        return cost

    def _reserve(self, est_cost: float) -> None:
        with self._lock:
            if self.spend_usd + self._reserved >= self.max_usd:
                raise BudgetExceeded(
                    f"OpenAI spend already at ${self.spend_usd:.3f} "
                    f"(reserved ${self._reserved:.3f}, cap ${self.max_usd:.2f})"
                )
            if self.spend_usd + self._reserved + est_cost > self.max_usd:
                raise BudgetExceeded(
                    f"OpenAI reserved spend would exceed ${self.max_usd:.2f} "
                    f"(spent ${self.spend_usd:.3f}, reserved ${self._reserved:.3f})"
                )
            self._reserved += est_cost

    def _release_reserve(self, est_cost: float) -> None:
        with self._lock:
            self._reserved = max(0.0, round(self._reserved - est_cost, 6))

    def _maybe_charge_response_body(self, text: str) -> None:
        """Count usage from any response body that carries it (including retries)."""
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return
        if isinstance(data, dict):
            self._charge_usage_dict(data.get("usage"))

    def _post(self, path: str, payload: dict) -> dict:
        for attempt in range(5):
            try:
                r = self._client.post(path, json=payload)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt >= 4:
                    raise RuntimeError(f"OpenAI {path} network error: {exc}") from exc
                time.sleep(2**attempt)
                continue
            # Bill any body that reports usage, even on error / retry paths.
            self._maybe_charge_response_body(r.text)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2**attempt)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"OpenAI {path} {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError(f"OpenAI {path} kept failing after retries")

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
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_completion_tokens is not None:
            payload["max_completion_tokens"] = max_completion_tokens

        est_in = estimate_tokens(system) + estimate_tokens(user)
        est_out = int(max_completion_tokens or 256)
        est_cost = estimate_cost(est_in, est_out, self.price_in, self.price_out)
        self._reserve(est_cost)
        temp_dropped = False
        try:
            try:
                data = self._post("/chat/completions", payload)
            except RuntimeError as exc:
                if temperature is not None and "temperature" in str(exc).lower():
                    payload.pop("temperature", None)
                    temp_dropped = True
                    data = self._post("/chat/completions", payload)
                else:
                    raise
            usage = data.get("usage") or {}
            # Usage may already have been charged from the raw body; charge delta only if needed.
            # Prefer explicit charge here for the successful completion path when body had no usage.
            tin = int(usage.get("prompt_tokens") or 0)
            tout = int(usage.get("completion_tokens") or 0)
            # Avoid double-charge: _maybe_charge_response_body already billed on HTTP response.
            # Track via a marker on the response cycle — re-read spend before/after is fragile.
            # Instead: _post charges from body; if usage present we already billed. Only charge
            # here when usage dict is empty (offline fakes / stubs).
            cost = 0.0
            if not usage:
                cost = self._charge(tin, tout)
            else:
                # Already billed in _post; report nominal cost for callers.
                cost = tin / 1e6 * self.price_in + tout / 1e6 * self.price_out
            choice = (data.get("choices") or [{}])[0]
            text = (choice.get("message") or {}).get("content") or ""
            finish_reason = choice.get("finish_reason")
            if temp_dropped:
                with self._lock:
                    if purpose == "judge":
                        self.temperature_dropped_judge = True
                    else:
                        self.temperature_dropped_generate = True
            meta = {
                "prompt_tokens": tin,
                "completion_tokens": tout,
                "finish_reason": finish_reason,
                "temperature_dropped": temp_dropped,
            }
            return text, cost, meta
        finally:
            self._release_reserve(est_cost)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost(tokens_in: int, tokens_out: int, price_in: float, price_out: float) -> float:
    return tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out


# ---------------------------------------------------------------------------
# Generate / judge
# ---------------------------------------------------------------------------


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    if bm25_token_count(text) <= max_tokens:
        return text
    lines: list[str] = []
    n = 0
    for line in text.split("\n"):
        lt = bm25_token_count(line)
        if n + lt <= max_tokens:
            lines.append(line)
            n += lt
            continue
        room = max_tokens - n
        if room > 0:
            words = line.split()
            kept: list[str] = []
            used = 0
            for w in words:
                wt = bm25_token_count(w)
                if used + wt > room and kept:
                    break
                kept.append(w)
                used += wt
                if used >= room:
                    break
            if kept:
                lines.append(" ".join(kept))
                n += used
        break
    return "\n".join(lines)


def _cap_context(chunks: list[str], token_cap: int = CONTEXT_WORD_CAP) -> str:
    parts: list[str] = []
    total = 0
    for ch in chunks:
        ct = bm25_token_count(ch)
        if total >= token_cap:
            break
        if total + ct <= token_cap:
            parts.append(ch)
            total += ct
            continue
        room = token_cap - total
        if room > 0:
            parts.append(_truncate_to_tokens(ch, room))
        break
    return "\n\n".join(parts)


def generate_prompt(
    query: str, chunks: list[str], query_time: Any = None
) -> tuple[str, str]:
    context = _cap_context(chunks)
    qt = _normalized_query_time(query_time)
    if qt:
        user = f"Context:\n{context}\n\nQuery time: {qt}\nQuestion: {query}\nAnswer:"
    else:
        user = f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    return GENERATE_SYSTEM, user


def is_idk(text: str) -> bool:
    return bool(IDK_RE.match((text or "").strip()))


def judge_system_for_rubric(rubric: str) -> str:
    r = (rubric or "v1").strip().lower()
    if r in ("v1", "1"):
        return JUDGE_SYSTEM
    if r in ("v2", "2"):
        return JUDGE_RUBRIC_V2
    raise ValueError(f"unknown rubric {rubric!r}; use v1 or v2")


def judge_prompt(
    query: str,
    gold: str,
    alt_ans: list,
    generated: str,
    *,
    judge_system: str = JUDGE_SYSTEM,
    query_time: Any = None,
) -> tuple[str, str]:
    alts = json.dumps(alt_ans or [], ensure_ascii=False)
    qt = _normalized_query_time(query_time)
    qt_line = f"Query time: {qt}\n" if qt else ""
    user = (
        f"Question: {query}\n"
        f"{qt_line}"
        f"Gold answer: {gold}\n"
        f"Alt answers: {alts}\n"
        f"Generated answer: {generated}\n"
    )
    return judge_system, user


def parse_judge_label(text: str) -> tuple[str | None, str]:
    """Return (label, reason) or (None, reason) if unparseable/invalid."""
    label, reason, _rule = parse_judge_label_v2(text, require_rule_id=False)
    return label, reason


def parse_judge_label_v2(
    text: str, *, require_rule_id: bool = True
) -> tuple[str | None, str, str | None]:
    """Return (label, reason, rule_id) for v2 judge JSON."""
    try:
        verdict = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, "unparseable_judge", None
    if not isinstance(verdict, dict):
        return None, "unparseable_judge", None
    label = str(verdict.get("label", "")).strip().lower()
    reason = str(verdict.get("reason", ""))[:300]
    rule_id = str(verdict.get("rule_id", "")).strip().upper() or None
    if label not in VALID_LABELS:
        return None, reason or "invalid_label", rule_id
    if require_rule_id:
        if rule_id not in ANSWER_RULE_IDS:
            return None, reason or "invalid_rule_id", rule_id
        if rule_id not in RULES_BY_LABEL[label]:
            return None, reason or "rule_id_does_not_fit_label", rule_id
    return label, reason, rule_id


def run_generate(
    questions: list[dict],
    retrievals: dict[str, dict[str, dict]],
    tools: tuple[str, ...] = TOOLS,
    *,
    cache_dir: Path,
    client: Any,
    model: str,
    workers: int = 4,
    dry_run: bool = False,
    price_in: float = 0.20,
    price_out: float = 0.75,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_GENERATE,
) -> tuple[dict[str, dict[str, dict]], dict]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    pending_by_key: dict[str, tuple[str, str, str]] = {}  # key -> system, user, sample qid
    assign: list[tuple[str, str, str]] = []  # qid, tool, key
    est_in = 0
    est_out = 0
    generate_error_count = 0
    generate_error_messages: list[str] = []
    slot_count = 0

    for rec in questions:
        qid = question_id(rec)
        qt = rec.get("query_time")
        for tool in tools:
            chunks = retrievals[qid][tool].get("chunks") or []
            system, user = generate_prompt(rec["query"], chunks, query_time=qt)
            key = generate_cache_key(
                query=rec["query"],
                chunks=chunks,
                model=model,
                prompt_system=system,
                max_completion_tokens=max_completion_tokens,
                temperature=0.0,
                query_time=qt,
            )
            assign.append((qid, tool, key))
            slot_count += 1
            cpath = cache_path(cache_dir, "generate", key[:2], f"{key}.json")
            hit = read_json_cache(cpath)
            if hit is not None:
                out[qid][tool] = hit
                continue
            if key not in pending_by_key:
                pending_by_key[key] = (system, user, qid)
                est_in += estimate_tokens(system) + estimate_tokens(user)
                est_out += min(64, max_completion_tokens)

    pending = list(pending_by_key.items())
    cache_hits = sum(
        1
        for _qid, _tool, key in assign
        if read_json_cache(cache_path(cache_dir, "generate", key[:2], f"{key}.json"))
        is not None
    )
    unique_pending = len(pending_by_key)
    calls_saved = max(0, slot_count - cache_hits - unique_pending)

    dry_info = {
        "generate_calls": unique_pending,
        "generate_slots": slot_count,
        "generate_calls_saved": calls_saved,
        "est_prompt_tokens": est_in,
        "est_completion_tokens": est_out,
        "est_usd": round(estimate_cost(est_in, est_out, price_in, price_out), 6),
        "generate_errors": 0,
        "generate_error_messages": [],
    }
    if dry_run:
        return out, dry_info

    def _one(key: str, system: str, user: str) -> tuple[str, dict]:
        text, cost, usage = client.chat(
            model,
            system,
            user,
            temperature=0.0,
            json_mode=False,
            max_completion_tokens=max_completion_tokens,
            purpose="generate",
        )
        row = {
            "answer": text.strip(),
            "cost_usd": round(cost, 6),
            "usage": usage,
            "finish_reason": usage.get("finish_reason"),
        }
        return key, row

    budget_hit = False
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {
            pool.submit(_one, key, system, user): key
            for key, (system, user, _qid) in pending
        }
        for fut in as_completed(futs):
            try:
                key, row = fut.result()
            except BudgetExceeded:
                budget_hit = True
                continue
            except Exception as exc:  # noqa: BLE001
                generate_error_count += 1
                if len(generate_error_messages) < 5:
                    generate_error_messages.append(f"{type(exc).__name__}: {exc}")
                continue
            write_json_cache(cache_path(cache_dir, "generate", key[:2], f"{key}.json"), row)
            for qid, tool, akey in assign:
                if akey == key:
                    out[qid][tool] = row

    # Reload any cached rows (including from prior partial progress).
    for qid, tool, key in assign:
        if tool in out.get(qid, {}):
            continue
        hit = read_json_cache(cache_path(cache_dir, "generate", key[:2], f"{key}.json"))
        if hit is not None:
            out[qid][tool] = hit

    dry_info["generate_errors"] = generate_error_count
    dry_info["generate_error_messages"] = generate_error_messages

    if budget_hit:
        raise BudgetExceeded(
            "generate stage stopped on budget",
            partial_out=out,
            dry_info=dry_info,
            stage="generate",
        )
    return out, dry_info


def run_judge(
    questions: list[dict],
    generations: dict[str, dict[str, dict]],
    tools: tuple[str, ...] = TOOLS,
    *,
    cache_dir: Path,
    client: Any,
    model: str,
    seed: int,
    workers: int = 4,
    dry_run: bool = False,
    price_in: float = 0.20,
    price_out: float = 0.75,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_JUDGE,
    assume_no_tool_dedup: bool = False,
    judge_system: str = JUDGE_SYSTEM,
    rubric_version: str = "v1",
) -> tuple[dict[str, dict[str, dict]], dict]:
    """Blind judge: sees question, gold, alts, generated answer only — never tool/context."""
    require_rule = rubric_version.strip().lower() == "v2"
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    unique: dict[str, dict] = {}
    assign: list[tuple[str, str, str]] = []  # qid, tool, cache_key
    est_in = 0
    est_out = 0
    idk_count = 0
    empty_answer_count = 0
    empty_answer_length_count = 0
    judge_error_count = 0

    for rec in questions:
        qid = question_id(rec)
        for tool in tools:
            gen = generations.get(qid, {}).get(tool)
            if gen is None:
                continue
            answer = gen.get("answer") or ""
            finish_reason = gen.get("finish_reason") or (gen.get("usage") or {}).get(
                "finish_reason"
            )
            # Rule-based labels depend on answer + finish_reason; hash both into the cache.
            rule_path = cache_path(cache_dir, "judge", "rule", qid, f"{tool}.json")
            input_hash = rule_label_input_hash(answer, finish_reason)
            rule_hit = read_json_cache(rule_path)
            if rule_hit is not None and rule_hit.get("input_hash") == input_hash:
                out[qid][tool] = rule_hit
                reason = rule_hit.get("reason")
                if reason == "idk_rule":
                    idk_count += 1
                elif reason == "empty_answer_length":
                    empty_answer_length_count += 1
                elif reason == "empty_answer":
                    empty_answer_count += 1
                continue
            rule_row = rule_based_judge_row(answer, finish_reason)
            if rule_row is not None:
                write_json_cache(rule_path, rule_row)
                out[qid][tool] = rule_row
                reason = rule_row.get("reason")
                if reason == "idk_rule":
                    idk_count += 1
                elif reason == "empty_answer_length":
                    empty_answer_length_count += 1
                else:
                    empty_answer_count += 1
                continue

            key = judge_cache_key_full(
                query=rec["query"],
                query_time=rec.get("query_time"),
                gold=rec.get("answer") or "",
                alt_ans=rec.get("alt_ans") or [],
                answer=answer,
                model=model,
                prompt_system=judge_system,
            )
            # Dry-run no-dedup: force a unique key per tool so estimates do not collapse.
            est_key = f"{key}::{tool}" if assume_no_tool_dedup else key
            assign.append((qid, tool, key))
            jpath = cache_path(cache_dir, "judge", key[:2], f"{key}.json")
            if read_json_cache(jpath) is not None:
                continue
            if (not assume_no_tool_dedup) and key in unique:
                continue
            if assume_no_tool_dedup and est_key in unique:
                continue
            system, user = judge_prompt(
                rec["query"],
                rec.get("answer") or "",
                rec.get("alt_ans") or [],
                answer,
                judge_system=judge_system,
                query_time=rec.get("query_time"),
            )
            unique[est_key] = {"system": system, "user": user, "key": key}
            est_in += estimate_tokens(system) + estimate_tokens(user)
            est_out += min(48, max_completion_tokens)

    keys = list(unique)
    rng = random.Random(seed)
    rng.shuffle(keys)
    dry_info = {
        "judge_calls": len(keys),
        "idk_rule_labels": idk_count,
        "empty_answer": empty_answer_count,
        "empty_answer_length": empty_answer_length_count,
        "judge_errors": 0,
        "est_prompt_tokens": est_in,
        "est_completion_tokens": est_out,
        "est_usd": round(estimate_cost(est_in, est_out, price_in, price_out), 6),
    }
    if dry_run:
        return out, dry_info

    def _one(est_key: str) -> tuple[str, dict | None, bool]:
        """Return (cache_key, row_or_none, judge_error)."""
        job = unique[est_key]
        cache_key = job["key"]
        last_reason = "judge_error"
        total_cost = 0.0
        last_usage: dict = {}
        for _attempt in range(1 + JUDGE_PARSE_RETRIES):
            text, cost, usage = client.chat(
                model,
                job["system"],
                job["user"],
                temperature=0.0,
                json_mode=True,
                max_completion_tokens=max_completion_tokens,
                purpose="judge",
            )
            total_cost += cost
            last_usage = usage
            if require_rule:
                label, reason, rule_id = parse_judge_label_v2(text, require_rule_id=True)
            else:
                label, reason = parse_judge_label(text)
                rule_id = None
            if label is not None:
                row = {
                    "label": label,
                    "reason": reason,
                    "cost_usd": round(total_cost, 6),
                    "usage": usage,
                }
                if rule_id:
                    row["rule_id"] = rule_id
                return cache_key, row, False
            last_reason = reason or "judge_error"
        # Do not cache judge_error as a label.
        _ = last_reason
        _ = last_usage
        return cache_key, None, True

    budget_hit = False
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(_one, k): k for k in keys}
        for fut in as_completed(futs):
            try:
                cache_key, row, is_err = fut.result()
            except BudgetExceeded:
                budget_hit = True
                continue
            except Exception:  # noqa: BLE001
                judge_error_count += 1
                continue
            if is_err or row is None:
                judge_error_count += 1
                continue
            write_json_cache(cache_path(cache_dir, "judge", cache_key[:2], f"{cache_key}.json"), row)

    for qid, tool, key in assign:
        hit = read_json_cache(cache_path(cache_dir, "judge", key[:2], f"{key}.json"))
        if hit is not None:
            out[qid][tool] = hit

    dry_info["judge_errors"] = judge_error_count
    dry_info["empty_answer"] = empty_answer_count
    dry_info["empty_answer_length"] = empty_answer_length_count

    if budget_hit:
        raise BudgetExceeded(
            "judge stage stopped on budget",
            partial_out=out,
            dry_info=dry_info,
            stage="judge",
        )
    return out, dry_info


# ---------------------------------------------------------------------------
# Metrics / report
# ---------------------------------------------------------------------------


def _label_score(label: str) -> float:
    if label == "accurate":
        return 1.0
    if label == "incorrect":
        return -1.0
    return 0.0


def fully_labelled_question_ids(
    questions: list[dict],
    judgements: dict[str, dict[str, dict]],
    tools: tuple[str, ...],
) -> tuple[list[str], int]:
    """Intersection: questions with a valid label for every tool."""
    kept: list[str] = []
    for rec in questions:
        qid = question_id(rec)
        ok = True
        for tool in tools:
            lab = (judgements.get(qid) or {}).get(tool, {}).get("label")
            if lab not in VALID_LABELS:
                ok = False
                break
        if ok:
            kept.append(qid)
    dropped = len(questions) - len(kept)
    return kept, dropped


def paired_bootstrap_ci(
    per_q_a: list[float],
    per_q_b: list[float],
    seed: int,
    iters: int = BOOTSTRAP_ITERS,
) -> dict:
    n = len(per_q_a)
    if n == 0:
        return {"mean_diff": None, "ci95": [None, None]}
    diffs = [per_q_a[i] - per_q_b[i] for i in range(n)]
    rng = random.Random(seed)
    samples = sorted(
        statistics.mean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(iters)
    )
    return {
        "mean_diff": round(statistics.mean(diffs), 4),
        "ci95": [
            round(samples[int(0.025 * iters)], 4),
            round(samples[int(0.975 * iters) - 1], 4),
        ],
    }


def git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def page_stats(pages: list[dict]) -> dict:
    n_empty = sum(1 for p in pages if p.get("empty") and not p.get("error") and not p.get("timeout"))
    n_error = sum(1 for p in pages if p.get("error") and not p.get("timeout"))
    n_timeout = sum(1 for p in pages if p.get("timeout"))
    words_all = [float(p.get("words") or 0) for p in pages]
    ok_pages = [p for p in pages if p.get("ok") and not p.get("timeout") and not p.get("error")]
    words_ok = [float(p.get("words") or 0) for p in ok_pages]
    return {
        "n_pages_empty": n_empty,
        "n_pages_error": n_error,
        "n_pages_timeout": n_timeout,
        "mean_words_per_page_including_failed": round(statistics.mean(words_all), 2)
        if words_all
        else None,
        "mean_words_per_page_excluding_failed": round(statistics.mean(words_ok), 2)
        if words_ok
        else None,
    }


def summarize(
    questions: list[dict],
    extracts: dict[str, dict[str, list[dict]]],
    retrievals: dict[str, dict[str, dict]],
    judgements: dict[str, dict[str, dict]],
    tools: tuple[str, ...] = TOOLS,
    *,
    seed: int,
    model: str,
    spend_usd: float,
    spend_this_run: float = 0.0,
    spend_total: float | None = None,
    exclusion_counts: dict,
    chosen_ids: list[str],
    partial: bool = False,
    judge_errors: int = 0,
    generate_errors: int = 0,
    generate_error_messages: list[str] | None = None,
    empty_answer: int = 0,
    empty_answer_length: int = 0,
    temperature_dropped_generate: bool = False,
    temperature_dropped_judge: bool = False,
) -> dict:
    labelled_ids, n_dropped = fully_labelled_question_ids(questions, judgements, tools)
    labelled_set = set(labelled_ids)
    scored_questions = [r for r in questions if question_id(r) in labelled_set]

    by_tool: dict[str, dict] = {}
    per_q_score: dict[str, list[float]] = {t: [] for t in tools}
    domains = sorted({str(r.get("domain") or "unknown") for r in scored_questions})

    def _tool_page_failure_stats(recs: list[dict], tool: str) -> dict:
        n_pages_empty = 0
        n_pages_error = 0
        n_pages_timeout = 0
        n_questions_no_chunks = 0
        words_incl: list[float] = []
        words_excl: list[float] = []
        seconds: list[float] = []
        indexed_tokens_total = 0
        n_pages = 0
        for rec in recs:
            qid = question_id(rec)
            pages = extracts.get(qid, {}).get(tool) or []
            ps = page_stats(pages)
            n_pages_empty += ps["n_pages_empty"]
            n_pages_error += ps["n_pages_error"]
            n_pages_timeout += ps["n_pages_timeout"]
            for p in pages:
                n_pages += 1
                words_incl.append(float(p.get("words") or 0))
                if p.get("ok") and not p.get("timeout") and not p.get("error"):
                    words_excl.append(float(p.get("words") or 0))
                    indexed_tokens_total += page_indexed_token_count(p.get("text") or "")
                sec = p.get("seconds")
                if isinstance(sec, (int, float)):
                    seconds.append(float(sec))
            chunks = (retrievals.get(qid) or {}).get(tool, {}).get("chunks") or []
            if not chunks:
                n_questions_no_chunks += 1
        mean_indexed = (
            round(indexed_tokens_total / n_pages, 2) if n_pages else None
        )
        return {
            "n_questions": len(recs),
            "n_pages_empty": n_pages_empty,
            "n_pages_error": n_pages_error,
            "n_pages_timeout": n_pages_timeout,
            "n_questions_no_chunks": n_questions_no_chunks,
            "mean_words_indexed_per_page": mean_indexed,
            "mean_words_per_page_including_failed": round(statistics.mean(words_incl), 2)
            if words_incl
            else None,
            "mean_words_per_page_excluding_failed": round(statistics.mean(words_excl), 2)
            if words_excl
            else None,
            "mean_seconds_per_page": round(statistics.mean(seconds), 4) if seconds else None,
        }

    all_sampled_tools: dict[str, dict] = {}
    for tool in tools:
        labels = []
        gold_hits = []
        by_domain: dict[str, Counter] = defaultdict(Counter)
        # Failure/word stats use the same population as the rates (scored intersection).
        scored_stats = _tool_page_failure_stats(scored_questions, tool)
        all_sampled_tools[tool] = _tool_page_failure_stats(questions, tool)

        for rec in scored_questions:
            qid = question_id(rec)
            domain = str(rec.get("domain") or "unknown")
            lab = judgements[qid][tool]["label"]
            labels.append(lab)
            by_domain[domain][lab] += 1
            # Never invent a 0 for unlabelled — only fully labelled ids reach here.
            per_q_score[tool].append(_label_score(lab))
            ans = str(rec.get("answer") or "")
            chunks = (retrievals.get(qid) or {}).get(tool, {}).get("chunks") or []
            g = gold_in_top5(ans, chunks)
            if g is not None:
                gold_hits.append(1.0 if g else 0.0)

        n = len(labels)
        accurate = sum(1 for x in labels if x == "accurate")
        missing = sum(1 for x in labels if x == "missing")
        incorrect = sum(1 for x in labels if x == "incorrect")
        domain_table = {}
        for d in domains:
            c = by_domain[d]
            dn = sum(c.values())
            if dn == 0:
                continue
            domain_table[d] = {
                "n": dn,
                "accurate": round(c["accurate"] / dn, 4),
                "missing": round(c["missing"] / dn, 4),
                "incorrect": round(c["incorrect"] / dn, 4),
                "crag_score": round((c["accurate"] - c["incorrect"]) / dn, 4),
            }
        by_tool[tool] = {
            "n": n,
            "accurate": round(accurate / n, 4) if n else None,
            "missing": round(missing / n, 4) if n else None,
            "incorrect": round(incorrect / n, 4) if n else None,
            "crag_score": round((accurate - incorrect) / n, 4) if n else None,
            "n_pages_empty": scored_stats["n_pages_empty"],
            "n_pages_error": scored_stats["n_pages_error"],
            "n_pages_timeout": scored_stats["n_pages_timeout"],
            "n_questions_no_chunks": scored_stats["n_questions_no_chunks"],
            "mean_words_indexed_per_page": scored_stats["mean_words_indexed_per_page"],
            "mean_words_per_page_including_failed": scored_stats[
                "mean_words_per_page_including_failed"
            ],
            "mean_words_per_page_excluding_failed": scored_stats[
                "mean_words_per_page_excluding_failed"
            ],
            "mean_seconds_per_page": scored_stats["mean_seconds_per_page"],
            "gold_in_top5_short": round(statistics.mean(gold_hits), 4) if gold_hits else None,
            "gold_in_top5_short_n": len(gold_hits),
            "by_domain": domain_table,
            "extractor_config": extractor_config_for_tool(tool),
        }

    boot = []
    ref = "trafilatura"
    for tool in tools:
        if tool == ref:
            continue
        boot.append(
            {
                "comparison": f"{tool} - {ref}",
                **paired_bootstrap_ci(per_q_score[tool], per_q_score[ref], seed),
            }
        )
    if "chromerag_coverage" in per_q_score and "chromerag_balanced" in per_q_score:
        boot.append(
            {
                "comparison": "chromerag_coverage - chromerag_balanced",
                **paired_bootstrap_ci(
                    per_q_score["chromerag_coverage"],
                    per_q_score["chromerag_balanced"],
                    seed + 1,
                ),
            }
        )

    total = spend_total if spend_total is not None else spend_usd
    return {
        "partial": partial,
        "model": model,
        "seed": seed,
        "git_commit": git_commit(),
        "spend_usd": round(spend_usd, 6),
        "spend_this_run": round(spend_this_run, 6),
        "spend_total": round(total, 6),
        "chosen_question_ids": chosen_ids,
        "scored_question_ids": labelled_ids,
        "n_scored": len(labelled_ids),
        "n_dropped_incomplete_labels": n_dropped,
        "judge_errors": judge_errors,
        "generate_errors": generate_errors,
        "generate_error_messages": list(generate_error_messages or [])[:5],
        "empty_answer": empty_answer,
        "empty_answer_length": empty_answer_length,
        "exclusion_counts": exclusion_counts,
        "temperature_dropped_generate": temperature_dropped_generate,
        "temperature_dropped_judge": temperature_dropped_judge,
        "url_input_note": (
            "ChromeRAG and trafilatura receive page_url; markitdown baselines do not."
        ),
        "tools": by_tool,
        "all_sampled": {
            "n_questions": len(questions),
            "tools": all_sampled_tools,
        },
        "paired_bootstrap_crag": boot,
    }


def load_cached_extracts(
    questions: list[dict],
    *,
    from_cache: Path,
    tools: tuple[str, ...] = TOOLS,
) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for rec in questions:
        qid = question_id(rec)
        pages = rec.get("search_results") or []
        for tool in tools:
            rows = []
            for pi, page in enumerate(pages):
                html = page.get("page_result") or ""
                url = page.get("page_url")
                key = extract_cache_key(html=html, tool=tool, url=url)
                cpath = cache_path(from_cache, "extract", key[:2], f"{key}.json")
                hit = read_json_cache(cpath)
                if hit is None:
                    hit = {
                        "ok": False,
                        "text": "",
                        "empty": True,
                        "error": "missing_cache",
                        "timeout": False,
                        "words": 0,
                    }
                rows.append(hit)
            out[qid][tool] = rows
    return out


def load_cached_retrievals(
    questions: list[dict],
    extracts: dict[str, dict[str, list[dict]]],
    *,
    from_cache: Path,
    tools: tuple[str, ...] = TOOLS,
) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in questions:
        qid = question_id(rec)
        query = rec["query"]
        for tool in tools:
            page_rows = extracts[qid][tool]
            page_texts = [row.get("text") or "" for row in page_rows]
            page_hashes = [html_hash(t) for t in page_texts]
            key = retrieve_cache_key(query=query, page_text_hashes=page_hashes, tool=tool)
            cpath = cache_path(from_cache, "retrieve", key[:2], f"{key}.json")
            hit = read_json_cache(cpath)
            if hit is None:
                hit = {"chunks": [], "indices": [], "n_chunks_indexed": 0}
            out[qid][tool] = hit
    return out


def load_cached_generations(
    questions: list[dict],
    retrievals: dict[str, dict[str, dict]],
    *,
    from_cache: Path,
    model: str,
    tools: tuple[str, ...] = TOOLS,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_GENERATE,
) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in questions:
        qid = question_id(rec)
        qt = rec.get("query_time")
        for tool in tools:
            chunks = (retrievals.get(qid) or {}).get(tool, {}).get("chunks") or []
            system, _user = generate_prompt(rec["query"], chunks, query_time=qt)
            key = generate_cache_key(
                query=rec["query"],
                chunks=chunks,
                model=model,
                prompt_system=system,
                max_completion_tokens=max_completion_tokens,
                temperature=0.0,
                query_time=qt,
            )
            hit = read_json_cache(
                cache_path(from_cache, "generate", key[:2], f"{key}.json")
            )
            if hit is not None:
                out[qid][tool] = hit
    return out


def rule_based_judge_row(answer: str, finish_reason: Any) -> dict | None:
    """Same IDK/empty rules for v1 and v2; None when an LLM judge call is required."""
    input_hash = rule_label_input_hash(answer, finish_reason)
    if is_idk(answer):
        return {
            "label": "missing",
            "reason": "idk_rule",
            "rule_id": "R-MISS",
            "cost_usd": 0.0,
            "cached": False,
            "input_hash": input_hash,
        }
    if not str(answer).strip():
        if finish_reason == "length":
            return {
                "label": "missing",
                "reason": "empty_answer_length",
                "rule_id": "R-MISS",
                "cost_usd": 0.0,
                "cached": False,
                "input_hash": input_hash,
            }
        return {
            "label": "missing",
            "reason": "empty_answer",
            "rule_id": "R-MISS",
            "cost_usd": 0.0,
            "cached": False,
            "input_hash": input_hash,
        }
    return None


def load_cached_v1_judgement(
    rec: dict,
    tool: str,
    answer: str,
    finish_reason: Any,
    *,
    from_cache: Path,
    model: str,
) -> dict | None:
    qid = question_id(rec)
    input_hash = rule_label_input_hash(answer, finish_reason)
    rule_path = cache_path(from_cache, "judge", "rule", qid, f"{tool}.json")
    rule_hit = read_json_cache(rule_path)
    if rule_hit is not None and rule_hit.get("input_hash") == input_hash:
        return rule_hit
    rule_row = rule_based_judge_row(answer, finish_reason)
    if rule_row is not None:
        return rule_row
    key = judge_cache_key_full(
        query=rec["query"],
        query_time=rec.get("query_time"),
        gold=rec.get("answer") or "",
        alt_ans=rec.get("alt_ans") or [],
        answer=answer,
        model=model,
        prompt_system=JUDGE_SYSTEM,
    )
    return read_json_cache(cache_path(from_cache, "judge", key[:2], f"{key}.json"))


def rule_id_counts(judgements: dict[str, dict[str, dict]], tools: tuple[str, ...]) -> dict[str, int]:
    counts: Counter = Counter()
    for qid, by_tool in judgements.items():
        _ = qid
        for tool in tools:
            row = by_tool.get(tool) or {}
            rid = row.get("rule_id")
            if rid:
                counts[str(rid)] += 1
    return dict(counts)


def label_changes_v1_v2_by_tool(
    v1: dict[str, dict[str, dict]],
    v2: dict[str, dict[str, dict]],
    tools: tuple[str, ...],
) -> dict[str, dict[str, int]]:
    out: dict[str, Counter] = {t: Counter() for t in tools}
    qids = set(v1) | set(v2)
    for qid in qids:
        for tool in tools:
            a = (v1.get(qid) or {}).get(tool, {}).get("label")
            b = (v2.get(qid) or {}).get(tool, {}).get("label")
            if a not in VALID_LABELS or b not in VALID_LABELS:
                continue
            if a == b:
                continue
            out[tool][f"{a}->{b}"] += 1
    return {t: dict(c) for t, c in out.items()}


def questions_from_prior_report(
    records: list[dict], prior: dict, *, seed: int, n: int
) -> list[dict]:
    ids = prior.get("chosen_question_ids")
    if not ids:
        raise SystemExit("--rejudge-only needs --prior-out with chosen_question_ids")
    by_id = {question_id(r): r for r in records}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise ValueError(f"prior report ids missing from data: {missing[:5]}")
    return [by_id[i] for i in ids]


def run_rejudge_only(
    args: argparse.Namespace,
    *,
    client_factory: Callable[..., Any] | None = None,
) -> dict:
    if args.from_cache is None or args.cache_dir is None or args.out is None or args.data is None:
        raise SystemExit("--rejudge-only requires --data, --from-cache, --cache-dir, and --out")
    if args.rubric.strip().lower() not in ("v2", "2"):
        raise SystemExit("--rejudge-only requires --rubric v2")
    from_cache = args.from_cache.resolve()
    cache_dir = args.cache_dir.resolve()
    if from_cache == cache_dir:
        raise SystemExit("--from-cache must differ from --cache-dir (original cache is read-only)")
    judge_system = judge_system_for_rubric("v2")
    records = load_crag_records(
        args.data,
        split=args.split,
        limit=args.limit,
        locked_run=getattr(args, "locked_split_1", False),
    )
    prior: dict = {}
    if args.prior_out and args.prior_out.exists():
        prior = json.loads(args.prior_out.read_text(encoding="utf-8"))
    sampled = questions_from_prior_report(records, prior, seed=args.seed, n=args.n)
    if prior.get("model") != args.model:
        raise SystemExit(f"--model {args.model} differs from prior run {prior.get('model')}")
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    prior_spend = load_persisted_spend(args.cache_dir)

    extracts = load_cached_extracts(sampled, from_cache=from_cache)
    retrievals = load_cached_retrievals(sampled, extracts, from_cache=from_cache)
    max_gen_tok = getattr(
        args, "max_completion_tokens_generate", DEFAULT_MAX_COMPLETION_GENERATE
    )
    generations = load_cached_generations(
        sampled,
        retrievals,
        from_cache=from_cache,
        model=args.model,
        max_completion_tokens=max_gen_tok,
    )
    lost = [
        (question_id(rec), tool)
        for rec in sampled
        for tool in TOOLS
        if not generations.get(question_id(rec), {}).get(tool)
    ]
    if lost:
        raise SystemExit(f"{len(lost)} cached answers not found, e.g. {lost[:3]}; check model and caps")
    v1: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in sampled:
        qid = question_id(rec)
        for tool in TOOLS:
            gen = generations.get(qid, {}).get(tool)
            if not gen:
                continue
            ans = gen.get("answer") or ""
            fr = gen.get("finish_reason") or (gen.get("usage") or {}).get("finish_reason")
            hit = load_cached_v1_judgement(
                rec, tool, ans, fr, from_cache=from_cache, model=args.model
            )
            if hit:
                v1[qid][tool] = hit

    max_judge_tok = getattr(args, "max_completion_tokens_judge", DEFAULT_MAX_COMPLETION_JUDGE)
    if args.dry_run:
        _, dry_judge = run_judge(
            sampled,
            generations,
            cache_dir=args.cache_dir,
            client=None,
            model=args.model,
            seed=args.seed,
            dry_run=True,
            price_in=args.price_in,
            price_out=args.price_out,
            max_completion_tokens=max_judge_tok,
            judge_system=judge_system,
            rubric_version="v2",
        )
        report = {
            "dry_run": True,
            "rejudge_only": True,
            "rubric": "v2",
            "from_cache": str(from_cache),
            "cache_dir": str(args.cache_dir),
            "n_questions": len(sampled),
            "judge": dry_judge,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            f"dry-run rejudge: judge_calls={dry_judge['judge_calls']} "
            f"est_usd={dry_judge.get('est_usd')}"
        )
        return report

    if prior_spend >= args.max_usd:
        raise BudgetExceeded(
            f"persisted spend ${prior_spend:.3f} already at/above cap ${args.max_usd:.2f}"
        )
    factory = client_factory or (
        lambda: OpenAIClient(
            max_usd=args.max_usd,
            ca_bundle=args.ca_bundle,
            price_in=args.price_in,
            price_out=args.price_out,
            starting_spend_usd=prior_spend,
        )
    )
    client = factory()
    partial = False
    v2: dict[str, dict[str, dict]] = defaultdict(dict)
    dry_judge: dict = {}
    try:
        try:
            v2, dry_judge = run_judge(
                sampled,
                generations,
                cache_dir=args.cache_dir,
                client=client,
                model=args.model,
                seed=args.seed,
                workers=args.workers,
                price_in=args.price_in,
                price_out=args.price_out,
                max_completion_tokens=max_judge_tok,
                judge_system=judge_system,
                rubric_version="v2",
            )
        except BudgetExceeded as exc:
            partial = True
            print(f"Stopped on budget: {exc}")
            if exc.dry_info:
                dry_judge = exc.dry_info
            for qid, tools_map in (exc.partial_out or {}).items():
                for tool, row in tools_map.items():
                    v2[qid][tool] = row
            # Reload any judge rows earned before the cap (incl. rule labels).
            for rec in sampled:
                qid = question_id(rec)
                for tool in TOOLS:
                    if tool in v2.get(qid, {}):
                        continue
                    gen = generations.get(qid, {}).get(tool)
                    if not gen:
                        continue
                    ans = gen.get("answer") or ""
                    fr = gen.get("finish_reason") or (gen.get("usage") or {}).get(
                        "finish_reason"
                    )
                    rule_path = cache_path(args.cache_dir, "judge", "rule", qid, f"{tool}.json")
                    rule = read_json_cache(rule_path)
                    if (
                        rule is not None
                        and rule.get("input_hash")
                        == rule_label_input_hash(ans, fr)
                    ):
                        v2[qid][tool] = rule
                        continue
                    jkey = judge_cache_key_full(
                        query=rec["query"],
                        query_time=rec.get("query_time"),
                        gold=rec.get("answer") or "",
                        alt_ans=rec.get("alt_ans") or [],
                        answer=ans,
                        model=args.model,
                        prompt_system=judge_system,
                    )
                    hit = read_json_cache(
                        cache_path(args.cache_dir, "judge", jkey[:2], f"{jkey}.json")
                    )
                    if hit is not None:
                        v2[qid][tool] = hit
    finally:
        save_persisted_spend(args.cache_dir, float(getattr(client, "spend_usd", prior_spend)))

    report = {
        "rejudge_only": True,
        "partial": partial,
        "rubric": "v2",
        "from_cache": str(from_cache),
        "cache_dir": str(args.cache_dir),
        "prior_out": str(args.prior_out) if args.prior_out else None,
        "model": args.model,
        "seed": args.seed,
        "n_questions": len(sampled),
        "rule_id_counts": rule_id_counts(v2, TOOLS),
        "label_changes_v1_v2_by_tool": label_changes_v1_v2_by_tool(v1, v2, TOOLS),
        "judge_errors": int(dry_judge.get("judge_errors") or 0),
        "spend_usd": round(float(getattr(client, "spend_usd", 0.0)), 6),
        "tools": summarize(
            sampled,
            extracts,
            retrievals,
            v2,
            seed=args.seed,
            model=args.model,
            spend_usd=float(getattr(client, "spend_usd", 0.0)),
            exclusion_counts={},
            chosen_ids=[question_id(r) for r in sampled],
            partial=partial,
        )["tools"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["label_changes_v1_v2_by_tool"], indent=2))
    print(f"wrote {args.out}")
    return report


def load_rubric_fixture_cases(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_calibrate(args: argparse.Namespace) -> dict:
    cases = load_rubric_fixture_cases(args.calibrate)
    for row in cases:
        if row.get("expected_label") not in VALID_LABELS:
            raise SystemExit(f"bad expected_label in {row.get('id')}")
        if row.get("rule") not in RULES_BY_LABEL[row["expected_label"]]:
            raise SystemExit(f"bad rule in {row.get('id')}")
    judge_system = judge_system_for_rubric("v2")
    client = OpenAIClient(
        max_usd=args.max_usd,
        ca_bundle=args.ca_bundle,
        price_in=args.price_in,
        price_out=args.price_out,
    )
    agree = 0
    agree_rule = 0
    rows_out: list[dict] = []
    for case in cases:
        # Same order as the real grader: empty and "I don't know" answers never reach the model.
        rule_row = rule_based_judge_row(case["answer"], None)
        system, user = judge_prompt(
            case["question"],
            case["gold"],
            case.get("alt_ans") or [],
            case["answer"],
            judge_system=judge_system,
            query_time=case.get("query_time"),
        )
        if rule_row is not None:
            label, reason, rule_id, cost = (
                rule_row["label"], rule_row["reason"], rule_row["rule_id"], 0.0
            )
        else:
            text, cost, _usage = client.chat(
                args.model,
                system,
                user,
                temperature=0.0,
                json_mode=True,
                max_completion_tokens=DEFAULT_MAX_COMPLETION_JUDGE,
                purpose="judge",
            )
            label, reason, rule_id = parse_judge_label_v2(text, require_rule_id=True)
        ok = label == case["expected_label"]
        agree += int(ok)
        agree_rule += int(ok and rule_id == case["rule"])
        rows_out.append(
            {
                "id": case.get("id"),
                "expected_label": case["expected_label"],
                "expected_rule": case["rule"],
                "label": label,
                "rule_id": rule_id,
                "reason": reason,
                "agree_label": ok,
                "cost_usd": round(cost, 6),
            }
        )
    report = {
        "calibrate": True,
        "n_cases": len(cases),
        "agreement": round(agree / len(cases), 4) if cases else None,
        "agreement_label_and_rule": round(agree_rule / len(cases), 4) if cases else None,
        "spend_usd": round(client.spend_usd, 6),
        "cases": rows_out,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"calibrate agreement={report['agreement']} n={len(cases)} spend=${report['spend_usd']}")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=None, help="crag_task_1_and_2_dev_v5.jsonl.bz2")
    p.add_argument("--cache-dir", type=Path, default=None, help="disk cache outside the repo")
    p.add_argument("--out", type=Path, default=None, help="output JSON path")
    p.add_argument("--n", type=int, default=50, help="sample size")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--limit", type=int, default=None, help="max split-0 records to load")
    p.add_argument("--split", type=int, default=0, help="0, or 1 with --locked-split-1")
    p.add_argument("--locked-split-1", action="store_true", help="The one protocol run on split 1")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--max-usd", type=float, default=5.0)
    p.add_argument("--price-in", type=float, default=0.20, help="USD per 1M input tokens")
    p.add_argument("--price-out", type=float, default=0.75, help="USD per 1M output tokens")
    p.add_argument("--ca-bundle", type=str, default=None, help="corporate proxy CA bundle")
    p.add_argument("--workers", type=int, default=4, help="concurrent LLM requests")
    p.add_argument("--extract-workers", type=int, default=4)
    p.add_argument("--page-timeout", type=float, default=60.0)
    p.add_argument(
        "--max-completion-tokens-generate",
        type=int,
        default=DEFAULT_MAX_COMPLETION_GENERATE,
        help="max_completion_tokens for generate (room for reasoning models)",
    )
    p.add_argument(
        "--max-completion-tokens-judge",
        type=int,
        default=DEFAULT_MAX_COMPLETION_JUDGE,
        help="max_completion_tokens for judge",
    )
    p.add_argument("--dry-run", action="store_true", help="print token/cost estimate; no LLM calls")
    p.add_argument(
        "--rejudge-only",
        action="store_true",
        help="re-grade cached answers with --rubric v2; read --from-cache, write --cache-dir",
    )
    p.add_argument(
        "--from-cache",
        type=Path,
        default=None,
        help="original eval cache (generate + v1 judge); read-only",
    )
    p.add_argument(
        "--prior-out",
        type=Path,
        default=None,
        help="prior crag_answer_eval.json for chosen_question_ids and v1 labels",
    )
    p.add_argument(
        "--rubric",
        choices=("v1", "v2"),
        default="v1",
        help="answer judge rubric (v2 for --rejudge-only)",
    )
    p.add_argument(
        "--calibrate",
        type=Path,
        default=None,
        help="run fixture jsonl through live v2 grader; reports agreement",
    )
    return p


def run(
    args: argparse.Namespace,
    *,
    client_factory: Callable[..., Any] | None = None,
) -> dict:
    if args.data is None or args.cache_dir is None or args.out is None:
        raise SystemExit("--data, --cache-dir, and --out are required for a full eval run")
    enforce_split(args.split, locked_run=getattr(args, "locked_split_1", False))
    verify_tools_importable(TOOLS)
    records = load_crag_records(args.data, split=args.split, limit=args.limit, locked_run=getattr(args, "locked_split_1", False))
    kept, exclusion_counts = filter_web_static(records)
    sampled = sample_questions(kept, args.n, args.seed)
    chosen_ids = [question_id(r) for r in sampled]

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    prior_spend = load_persisted_spend(args.cache_dir)
    extracts = run_extract(
        sampled,
        cache_dir=args.cache_dir,
        workers=args.extract_workers,
        page_timeout=args.page_timeout,
    )
    retrievals = run_retrieve(sampled, extracts, cache_dir=args.cache_dir)

    client = None
    spend = 0.0
    spend_this_run = 0.0
    partial = False
    generations: dict[str, dict[str, dict]] = defaultdict(dict)
    judgements: dict[str, dict[str, dict]] = defaultdict(dict)
    dry_gen: dict = {}
    dry_judge: dict = {}
    judge_errors = 0
    generate_errors = 0
    generate_error_messages: list[str] = []
    empty_answer = 0
    empty_answer_length = 0
    max_gen_tok = getattr(
        args, "max_completion_tokens_generate", DEFAULT_MAX_COMPLETION_GENERATE
    )
    max_judge_tok = getattr(args, "max_completion_tokens_judge", DEFAULT_MAX_COMPLETION_JUDGE)

    if args.dry_run:
        for rec in sampled:
            qid = question_id(rec)
            qt = rec.get("query_time")
            for tool in TOOLS:
                chunks = retrievals[qid][tool].get("chunks") or []
                system, _user = generate_prompt(rec["query"], chunks, query_time=qt)
                key = generate_cache_key(
                    query=rec["query"],
                    chunks=chunks,
                    tool=tool,
                    model=args.model,
                    prompt_system=system,
                    max_completion_tokens=max_gen_tok,
                    temperature=0.0,
                    query_time=qt,
                )
                hit = read_json_cache(cache_path(args.cache_dir, "generate", key[:2], f"{key}.json"))
                if hit is not None:
                    generations[qid][tool] = hit
        _, dry_gen = run_generate(
            sampled,
            retrievals,
            cache_dir=args.cache_dir,
            client=None,
            model=args.model,
            dry_run=True,
            price_in=args.price_in,
            price_out=args.price_out,
            max_completion_tokens=max_gen_tok,
        )
        for rec in sampled:
            qid = question_id(rec)
            for tool in TOOLS:
                generations.setdefault(qid, {}).setdefault(
                    tool, {"answer": f"__DRY_PLACEHOLDER_{tool}__"}
                )
        _, dry_judge = run_judge(
            sampled,
            generations,
            cache_dir=args.cache_dir,
            client=None,
            model=args.model,
            seed=args.seed,
            dry_run=True,
            price_in=args.price_in,
            price_out=args.price_out,
            max_completion_tokens=max_judge_tok,
            assume_no_tool_dedup=True,
        )
        report = {
            "dry_run": True,
            "model": args.model,
            "seed": args.seed,
            "git_commit": git_commit(),
            "chosen_question_ids": chosen_ids,
            "exclusion_counts": exclusion_counts,
            "prior_spend_usd": prior_spend,
            "token_estimate": {
                "generate": dry_gen,
                "judge": dry_judge,
                "total_est_usd": round(
                    dry_gen.get("est_usd", 0) + dry_judge.get("est_usd", 0), 6
                ),
            },
            "price_in": args.price_in,
            "price_out": args.price_out,
            "extractor_configs": {t: extractor_config_for_tool(t) for t in TOOLS},
            "url_input_note": (
                "ChromeRAG and trafilatura receive page_url; markitdown baselines do not."
            ),
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            f"dry-run: generate_calls={dry_gen['generate_calls']} "
            f"generate_calls_saved={dry_gen.get('generate_calls_saved', 0)} "
            f"judge_calls={dry_judge['judge_calls']} "
            f"est_prompt_tokens={dry_gen['est_prompt_tokens'] + dry_judge['est_prompt_tokens']} "
            f"est_completion_tokens={dry_gen['est_completion_tokens'] + dry_judge['est_completion_tokens']} "
            f"est_usd={report['token_estimate']['total_est_usd']}"
        )
        return report

    if prior_spend >= args.max_usd:
        raise BudgetExceeded(
            f"persisted spend ${prior_spend:.3f} already at/above cap ${args.max_usd:.2f}"
        )

    factory = client_factory or (
        lambda: OpenAIClient(
            max_usd=args.max_usd,
            ca_bundle=args.ca_bundle,
            price_in=args.price_in,
            price_out=args.price_out,
            starting_spend_usd=prior_spend,
        )
    )
    client = factory()
    # Ensure resumed spend is visible even for fake clients.
    if getattr(client, "spend_usd", 0.0) == 0.0 and prior_spend:
        client.spend_usd = prior_spend
    if not hasattr(client, "spend_this_run"):
        client.spend_this_run = 0.0
    try:
        try:
            generations, dry_gen = run_generate(
                sampled,
                retrievals,
                cache_dir=args.cache_dir,
                client=client,
                model=args.model,
                workers=args.workers,
                price_in=args.price_in,
                price_out=args.price_out,
                max_completion_tokens=max_gen_tok,
            )
            saved = int(dry_gen.get("generate_calls_saved") or 0)
            if saved:
                print(f"generate: deduped {saved} duplicate context(s)")
            judgements, dry_judge = run_judge(
                sampled,
                generations,
                cache_dir=args.cache_dir,
                client=client,
                model=args.model,
                seed=args.seed,
                workers=args.workers,
                price_in=args.price_in,
                price_out=args.price_out,
                max_completion_tokens=max_judge_tok,
            )
            judge_errors = int(dry_judge.get("judge_errors") or 0)
            generate_errors = int(dry_gen.get("generate_errors") or 0)
            generate_error_messages = list(dry_gen.get("generate_error_messages") or [])
            empty_answer = int(dry_judge.get("empty_answer") or 0)
            empty_answer_length = int(dry_judge.get("empty_answer_length") or 0)
        except BudgetExceeded as exc:
            print(f"Stopped on budget: {exc}")
            partial = True
            # Preserve mid-stage maps/counters that the failed assignment never bound.
            if getattr(exc, "stage", None) == "generate" or (
                getattr(exc, "dry_info", None) and "generate_calls" in (exc.dry_info or {})
            ):
                if exc.dry_info:
                    dry_gen = exc.dry_info
                for qid, tools_map in (exc.partial_out or {}).items():
                    for tool, row in tools_map.items():
                        generations[qid][tool] = row
            if getattr(exc, "stage", None) == "judge" or (
                getattr(exc, "dry_info", None) and "judge_calls" in (exc.dry_info or {})
            ):
                if exc.dry_info:
                    dry_judge = exc.dry_info
                for qid, tools_map in (exc.partial_out or {}).items():
                    for tool, row in tools_map.items():
                        judgements[qid][tool] = row
            generate_errors = int((dry_gen or {}).get("generate_errors") or 0)
            generate_error_messages = list((dry_gen or {}).get("generate_error_messages") or [])
            for rec in sampled:
                qid = question_id(rec)
                qt = rec.get("query_time")
                for tool in TOOLS:
                    chunks = retrievals[qid][tool].get("chunks") or []
                    system, _user = generate_prompt(rec["query"], chunks, query_time=qt)
                    gkey = generate_cache_key(
                        query=rec["query"],
                        chunks=chunks,
                        tool=tool,
                        model=args.model,
                        prompt_system=system,
                        max_completion_tokens=max_gen_tok,
                        temperature=0.0,
                        query_time=qt,
                    )
                    g = read_json_cache(
                        cache_path(args.cache_dir, "generate", gkey[:2], f"{gkey}.json")
                    )
                    if g is not None:
                        generations[qid][tool] = g
                    if qid in generations and tool in generations[qid]:
                        gen_row = generations[qid][tool]
                        answer = gen_row.get("answer") or ""
                        finish_reason = gen_row.get("finish_reason") or (
                            gen_row.get("usage") or {}
                        ).get("finish_reason")
                        # Load rule-label cache so IDK/empty answers stay in the intersection.
                        rule_path = cache_path(
                            args.cache_dir, "judge", "rule", qid, f"{tool}.json"
                        )
                        rule = read_json_cache(rule_path)
                        if (
                            rule is not None
                            and rule.get("input_hash")
                            == rule_label_input_hash(answer, finish_reason)
                        ):
                            judgements[qid][tool] = rule
                            continue
                        jkey = judge_cache_key_full(
                            query=rec["query"],
                            query_time=rec.get("query_time"),
                            gold=rec.get("answer") or "",
                            alt_ans=rec.get("alt_ans") or [],
                            answer=answer,
                            model=args.model,
                        )
                        j = read_json_cache(
                            cache_path(args.cache_dir, "judge", jkey[:2], f"{jkey}.json")
                        )
                        if j is not None:
                            judgements[qid][tool] = j
            # Fill remaining labels (incl. fresh IDK rule labels) on whatever gens we have.
            missing_labels = any(
                tool not in judgements.get(question_id(rec), {})
                for rec in sampled
                for tool in TOOLS
                if tool in generations.get(question_id(rec), {})
            )
            if generations and missing_labels:
                try:
                    judgements, dry_judge = run_judge(
                        sampled,
                        generations,
                        cache_dir=args.cache_dir,
                        client=client,
                        model=args.model,
                        seed=args.seed,
                        workers=args.workers,
                        price_in=args.price_in,
                        price_out=args.price_out,
                        max_completion_tokens=max_judge_tok,
                    )
                except BudgetExceeded as be:
                    if be.dry_info:
                        dry_judge = be.dry_info
                    for qid, tools_map in (be.partial_out or {}).items():
                        for tool, row in tools_map.items():
                            judgements[qid][tool] = row
                judge_errors = int((dry_judge or {}).get("judge_errors") or 0)
                empty_answer = int((dry_judge or {}).get("empty_answer") or 0)
                empty_answer_length = int((dry_judge or {}).get("empty_answer_length") or 0)
            else:
                judge_errors = int((dry_judge or {}).get("judge_errors") or 0)
                empty_answer = int((dry_judge or {}).get("empty_answer") or 0)
                empty_answer_length = int((dry_judge or {}).get("empty_answer_length") or 0)
    finally:
        spend = float(getattr(client, "spend_usd", 0.0))
        spend_this_run = float(
            getattr(client, "spend_this_run", max(0.0, spend - prior_spend))
        )
        save_persisted_spend(args.cache_dir, spend)

    labelled_ids, n_dropped = fully_labelled_question_ids(sampled, judgements, TOOLS)
    if n_dropped or judge_errors or generate_errors:
        partial = True

    report = summarize(
        sampled,
        extracts,
        retrievals,
        judgements,
        seed=args.seed,
        model=args.model,
        spend_usd=spend,
        spend_this_run=spend_this_run,
        spend_total=spend,
        exclusion_counts=exclusion_counts,
        chosen_ids=chosen_ids,
        partial=partial,
        judge_errors=judge_errors,
        generate_errors=generate_errors,
        generate_error_messages=generate_error_messages,
        empty_answer=empty_answer,
        empty_answer_length=empty_answer_length,
        temperature_dropped_generate=bool(
            getattr(client, "temperature_dropped_generate", False)
        ),
        temperature_dropped_judge=bool(getattr(client, "temperature_dropped_judge", False)),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({t: report["tools"][t] for t in TOOLS}, indent=2))
    print(
        f"spend this_run=${spend_this_run:.4f} total=${spend:.4f}; "
        f"scored={report['n_scored']} dropped={report['n_dropped_incomplete_labels']}; "
        f"wrote {args.out}"
    )
    return report


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    if args.calibrate:
        run_calibrate(args)
        return
    if args.rejudge_only:
        if args.from_cache is None:
            raise SystemExit("--rejudge-only requires --from-cache")
        run_rejudge_only(args)
        return
    run(args)


if __name__ == "__main__":
    main()
