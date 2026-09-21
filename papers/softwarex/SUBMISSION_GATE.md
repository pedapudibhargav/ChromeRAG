# SoftareX pre-submission gate (ChromeRAG)

Against Elsevier SoftareX Guide for Authors (Original Software Publication).

## Desk-rejection killers (must be green)

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Official SoftareX **Word or LaTeX template**, styles unaltered | **DONE** — `papers/softwarex/ChromeRAG_SoftwareX_OSP.docx` |
| 2 | Article type: **Original Software Publication** in Editorial Manager | **YOU** at submit |
| 3 | Public **GitHub** (not GitLab) with working code | **DONE** — https://github.com/pedapudibhargav/ChromeRAG |
| 4 | `README.md` + license file (`LICENSE` / `Licence.txt`) | **DONE** |
| 5 | Five sections: Motivation, Software description, Illustrative examples, Impact, Conclusions | **DONE** in docx |
| 6 | Code metadata table C1–C8 filled | **DONE** |
| 7 | ≤4000 words (abs+body+captions); ≤6 figures | **OK** (~1.5k words; 4 figs **embedded**) |
| 8 | Figures **embedded in the .docx** (Word path) | **DONE** |
| 9 | AI declaration + competing interests + funding | **DONE** in draft/docx |
| 10 | Permanent C2 URL — prefer **release tag** | **PENDING** — create `v0.1.0` |

## Strongly recommended (peer-review strength)

| Item | Why | Status |
|------|-----|--------|
| Docs / Compare Lab live | Reuse evidence | **DONE** — https://pedapudibhargav.github.io/ChromeRAG/ |
| Honest limitations (JS shells, scoreable gate) | Trust | **DONE** |
| Highlights (3–5 × ≤85 chars) | EM form | **DONE** in `SOFTWAREX_DRAFT.md` |
| CRediT author statement | Required for corresponding authors | **DONE** in draft — confirm in EM |
| Short screencast (60–90s) | SoftareX encourages video | **PENDING** |
| Spell-check the .docx in Word | Guide advice | **YOU** open & skim once |
| Expand references (DOIs where possible) | Completeness | **PENDING** light polish |

## Do **not** claim at submission

- SOTA on unrendered JS shells
- Human-gold span labels (we use structural anchors)
- PyPI package as primary install (install from GitHub)

## Submit path

1. Tag `v0.1.0` and put that URL in C2 if not already the repo root.
2. Open `ChromeRAG_SoftwareX_OSP.docx` in Word → save (no style edits).
3. Editorial Manager → **Original Software Publication**.
4. Upload competing-interests Word from Elsevier declarations tool.
5. Paste Highlights into EM.
6. APC only **after acceptance**.
