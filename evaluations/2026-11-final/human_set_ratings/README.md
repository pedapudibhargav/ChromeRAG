# Human ratings of the 2026-11 rating set (pseudonymized)

Five volunteer raters returned these files from the offline rating app (`evaluators/`, version 1.1.0). Two rated the full set (85 items) and three rated one part each (34 to 36 items). After 5 skipped ratings, 67 main pages have three ratings and 3 have two; the 5 anchor pages, in every part, have four or five. (An earlier version of this file said that every main page has three raters.)

Each rater chose a rater name in the app. Before publication every name was replaced with a neutral code (`rater-01` to `rater-05`) in a random order, as the protocol requires (`../PROTOCOL.md`, amendment "smaller parts and rater-chosen names"). The map back to people is kept privately. The study note in each rating package stated that ratings would be published under a neutral code, and each rater confirmed by email that they agreed to take part and to be named in the acknowledgments; each confirmation was recorded after that rater had finished rating. The names in the acknowledgments are listed alphabetically by surname and do not follow these codes.

Fields: `bundle_id` (full set or part), `app_version` and `items`. Start and end times were removed to keep the published data minimal. Each item holds the labels judged best (`best`), the `all_same` and `none_good` flags, 1 to 5 scores for content and chrome per label, `skipped`, `seconds_spent` (time the item was open, including idle time) and `shown_order`. Labels A, B and C are blind. The label key `label_key.json` maps them to tools for each item (`key`), maps each item to its page in `../human_set/corpus_pages.json` (`page_of`) and each repeat to its original (`repeat_of`), and lists the page types, the practice items (`calibration`), the anchor items rated by everyone (`anchors`) and the length in characters of each output as shown to raters (`output_chars`). It holds item ids and numbers only, no page or output text.

The analysis fixed in advance (`../PROTOCOL.md`, committed before any rating) runs from these files alone (results.json and results.md in the output folder):

```bash
PYTHONPATH=src:. python -m poc.human_set_analysis --out out/human_set
PYTHONPATH=src:. python -m poc.human_set_score_diff > out/human_set/score_diff_output.txt
PYTHONPATH=src:. python -m poc.human_set_ai_by_forum --out out/human_set/ai_by_forum.json
```

`poc/gen_supplement.py` turns these outputs and the committed result files into `../SUPPLEMENT.md`.

Practice items (5) and repeats are in the files; the analysis leaves practice items out and uses repeats only for the repeat-consistency check.

`bundle_seed.txt` is the private bundle seed used to shuffle items and A/B/C labels (`evaluators/author/build_bundle.py`). It was kept private until rating ended, as the protocol requires; its SHA-256 begins `118aabe6`.
