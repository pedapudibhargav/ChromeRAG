# What “references”, APC, and “ready for EM” mean

## 1. References (what we just added)

**References** are the formal bibliography at the end of the paper: prior work you cite so reviewers can verify claims and see how ChromeRAG fits the literature.

A **DOI** (Digital Object Identifier) is a permanent link like `https://doi.org/10.…`. SoftareX / Elsevier prefer DOIs because they do not rot like random URLs.

We researched and added these citable items (with DOIs where they exist):

| # | Work | Why it belongs | DOI / link |
|---|------|----------------|------------|
| 1 | Barbaresi, Trafilatura (ACL 2021) | Main baseline for HTML main-content extraction | [10.18653/v1/2021.acl-demo.15](https://doi.org/10.18653/v1/2021.acl-demo.15) |
| 2 | Alarte et al., template extractors (TWEB 2019) | Classical site-template / chrome extraction literature | [10.1145/3316810](https://doi.org/10.1145/3316810) |
| 3 | Tan et al., HtmlRAG (WWW 2025) | Query-time HTML pruning for RAG — complementary to our *ingest-time* scope | [10.1145/3696410.3714546](https://doi.org/10.1145/3696410.3714546) |
| 4 | ChromeRAG v0.1.0 | SoftareX asks you to cite the software itself | https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0 |
| 5 | MarkItDown (Microsoft) | Multi-format Markdown converter baseline (no journal DOI; software URL is fine) | https://github.com/microsoft/markitdown |

These live in `SOFTWAREX_DRAFT.md` and should match the References section in `ChromeRAG_SoftwareX_OSP.docx` after you open/save (or we regenerate).

## 2. APC only after acceptance

**APC** = Article Publishing Charge (SoftareX open-access fee, ~USD 1,560 + tax).

| Stage | Pay? |
|-------|------|
| Create EM account / upload manuscript | **No** |
| Under review / revisions | **No** |
| Editor **accepts** the paper | **Yes** — Elsevier emails Rights & Access |
| If rejected | **$0** |

So “APC only after acceptance” means: submit for free; pay only if SoftareX accepts the paper.

## 3. “Tagged v0.1.0 and opened the docx once → ready for EM”

That sentence means two practical gates before you click Submit:

1. **`v0.1.0` tag exists on GitHub** (done: https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0)  
   SoftareX metadata C2 should point at that permanent snapshot. Tagging does **not** freeze `main` — you can keep committing; SoftareX reviews the tagged version. Later improvements can be a SoftareX **Software Update** or a new tag (`v0.1.1`, `v0.2.0`).

2. **Open `ChromeRAG_SoftwareX_OSP.docx` in Microsoft Word once**  
   Spell-check, confirm figures appear, confirm C1=`0.1.0` and C2=tag URL. Do **not** change SoftareX styles. Then upload that `.docx` in Editorial Manager as the manuscript.

Then in EM choose article type **Original Software Publication**, paste Highlights from `HIGHLIGHTS.md`, upload competing-interests `.docx`, and submit.

## 4. Screencast

Optional. SoftareX encourages a short demo video; it is not required for desk acceptance. See `SCREENCAST.md` for a 60–90s shot list. I cannot record your screen from here — you record with QuickTime / Cmd+Shift+5.
