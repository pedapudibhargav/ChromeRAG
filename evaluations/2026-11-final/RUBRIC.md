# Evaluation rubrics (2026-11 final)

Decision rules for the CRAG answer grader (v2) and the blind pairwise page judges. The two prompt blocks below are the normative text; everything else explains them. Fixtures: `tests/fixtures/crag_rubric_cases.jsonl`, where each case's `why` field names the step that decides it.

## Answer grader (v2)

### Relation to CRAG

From memory of the CRAG paper (Yang et al., 2024); wording not rechecked against the source:

- **Perfect**: answers correctly, no hallucinated content. **Acceptable**: useful, with minor errors that do not harm usefulness. **Missing**: "I don't know", "can't find", a system error or empty response, or a request to clarify. **Incorrect**: wrong or irrelevant information.
- Auto-eval uses accurate / missing / incorrect. As recalled, perfect and acceptable both collapse into accurate. This is the least certain point.

Departures, to be disclosed:

- There is no "minor errors" allowance, because two graders cannot agree on "minor". Partial lists and extra list members are **incorrect**, so this rubric is stricter than CRAG acceptable.
- Omitted and added list members are treated alike. Accepting additions while rejecting omissions would favor the extractor that passes more text to the generator.
- The grader does not see the retrieved context and may not use world knowledge, so hallucinated detail that gold does not address cannot be detected and is ignored. The rubric measures the asked-for facts, not freedom from hallucination.
- Irrelevant text with no abstention is incorrect (as in CRAG), not missing.

The sampler already excludes false-premise questions, fast-changing and real-time questions, and gold "invalid question". The pipeline labels exact "I don't know" and empty answers as missing without a model call; the prompt gives the same result.

### Rule ids

Steps run in order, and the first that applies decides. `R-ALT` and `R-NAME` only ever explain an accurate label. Labels are the measured output; `rule_id` is for audit.

<!-- ANSWER_JUDGE_PROMPT_V2 -->
```prompt
You grade one answer from a retrieval system against a gold answer for the CRAG benchmark.
Input: Question, optional Query time, Gold answer, Alt answers, Generated answer. You do not see the retrieved context.

EVIDENCE
Gold and alts are correct by definition, even if you recall otherwise. Do not use the current date. Use general knowledge only for arithmetic and to decide whether two expressions mean the same thing (aliases, abbreviations, translations, units, formats). Never judge whether a claim is true in the world or supported by context.

TERMS
Reference: the gold or the one alt the answer fits best. Grade against that one only; never combine items from different references.
Required items: only the parts of the reference that answer what the question asks; other reference detail is not required. Yes/no question: the yes or no. Why/how question: the reason or method. If the question asks for N items and the reference lists more, any N.
Open list: the reference says "such as", "including", "for example", "etc." or "among others". One listed item is required (or N if asked), and other items in the answer are extra detail. Any other list is closed and complete. Order does not matter unless asked.
Committed value: what the answer asserts as its answer. A hedge ("probably", "about", "I think") still commits. "I don't know" next to a value is ignored. A statement that settles a yes/no question commits to yes or no. A value mentioned only as rejected or considered is not committed.
Extra detail: any claim that is neither a further answer to the question nor a different value for something the reference states. Ignore it, including explanations you believe are wrong.

MATCH TESTS
Number: convert to the reference's unit (never between currencies), round to the last digit written in the reference ("3.14": hundredths; "5 million": millions; "100": units), then compare. Less precise answers fail. A bound ("over 40") or range matches only the same bound or range. Number words equal digits; a list of N items states a count of N. "About" in the reference changes nothing.
Date: same date after formatting; accept either reading of an ambiguous numeric date. A date inside the reference's period matches ("March 1, 2020" for "March 2020"); a wider one fails. Resolve relative dates with Query time; with no Query time they fail. Ignore weekdays unless the reference states one.
Name: same entity through alias, abbreviation, transliteration or surname alone. A qualifier that only locates the entity may be dropped or added unless the question asks for it ("Paris" for "Paris, France" unless the country is asked). A broader answer fails ("France"). A narrower one matches only if it contains the reference's words ("San Francisco, California" for "California"). A different entity sharing part of the name fails. If unsure, it fails.

STEPS: apply in order and stop at the first that applies.
1. R-MISS, missing: no committed value for any required item, and the answer is empty, says it does not know, cannot find or lacks the information, is a system error, or asks for clarification. Side remarks do not change this. "None" is a value; bare or stated "unknown" is abstention unless the reference says unknown.
2. R-CONTRA, incorrect: asserts incompatible values for one item, including self-corrections. Values labelled with different times are not incompatible.
3. R-HEDGE, incorrect: offers different values for one item without choosing ("A or B", "A, though some say B", "yes and no", "it depends"), unless the reference offers the same choice.
4. R-TIME, incorrect: the value for a required item differs from the reference and the answer presents it as from another time ("today", "in 2015"). A value so labelled alongside the reference's value is extra detail.
5. R-NUM, incorrect: a required number fails the number test.
6. R-DATE, incorrect: a required date fails the date test.
7. R-WRONG, incorrect: any of these: a required value fails to match; a further member beyond a closed list; a further answer to a single-answer question; a different value for anything the reference states, required or not; a denied premise with no required item; or text that neither answers nor abstains.
8. R-PART, incorrect: a list question with some but not all required members, even with "I don't know". Never missing.
9. R-MULTI, incorrect: a question with distinct parts where a required part has no committed value.
10. Accurate: every required item matches. rule_id is the first that applies: R-HEDGE (hedged value), R-ALT (fits only an alt), R-NUM (needed a number test beyond identical text), R-DATE (same, for dates), R-NAME (needed the name test), otherwise R-REQ.

Reply with JSON only:
{"label":"accurate"|"missing"|"incorrect","rule_id":"R-REQ","reason":"one short sentence"}
```
<!-- END_ANSWER_JUDGE_PROMPT_V2 -->

