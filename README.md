# Are Federal Public Comments Being Written by AI?

The first large-scale audit of LLM-generated text in U.S. federal rulemaking
comments. When a federal agency proposes a rule, the public can comment, and the
agency is **legally required to consider those comments**. This project measures
how much of that input is now machine-generated — and whether it surged after
ChatGPT.

## Why this matters

Public comments shape the regulations everyone lives under. A pre-LLM precedent
(millions of fabricated net-neutrality comments) already showed the channel is
gameable. LLMs make astroturfing trivial and fluent. Yet while AI-text detectors
have been run on scientific papers, news, and court filings, the **public-comment
stream has not been systematically audited**. This fills that gap.

## Method

Detector (`detector.py`): scores text by density of the vocabulary that became
sharply over-represented in human writing only **after** ChatGPT (the
"delve/underscore/multifaceted" register) — the same excess-word approach used
by published paper-corpus studies.

Calibration (`analyze.py`): comments posted before Nov 2022 are **guaranteed
human** (no LLMs existed). We set the suspicion threshold from that human
distribution, fixing the human false-positive rate by construction, then measure
how the suspect rate rises post-ChatGPT via a difference-in-difference with a
two-proportion z-test and Wilson intervals.

## Validated instrument (plant-and-recover)

`validate_detector.py` builds corpora with a **known** AI fraction and confirms
the pipeline recovers it before it touches live data:

| planted AI % | recovered | z |
|---|---|---|
| 0% | 0% | 0.0 |
| 5% | 6% | 3.4 |
| 10% | 10% | 4.6 |
| 20% | 24% | 7.3 |
| 40% | 39% | 9.8 |

Recovered ≈ planted; zero planted gives zero signal. The instrument has power.

## Run it on live federal data

1. Get a free API key (instant, 1,000 req/hr): https://open.gsa.gov/api/regulationsgov/
   (sign up at https://api.data.gov/signup/).
2. `export REGS_API_KEY=your_key`
3. `python3 fetch.py <topic> <N>` → pulls pre/post-ChatGPT comment samples.
4. `python3 analyze.py` → the AI-contamination rate shift with significance.

Files: `detector.py` (scorer) · `fetch.py` (regulations.gov client) ·
`analyze.py` (temporal difference-in-difference) · `validate_detector.py`
(instrument-power proof).

## Responsible use

Error/registers are measured in **aggregate** for public awareness. An
LLM-register comment is not proof of misconduct by any individual; the finding
of interest is the *rate and its trend*, and coordinated/mass AI submission as a
mechanism. We do not accuse individuals.

## Pilot result (real federal data, 2026-11-02)

First run on 1,355 unique real comments (274 dockets, 1996–2024, form-letter
deduped; data: ro-h/regulatory_comments). Calibrating on 1,290 guaranteed-human
pre-2023 comments (suspect threshold = 90th pctile → 10.1% human rate by
design): **post-ChatGPT suspect rate = 19.0% (12/63), +9.0pp, permutation
p = 0.0245**. A tie-corrected Mann-Whitney on the full rate distribution is
null (z = +0.76) — the shift is in the suspicious tail, not the bulk, which is
the expected signature of partial AI contamination. With only 63 post-2023
comments this is a pilot signal, not a headline; the powered run (thousands of
post-2023 comments via API key or bulk download) is the next step.

Methodological note: our first rank test showed z = +9.2 and was WRONG (a
tie-ordering bug systematically inflated post ranks). Caught by re-derivation;
only the permutation test and two-proportion comparison survived scrutiny.

## Powered result (bulk mirror sample, overnight run)

1,522 comments from the Mirrulations full mirror (6 agencies × 2019-21 vs
2023-25, matched within agency), 1,306 after form-letter dedup: **the pilot's
doubling did NOT replicate.** Suspect rate 10.1% pre vs 11.8% post (+1.7pp,
docket-level permutation p = 0.33). Per-year rates bounce 7-18% with no clean
ChatGPT inflection (2023 shows 18.1% but 2024-25 return to ~12%).

**Honest interpretation:** with ~1,300 comments we can rule out a large
(≳5pp) surge of heavy-AI-register comments — federal public comments do NOT
(yet) show the dramatic LLM contamination documented in scientific abstracts.
The pilot signal (n_post=63) was noise, exactly the risk its caveat named.
Remaining open: (a) subtle/light-register AI use is not excluded — the
detector is calibrated for the heavy "delve/underscore" register; (b) the
2023 bump and the FWS endangered-species dockets (16.7%) merit a targeted
look; (c) scale to 10k+ comments shrinks the excludable effect further.

This null is a finding: the democratic-input channel appears more
AI-resistant than the scientific literature — or AI commenters write less
floridly than AI paper-authors. Distinguishing those is the next experiment.
