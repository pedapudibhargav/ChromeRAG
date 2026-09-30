"""Golden Markdown hashes for regression detection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LANDING_RAW = ROOT / "data" / "landing_raw"
MANIFEST = ROOT / "tests" / "golden" / "manifest.json"
FIXTURE_GOLDEN = ROOT / "tests" / "golden" / "fixtures"

MODES = {
    "chromerag_coverage": ContentPriority.COVERAGE,
    "chromerag": ContentPriority.BALANCED,
    "chromerag_precision": ContentPriority.PRECISION,
}


def _sorted_ids(raw_dir: Path, n: int) -> list[str]:
    ids: list[str] = []
    for meta_path in sorted(raw_dir.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        page_id = meta["id"]
        if (raw_dir / f"{page_id}.html").exists():
            ids.append(page_id)
        if len(ids) >= n:
            break
    return ids


def _hash_md(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract(mode: str, html: str) -> str:
    return ChromeRAG(
        config=PipelineConfig.from_priority(MODES[mode], enable_dvdf=True)
    ).extract(html).markdown


def _corpus_entries() -> list[dict]:
    entries: list[dict] = []
    for page_id in _sorted_ids(RAW, 150):
        entries.append({"id": page_id, "source": "raw", "path": str((RAW / f"{page_id}.html").relative_to(ROOT))})
    for page_id in _sorted_ids(LANDING_RAW, 150):
        entries.append(
            {
                "id": page_id,
                "source": "landing_raw",
                "path": str((LANDING_RAW / f"{page_id}.html").relative_to(ROOT)),
            }
        )
    return entries


def write_manifest() -> dict:
    manifest: dict = {"pages": []}
    for entry in _corpus_entries():
        html = (ROOT / entry["path"]).read_text(encoding="utf-8", errors="ignore")
        hashes = {mode: _hash_md(_extract(mode, html)) for mode in MODES}
        manifest["pages"].append({"id": entry["id"], "source": entry["source"], "hashes": hashes})
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def check_manifest() -> list[str]:
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Missing {MANIFEST}; run with --write first")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    changed: list[str] = []
    for entry in manifest["pages"]:
        path = ROOT / entry.get("path", f"data/{entry['source']}/{entry['id']}.html")
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        for mode, expected in entry["hashes"].items():
            actual = _hash_md(_extract(mode, html))
            if actual != expected:
                changed.append(f"{entry['id']}:{mode}")
    return changed


def write_fixture_golden(name: str, html: str) -> None:
    FIXTURE_GOLDEN.mkdir(parents=True, exist_ok=True)
    for mode in MODES:
        md = _extract(mode, html)
        (FIXTURE_GOLDEN / f"{name}_{mode}.md").write_text(md, encoding="utf-8")


def check_fixtures(fixtures_dir: Path) -> list[str]:
    changed: list[str] = []
    for fixture in sorted(fixtures_dir.glob("*.html")):
        html = fixture.read_text(encoding="utf-8")
        for mode in MODES:
            golden_path = FIXTURE_GOLDEN / f"{fixture.stem}_{mode}.md"
            if not golden_path.exists():
                changed.append(f"{fixture.stem}:{mode}:missing")
                continue
            actual = _extract(mode, html)
            expected = golden_path.read_text(encoding="utf-8")
            if actual != expected:
                changed.append(f"{fixture.stem}:{mode}")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        write_manifest()
        for fixture in sorted((ROOT / "tests" / "fixtures").glob("*.html")):
            write_fixture_golden(fixture.stem, fixture.read_text(encoding="utf-8"))
        print(f"Wrote {MANIFEST} and fixture golden files")
    elif args.check:
        changed = check_manifest() + check_fixtures(ROOT / "tests" / "fixtures")
        if changed:
            for item in changed:
                print(item)
            raise SystemExit(1)
        print("Golden check OK")
    else:
        parser.error("pass --write or --check")


if __name__ == "__main__":
    main()