## Pairwise page quality (blind A / B / tie)

Task (same as human raters): *Imagine a search assistant that can only read this text. People ask questions this page should answer. Which output would give right answers most reliably?*

Judges see the page's visible text and two extractions labelled **A** and **B** only (tool names hidden). Page text and each extraction get the same budget of 24,000 characters; a longer extraction shows its first 18,000 and last 6,000. That budget shows both extractions in full for about 98% of the primary pairs. Facts hidden by clipping cannot be counted as lost, which would favor a long extraction, so every result is also reported on the pairs where neither extraction was clipped. The content and noise anchors match the human scale, and both use 5 as best.

**Primary verdict.** The judge's own choice of "better", with no fixed trade-off between lost content and leftover chrome, as for human raters. This keeps the judge neutral: the tool's author prefers higher recall, and a fixed order favoring recall would favor the author's tool.

**Sensitivity verdict.** Computed afterwards from the same content and chrome scores, with no further model calls, and reported beside the primary, always labelled as such:
1. Treat content 5 and 4 as equal. Treat chrome 5, 4 and 3 as equal.
2. If content is equal, the higher chrome wins; if chrome is also equal, tie.
3. If content differs, the higher content wins, unless it has chrome 1 while the other has chrome 2 or more and content 3 or more; then the other wins.

<!-- PAGE_JUDGE_PROMPT -->
```prompt
You evaluate HTML-to-text extraction for retrieval-augmented generation (RAG).
You get the start of a web page's visible text and two extractions labelled A and B only.
Task: imagine a search assistant that reads only the extraction. Which would give right answers most reliably to questions this page should answer?

Useful content: the facts the page exists to give (body text, prices, steps, tables). Chrome: everything else, such as navigation, footers, consent banners, newsletters, social blocks, legal boilerplate, related items, other products, and comments unless they are what the page is for.

What you can see: PAGE TEXT may be cut off, and "[...]" in an extraction marks text hidden by this evaluation, not lost text. Count a fact as lost only if it appears in PAGE TEXT, is absent from the extraction, and the extraction has no "[...]" that could hide it. Do not penalize text just because it lies beyond the cut-off PAGE TEXT. Estimate chrome shares from the text you can see.

content (pick the lowest that applies):
5 nothing useful lost
4 small loss nobody would ask about (caption, byline, decorative line)
3 one useful fact lost (price, table row, step, short paragraph)
2 a main section, most of a table, or several separate useful facts lost
1 most content lost, or text from the wrong page

chrome (5 is cleanest; pick the lowest that applies):
5 none
4 harmless: a few lines, under about 5% of the text (breadcrumb, share label)
3 tolerable: short blocks, about 5 to 15%, that could not be mistaken for page content (footer, short menu)
2 disruptive: about 15 to 40%, or long link lists that bury the content
1 misleading or overwhelming: over about 40%, or text about other things that could produce a wrong answer (other products' prices, related articles, comments read as facts)

Verdict: choose the extraction that would give right answers most reliably, weighing lost content and chrome as you judge best for this page. Answer tie if neither is clearly better. Length alone never decides.

Answer with JSON only:
{"better":"A"|"B"|"tie",
 "content_A":1-5,"content_B":1-5,
 "chrome_A":1-5,"chrome_B":1-5,
 "reason":"one short sentence"}
```
<!-- END_PAGE_JUDGE_PROMPT -->
