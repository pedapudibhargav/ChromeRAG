"""Mechanical page filter for evaluations/2026-11-final (no tool outputs).

Reads only HTML + meta under data/final. Writes evaluations/2026-11-final/page_filter.json.

Rules (applied to every ok page; no id hardcoding):
  (a) duplicate final URL — keep the lowest id, remove the rest
  (b) body is not HTML (e.g. JSON document / JSON-only payload)
  (c) non-English: many non-Latin letters, or another language's common words win

Login, template, and thin pages are kept unless they fail (a)–(c).
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

from poc.final_collect import normalize_url

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAGES = ROOT / "data" / "final"
DEFAULT_OUT = ROOT / "evaluations" / "2026-11-final" / "page_filter.json"

# Language is decided by comparison, not by a floor on English common words: English
# menus and product lists have few common words, so a floor removes them wrongly.
# A page is non-English when a large share of its letters are not Latin script, or when the
# common words of another language outnumber the English ones. The lists hold words
# that are frequent in that language and rare in English. No list is fitted to page ids.
ENGLISH_STOPWORDS = frozenset(
    "the of and to in a is that for it as with was on be by this are at from or an have not but "
    "they his her you we can all will their has more one if there been which when who would what "
    "about so out up your were than into them its our also only other some these may do how new".split()
)
OTHER_STOPWORDS = {
    "da": "og i er det en af til at de den for med som på ikke et har vi kan du om".split(),
    "de": "der die das und ist von den mit für auf nicht ein eine zu im dem sich auch werden wir".split(),
    "es": "el la los las de que y en del se por con para una un es lo como más pero sus".split(),
    "fi": "ja on ei että se oli ovat tai kun myös mutta sekä tämä jos kuin niin voi".split(),
    "fr": "le la les de des et est une un du pour dans que qui sur pas au avec nous vous".split(),
    "id": "yang dan di dengan untuk dari ini itu pada ke dalam tidak atau akan kami anda".split(),
    "it": "il la di che e per del della con le gli un una sono nella non più dei al".split(),
    "nl": "de het een van en is dat op te zijn voor met niet aan er om ook naar wij".split(),
    "no": "og i er det en av til at de som på ikke et har vi kan du for med".split(),
    "pl": "w i na z do nie jest się że to od po dla oraz przez jak".split(),
    "pt": "o a os as de que e em do da para com um uma não por mais dos das".split(),
    "sv": "och i är det en av till att de som på inte ett har vi kan du för med".split(),
    "tr": "ve bir bu için ile da de olarak daha çok en gibi kadar sonra".split(),
}
# Words shared with English say nothing about which language a page is in. Single letters
# (English "I", alphabet indexes) and "com" (web addresses) are not evidence either.
OTHER_STOPWORDS = {
    k: frozenset(w for w in v if len(w) > 1 and w != "com") - ENGLISH_STOPWORDS
    for k, v in OTHER_STOPWORDS.items()
}
# A quarter of letters outside Latin script means the page body is not English, even under
# an English menu. Set after viewing this share on the pages, with no tool output in view:
# English pages listing other languages stay under 0.07, foreign-language pages start at 0.42.
NON_LATIN_LETTER_SHARE_MIN = 0.25
# Need enough words for a stable comparison; thinner pages are kept (inconclusive).
MIN_WORDS_FOR_LANG = 40
# A language switcher ("Deutsch", "en", "de") can outnumber English on a terse list page,
# so another language needs real evidence: a body of text has far more than ten such words.
MIN_OTHER_STOPWORDS = 10
_WORD = re.compile(r"[^\W\d_]+")
_ADDRESS = re.compile(r"\S*(?:://|www\.|@)\S*|\S+\.(?:com|org|net)\b\S*", re.I)


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    return (soup.body or soup).get_text(" ", strip=True)


def _is_latin_letter(ch: str) -> bool:
    return "LATIN" in unicodedata.name(ch, "")


def language_signals(text: str) -> dict | None:
    """Counts behind the language decision; None when the page is too thin to judge."""
    words = [w.lower() for w in _WORD.findall(_ADDRESS.sub(" ", text or ""))]
    if len(words) < MIN_WORDS_FOR_LANG:
        return None
    letters = [ch for w in words for ch in w]
    non_latin = sum(1 for ch in letters if not _is_latin_letter(ch))
    english = sum(1 for w in words if w in ENGLISH_STOPWORDS)
    other = {k: sum(1 for w in words if w in v) for k, v in OTHER_STOPWORDS.items()}
    best = max(sorted(other), key=lambda k: other[k])
    return {
        "n_words": len(words),
        "non_latin_letter_share": round(non_latin / len(letters), 4),
        "english_stopwords": english,
        "best_other_language": best,
        "best_other_stopwords": other[best],
    }


def non_english_reason(signals: dict | None) -> str | None:
    if signals is None:
        return None
    if signals["non_latin_letter_share"] >= NON_LATIN_LETTER_SHARE_MIN:
        return "non_english_script"
    if (
        signals["best_other_stopwords"] >= MIN_OTHER_STOPWORDS
        and signals["best_other_stopwords"] > signals["english_stopwords"]
    ):
        return "non_english_stopwords"
    return None


def _try_json_payload(text: str) -> bool:
    s = (text or "").strip()
    if not s or s[0] not in "[{":
        return False
    try:
        json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return False
    return True


def is_non_html_body(raw: str) -> bool:
    """True when the fetched body is JSON (or HTML that only wraps a JSON payload)."""
    s = (raw or "").lstrip("\ufeff").strip()
    if _try_json_payload(s):
        return True
    # Common collector case: JSON stuffed into a lone textarea / pre.
    soup = BeautifulSoup(s, "lxml")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = (soup.body or soup).get_text("", strip=True)
    return _try_json_payload(text)


def load_ok_pages(pages_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for meta_path in sorted(pages_dir.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status") != "ok":
            continue
        pid = str(meta.get("id") or meta_path.name.replace(".meta.json", ""))
        html_path = pages_dir / f"{pid}.html"
        if not html_path.exists():
            continue
        rows.append(
            {
                "id": pid,
                "url": str(meta.get("url") or ""),
                "html_path": html_path,
                "meta": meta,
            }
        )
    return rows


def _id_sort_key(pid: str) -> tuple:
    m = re.search(r"(\d+)$", pid)
    if m:
        return (0, int(m.group(1)), pid)
    return (1, pid)


def filter_pages(pages_dir: Path) -> dict:
    pages = load_ok_pages(pages_dir)
    removed: list[dict] = []
    removed_ids: set[str] = set()

    # (b) non-HTML / JSON body
    for row in pages:
        raw = row["html_path"].read_text(encoding="utf-8", errors="replace")
        row["raw"] = raw
        if is_non_html_body(raw):
            removed.append({"id": row["id"], "reason": "non_html_json", "url": row["url"]})
            removed_ids.add(row["id"])

    # (c) non-English on visible text
    for row in pages:
        if row["id"] in removed_ids:
            continue
        signals = language_signals(visible_text(row["raw"]))
        reason = non_english_reason(signals)
        row["language_signals"] = signals
        if reason:
            removed.append({"id": row["id"], "reason": reason, "url": row["url"], **signals})
            removed_ids.add(row["id"])

    # (a) duplicate final URL — keep lowest id
    by_url: dict[str, list[str]] = defaultdict(list)
    for row in pages:
        if row["id"] in removed_ids:
            continue
        nu = normalize_url(row["url"]) if row["url"] else ""
        if not nu:
            continue
        by_url[nu].append(row["id"])
    for nu, ids in by_url.items():
        if len(ids) < 2:
            continue
        keep = sorted(ids, key=_id_sort_key)[0]
        for pid in ids:
            if pid == keep:
                continue
            removed.append(
                {
                    "id": pid,
                    "reason": "duplicate_final_url",
                    "url": nu,
                    "kept_id": keep,
                }
            )
            removed_ids.add(pid)

    removed.sort(key=lambda r: _id_sort_key(r["id"]))
    kept = sorted(
        (row["id"] for row in pages if row["id"] not in removed_ids),
        key=_id_sort_key,
    )
    by_reason: dict[str, int] = defaultdict(int)
    for r in removed:
        by_reason[str(r["reason"])] += 1
    try:
        pages_dir_label = str(pages_dir.resolve().relative_to(ROOT))
    except ValueError:
        pages_dir_label = "data/final"
    return {
        "pages_dir": pages_dir_label,
        "n_ok_input": len(pages),
        "n_kept": len(kept),
        "n_removed": len(removed),
        "rules": {
            "duplicate_final_url": "keep lowest id among normalize_url(meta.url)",
            "non_html_json": "body parses as JSON (raw or visible text)",
            "non_english_script": (
                f"visible words >= {MIN_WORDS_FOR_LANG} and share of letters outside "
                f"Latin script >= {NON_LATIN_LETTER_SHARE_MIN}"
            ),
            "non_english_stopwords": (
                f"visible words >= {MIN_WORDS_FOR_LANG} and another language's common "
                f"words number at least {MIN_OTHER_STOPWORDS} and outnumber the English ones"
            ),
        },
        "non_latin_letter_share_min": NON_LATIN_LETTER_SHARE_MIN,
        "min_words_for_lang": MIN_WORDS_FOR_LANG,
        "min_other_stopwords": MIN_OTHER_STOPWORDS,
        "removal_counts_by_reason": dict(by_reason),
        "removed": removed,
        "kept_ids": kept,
    }


def main(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pages-dir", type=Path, default=DEFAULT_PAGES)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    report = filter_pages(args.pages_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"removed {report['n_removed']} / {report['n_ok_input']} -> {args.out}")
    for row in report["removed"]:
        extra = ""
        if "n_words" in row:
            extra = (
                f" non_latin={row['non_latin_letter_share']} en={row['english_stopwords']}"
                f" {row['best_other_language']}={row['best_other_stopwords']}"
            )
        elif row.get("kept_id"):
            extra = f" kept={row['kept_id']}"
        print(f"  {row['id']}: {row['reason']}{extra}")
    return report


if __name__ == "__main__":
    main()
