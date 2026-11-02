# Blind rating handout

Plain steps for someone who did not build this project. You only rate text outputs against the original page. You do not need to know how the outputs were made.

## Install

You need Python 3.9 or newer. No packages to install for the rating app.

1. Get a copy of this repository.
2. Put the private file `bundle.json` you were sent here:

   ```text
   evaluators/bundle/bundle.json
   ```

   Create the `evaluators/bundle/` folder if it is missing.

## Run

From the repository root:

```bash
python evaluators/run.py --rater YOUR_ID
```

Use a short id such as your initials (no email or real name). The terminal prints a URL like `http://127.0.0.1:8770/`. Open that URL in your browser on the same computer.

To try the practice set first (no private bundle needed):

```bash
python evaluators/run.py --rater test --demo
```

## What to judge

Imagine a search assistant that can only read the extracted text. People ask questions this page should answer. Which labelled output (A, B, C, …) would give right answers most reliably?

For each item:

1. Read the original page (Rendered or Plain text). If the preview looks blank, use **Open saved page in new tab**. Prefer the saved copy over the live site.
2. Read every output.
3. Tick every output that is equally best, or choose **All about the same**, or **None are good**.
4. Score each output from 1 to 5 for **content kept** and **noise left in** (unless you Skip). You may add a short note if something important is missing.
5. Practice items are marked and come first; they are not used in the final analysis.

Progress is saved after every rating. You can stop and resume with the same `--rater` id.

**Time estimate:** about _N_ minutes for this bundle (the author fills in _N_ when they send the file).

## How to return the JSON

When you finish, the Finish screen shows a results file under `evaluators/results/`. Email that JSON file to the person who sent you the bundle. Do not edit it.

## Rules

- Rate alone.
- Do not use AI tools to decide scores.
- Do not open project result write-ups before you finish.
- Do not discuss items with other raters until everyone has submitted.
