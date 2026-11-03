# Blind rating handout

Plain steps for someone who did not build this project. You only rate text outputs against the original page. You do not need to know how the outputs were made.

## Install

You need Python 3.9 or newer. Nothing else needs installing. Unzip the folder you were sent and open a terminal inside it.

Mac or Linux: run `python3 --version`. Windows: run `python --version`. If it is missing, install Python from python.org first.

## Run

Use the rater id you were given, exactly as written:

```bash
python3 evaluators/run.py --rater YOUR_ID
```

On Windows, use `python` instead of `python3`. The terminal prints a URL like `http://127.0.0.1:8770/`. Open it in Chrome, Edge or Firefox on the same computer. Leave the terminal open while you work. To stop, close the browser tab and press Ctrl+C in the terminal. To continue later, run the same command.

## What to judge

Imagine a search assistant that can only read the extracted text. People ask questions this page should answer. Which labelled output (A, B, C, …) would give right answers most reliably?

For each item:

1. Read the original page (Rendered or Plain text). Pages are saved copies with images and links removed, and the app does not connect to any website. Judge the text. If the preview looks blank, use **Plain text**. Do not look the pages up online. Skim long pages; you do not need to read every word.
2. Read every output.
3. Tick every output that is equally best, or choose **All about the same**, or **None are good**.
4. Score each output from 1 to 5 for **content kept** and **noise left in** (unless you Skip). You may add a short note if something important is missing.
5. Practice items are marked and come first; they are not used in the final analysis.

Progress is saved after every rating. You can stop and resume with the same `--rater` id.

**Time estimate:** 85 items, about 2 to 4 minutes each, so about 3 to 6 hours in total. Skim long pages. Split it into sessions; you do not need to finish in one sitting. A few pages appear twice on purpose. Rate each as you see it.

## How to return the JSON

When you finish, press Finish. It shows a results file under `evaluators/results/`. Email that one JSON file to the person who sent you this folder. Do not edit it.

## Rules

- Rate alone.
- Do not use AI tools to decide scores.
- Do not open project result write-ups before you finish.
- Do not discuss items with other raters until everyone has submitted.
