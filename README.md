# AI Earnings Call Analyst

Reads an earnings call transcript and pulls out what an equity analyst looks for first:

- **Forward guidance**: every forward-looking statement with a number in it, tagged as raised, lowered or held
- **Risks management raised**, grouped into areas like macro/demand, supply chain, pricing/margins, costs/inflation, FX and regulation
- **Tone**: finance-specific sentiment (Loughran-McDonald style word lists) for the prepared remarks vs. the Q&A, plus how much management hedges ("may", "could", "approximately")
- **What analysts pushed on**: the topics analysts asked about in the Q&A
- **Quarter over quarter**: tone change, guidance changes, and risk areas that appeared or disappeared

It outputs a text summary, JSON, or a one-page HTML dashboard.

## Run it

```bash
python cli.py samples/northwind_q3_2026.txt --compare samples/northwind_q2_2026.txt --html report.html
python cli.py samples/northwind_q3_2026.txt --json
python -m pytest -q      # 13 tests
```

**AI mode (optional):** `pip install anthropic`, set `ANTHROPIC_API_KEY`, add `--ai`, and Claude writes the summary and lists analyst concerns as structured JSON. Without a key it falls back to the offline rule-based mode automatically.

The samples are a **fictional company** (Northwind Outdoor Co.) written for this demo, so the repo doesn't copy anyone's real transcript. Any public transcript in the same `Speaker: text` format works.

## What broke and how I fixed it

- **Analyst questions counted as guidance.** "You raised guidance. What could take you below the range?" was being tagged as the company raising guidance. Now only management's lines count toward guidance, risks and tone, and analyst questions go into their own "what analysts pushed on" section.
- **General-purpose sentiment misreads finance.** Words like "liability" and "tax" are normal in finance, not bad news, so I used finance-specific word lists and added a test that they stay neutral.
- **A risk slipped through.** "Wage inflation is a cost we are watching" wasn't flagged because the sentence had no obvious risk word. I widened the triggers and added a test.

## Files

| File | What it does |
|---|---|
| `analyst.py` | Parsing, guidance/risk/number extraction, sentiment, quarter comparison, optional Claude call |
| `report.py` | HTML dashboard |
| `cli.py` | Command line |
| `test_analyst.py` | 13 pytest tests |
| `samples/` | Two quarters of a fictional company's calls |

Built with AI help (Claude) for writing and debugging the code.
