# Blind rating app

Rate 40 held-out WCXB test pages: original page (rendered or source) next to four extractor outputs, labelled A-D
in a random order per page. Tool names stay on the server until you export.

```bash
python -m poc.human_eval_build     # builds data/human_eval/ (git-ignored): 40 pages, seeded, stratified by page type
python -m apps.rating.server       # open http://localhost:8770 ; ratings in data/human_eval/ratings.sqlite
python -m poc.human_eval_analyze human_ratings.csv   # after "Finish & export"
```

Keys: 1-4 pick the best output, 0 = none/tie, arrows navigate. Score each output for content kept and chrome left
out (1-5). Progress is saved after every click and you can resume. No dependencies beyond the repo's Python.
