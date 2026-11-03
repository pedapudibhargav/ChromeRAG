# Blind rating handout

Plain steps for someone who did not build this project. You only rate text outputs against the original page. You do not need to know how the outputs were made.

## Install

You need Python 3.9 or newer. Nothing else needs installing. Unzip the folder you were sent and open a terminal inside it.

Mac or Linux: run `python3 --version`. Windows: run `python --version`. If it is missing, install Python from python.org first.

## Run

Pick any short rater name (letters, numbers or dashes, no spaces) and use the same one every time. It is replaced with a neutral code before anything is published:

```bash
python3 evaluators/run.py --rater YOUR-NAME
```

On Windows, use `python` instead of `python3`. The terminal prints a URL like `http://127.0.0.1:8770/`. Open it in Chrome, Edge or Firefox on the same computer. Leave the terminal open while you work. To stop, close the browser tab and press Ctrl+C in the terminal. To continue later, run the same command.

## What this is about

AI assistants, such as chatbots that answer questions about a company's documents or the web, do not look at web pages the way you do. A tool first turns each page into plain text. The assistant then cuts that text into short pieces, picks the few pieces that best match a person's question, and writes its answer only from those pieces. This is often called retrieval-augmented generation, or RAG. You do not need to know more than this.

You are judging that first step: the plain text made from each page. Several tools made text from the same page, and you decide which text would serve the assistant best.

- **Content** is what the page exists to give: its main text, facts, prices, dates, steps, tables, and on a forum page the question and its answers. If content is missing from the text, the assistant cannot answer questions about it.
- **Noise** is everything else: menus, footers, cookie and sign-up notices, share buttons, ads, and links or teasers for other pages. A little noise is harmless. A lot of it crowds out the real content, and noise about other things (another product's price, a teaser for a different article) can be repeated as if it were a fact from this page.

A good output keeps all the content and little noise. When outputs differ in both, weigh lost content against noise as you judge best for that page; there is no fixed rule. A longer or shorter text is not better for its length alone.

### A small example

A bakery page shows a menu bar, the opening hours (Mon–Fri 7–18, Sat 8–14), a price list (bread 4.50, croissant 2.20, cake slice 3.80), a "You may also like: Riverside Café, cakes from 2.90" box, and a footer.

| Output | What it contains | Content kept | Noise left in |
|---|---|---|---|
| 1 | Hours and the full price list | 5 | 5 |
| 2 | Hours, price list, and the menu bar and footer | 5 | 3 |
| 3 | Hours only; the price list is missing | 2 | 5 |
| 4 | Hours, price list, and the "You may also like" box | 5 | 1 |

Output 1 is best. Output 2 is close behind: its extra text is clearly not about the bakery. Output 3 looks clean but cannot answer "how much is a croissant?". Output 4 could make the assistant say cake costs 2.90, which is the other café's price, so its noise scores 1 even though it is short.

Each practice item shows a short note after you rate it, saying what a careful rater would notice on that page. Compare it with your own scores, then go on. The notes are only a guide; on the real items, judge for yourself.

## What to judge

Imagine a search assistant that can only read the extracted text. People ask questions this page should answer. Which labelled output (A, B, C, …) would give right answers most reliably?

For each item:

1. Read the original page (Rendered or Plain text). Pages are saved copies with images and links removed, and the app does not connect to any website. Judge the text. If the preview looks blank, use **Plain text**. Do not look the pages up online. Skim long pages; you do not need to read every word. Some pages are menus, lists or hubs: judge them by the same question as any other page. Banners, notices and contact details are part of the real page and say nothing about the study; whether they count as content or noise follows the definitions above.
2. Read every output.
3. Tick every output that is equally best, or choose **All about the same**, or **None are good**.
4. Score each output from 1 to 5 for **content kept** and **noise left in** (unless you Skip). The **Guide** button at the top shows what each score means. You may add a short note if something important is missing.
5. Practice items are marked and come first; they are not used in the final analysis.

Progress is saved after every rating. You can stop and resume with the same `--rater` name.

**Time estimate:** {N_ITEMS} items, about 2 to 4 minutes each, so about {HOURS} hours in total. Skim long pages. Split it into sessions; you do not need to finish in one sitting. A few pages appear twice on purpose. Rate each as you see it.

## How to return the JSON

When you finish, press Finish. It shows a results file under `evaluators/results/`. Email that one JSON file to the person who sent you this folder. Do not edit it.

## Rules

- Rate alone.
- Do not use AI tools to decide scores.
- Do not open project result write-ups before you finish.
- Do not discuss items with other raters until everyone has submitted.
