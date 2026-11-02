# Blind rating kit

This is a small local app for rating text extractions from web pages **without seeing which tool produced each output**. You compare a few labelled outputs (A, B, C, …) next to the original page and pick which ones would be better for a search index.

You do not need to install anything beyond Python 3.9+. The app uses only the Python standard library, stores ratings as a plain JSON file on your machine, and listens only on `127.0.0.1` (your computer).

---

## 3-step start

1. **Get the private bundle**  
   The author will send you a file named `bundle.json`. Put it here (create the folder if needed):

   ```text
   evaluators/bundle/bundle.json
   ```

2. **Start the app** (from the repository root), choosing any short rater id (for example your initials). No personal data:

   ```bash
   python evaluators/run.py --rater YOUR_ID
   ```

   The terminal prints a URL like `http://127.0.0.1:8770/`. Open that URL in your browser.

3. **When finished**, the Finish screen shows the path of your results file (under `evaluators/results/`). Email that file to the author.

**Practice without a private bundle:**

```bash
python evaluators/run.py --rater test --demo
```

### For a coding assistant

```text
Work in this repository. Put the author’s bundle.json at evaluators/bundle/bundle.json
(unless using --demo). Start with:
  python evaluators/run.py --rater <id>
Print the URL from the terminal and open it locally. Do not install packages.
Do not open evaluations/, papers/, or project result write-ups before the rater finishes.
Results are written to evaluators/results/<rater>_<bundle_id>.json.
```

---

## How to rate

**The question (always visible in the app):** imagine a search assistant that can only read this text. People ask questions this page should answer. Which output would give right answers most reliably?

| Score | Content kept | Noise left in |
|---|---|---|
| 5 | Everything useful is there | None |
| 4 | Small loss nobody would ask about: caption, byline, decorative line | Harmless, under about 5% of the text: breadcrumb, share label |
| 3 | One useful fact gone: price, table row, step, short paragraph | Tolerable, about 5 to 15%: footer, short menu, cannot be mistaken for content |
| 2 | Main section or most of a table gone | Disruptive, about 15 to 40%, or long link lists bury the content |
| 1 | Most content gone, or text from the wrong page | Over about 40%, or text about other things that could give a wrong answer: other products' prices, related articles, comments read as facts |

Noise is acceptable if it would not change an answer: levels 3 to 5. The percentages are rough guides, so do not count words.

For each item:

- Read the original page (Rendered or Plain text tab).
- Read every output.
- If the original page looks blank or broken, use **Open saved page in new tab**. Pages are saved copies; images and links are removed, and the app connects to no website.
- Tick **every** output that is equally best (multi-select). If two are nearly the same and both best, tick both.
- Or choose **All about the same**, or **None are good**.
- Score each output 1–5 for **content kept** and **noise left in** (required unless you Skip). You can add an optional note if something important is missing.
- Practice items are marked and come first; they are not used in analysis.
- You can go back; progress is saved after every click.

**Keyboard:** number keys toggle best for output 1…n; ← / → move between items.

**Time estimate:** about _N_ minutes for this bundle (the author will fill in _N_ when they send the file).

---

## How to send results

Email the JSON file shown on the Finish screen (also under `evaluators/results/`) to the author. Do not edit the file.

### Results file shape (for authors)

```json
{
  "schema_version": 1,
  "bundle_id": "...",
  "rater": "...",
  "app_version": "1.0.0",
  "started": "ISO-8601",
  "updated": "ISO-8601",
  "items": {
    "item_id": {
      "item_id": "...",
      "best": ["A", "B"],
      "all_same": false,
      "none_good": false,
      "scores": {"A": {"content": 4, "chrome": 5, "missing": ""}},
      "skipped": false,
      "skip_reason": "",
      "seconds_spent": 12.5,
      "shown_order": ["B", "A", "C"]
    }
  }
}
```

---

## Rules

- Rate alone.
- Do **not** use AI tools to rate.
- Do **not** open `evaluations/`, `papers/`, or the project README results before you finish.
- Do **not** discuss items or answers with other raters until everyone has submitted.

## Privacy

No personal data is collected. The only identifier is the rater id you choose on the command line. Ratings never leave your machine unless you email the results file.

In results, the `chrome` field is the noise score (5 = no noise).
