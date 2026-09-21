# Screencast (optional but recommended)

SoftwareX encourages a short **video** demonstrating the software. It is **not** a desk-reject requirement, but reviewers like seeing install → extract → result in under 90 seconds.

## What to record (60–90s)

1. **0–10s** — Terminal: `git clone` / `pip install -e .` (or open already-cloned repo).
2. **10–35s** — `chromerag extract` on a docs HTML fixture; show Markdown output briefly.
3. **35–55s** — Show a JS-shell warning (`WARNING: … Playwright`) so honesty is visible.
4. **55–80s** — Open https://pedapudibhargav.github.io/ChromeRAG/results.html and point at the leaderboard.
5. **80–90s** — End on GitHub `v0.1.0` tag URL.

## How to capture (macOS)

```bash
# QuickTime Player → File → New Screen Recording
# Or: Cmd+Shift+5 → Record Selected Portion
```

Upload to YouTube/Vimeo (unlisted is fine) and add the URL to the README “Publishing” section and to EM as supplementary media if the form offers a video field.

## Script (speak or on-screen text)

> ChromeRAG converts HTML to RAG-ready Markdown by removing site chrome.  
> Install from GitHub, extract a page, and compare tools on the public leaderboard.  
> Empty JavaScript shells warn you to render first — we do not silently average those failures.
