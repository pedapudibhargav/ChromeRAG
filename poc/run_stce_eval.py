"""Mine site chrome from fixtures and re-run extraction with STCE + compare."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from poc.baselines import BASELINES, estimate_tokens, noise_keyword_hits
from chromerag import ChromeRAG, mine_site_chrome
from chromerag.config import PipelineConfig, Strictness
from chromerag.site_chrome import site_group_key

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs"


def _load_pages() -> list[tuple[str, str | None, str]]:
    rows = []
    for meta_path in sorted(RAW.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = RAW / f"{meta['id']}.html"
        if not html_path.exists():
            continue
        rows.append(
            (
                meta["id"],
                meta.get("url"),
                html_path.read_text(encoding="utf-8", errors="ignore"),
            )
        )
    return rows


def main() -> None:
    pages = _load_pages()
    print(f"Loaded {len(pages)} fixtures")

    # Mine per host (path_prefix_depth=0) so multi-page same-host fixtures share chrome
    mined = mine_site_chrome(
        [(url, html) for _, url, html in pages],
        min_pages=3,  # need ≥3 same-host pages before learning chrome
        frequency=0.80,
        max_block_chars=1800,
        require_chrome_features=True,
        path_prefix_depth=1,  # separate /docs from marketing hosts' path groups
    )
    for key, model in mined.items():
        print(
            f"STCE group={key:30s} pages={model.n_pages} "
            f"chrome_sigs={len(model.signatures)}"
        )
        for d in model.details[:5]:
            print(
                f"  freq={d.frequency:.2f} ld={d.avg_link_density:.2f} "
                f"chars={d.avg_chars:.0f} :: {d.sample_text[:70]}"
            )

    summary = []
    for page_id, url, html in pages:
        host = site_group_key(url, path_prefix_depth=1)
        model = mined.get(host)
        # Only apply if enough signatures learned
        use_model = model if model and model.signatures else None

        for strictness in (Strictness.BALANCED,):
            ext = ChromeRAG(
                config=PipelineConfig.from_strictness(strictness),
                site_chrome=use_model,
            )
            result = ext.extract(html, url=url)
            out_dir = OUT / page_id
            out_dir.mkdir(parents=True, exist_ok=True)
            suffix = "smart_rag_stce" if use_model else "chromerag"
            (out_dir / f"{suffix}.md").write_text(result.markdown, encoding="utf-8")
            # Also refresh default name for UI
            (out_dir / "chromerag.md").write_text(result.markdown, encoding="utf-8")

            row = {
                "id": page_id,
                "strictness": strictness.value,
                "tokens": result.tokens_estimate,
                "noise": sum(noise_keyword_hits(result.markdown).values()),
                "tables": result.n_tables,
                "json_ld": result.diagnostics.get("schema_sources", {}).get("json_ld_count", 0),
                "type": result.front_matter.get("type"),
                "stce_removed": result.diagnostics.get("stce_removed", 0),
                "stce_sigs": result.diagnostics.get("stce_signatures", 0),
                "title": (result.front_matter.get("title") or "")[:50],
            }
            summary.append(row)

            # Baselines refresh for key methods
            for name in ("trafilatura", "markitdown", "readability"):
                try:
                    text = BASELINES[name](html)
                    (out_dir / f"{name}.md").write_text(text, encoding="utf-8")
                except Exception as exc:  # noqa: BLE001
                    print(f"  baseline {name} fail: {exc}")

            print(
                f"{page_id:28s} tok={row['tokens']:6d} noise={row['noise']:2d} "
                f"jsonld={row['json_ld']} type={row['type']} "
                f"stce_rm={row['stce_removed']} title={row['title']!r}"
            )

    (OUT / "stce_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT / 'stce_run_summary.json'}")


if __name__ == "__main__":
    main()
