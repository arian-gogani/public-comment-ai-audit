# Who Is Actually Talking When America Comments on Its Laws?

*A national measurement of mass-produced and AI-register text in US federal
public comments: 42,140 comments sampled across 340 agencies and 20 years,
plus a full forensic dissection of one 118,284-comment rulemaking war.*

---

## The question

When a U.S. federal agency proposes a rule — on endangered species, drug
scheduling, workplace safety — it is required by law to ask the public for
comments, and to read and consider them. This is one of the few direct lines
between ordinary people and the regulatory state.

Two things made us want to X-ray that channel in 2026:

1. **Science got flooded.** Multiple studies have documented a measurable surge
   of AI-generated text in research papers after ChatGPT (late 2022).
2. **The comment system has been gamed before.** The 2017 net-neutrality
   proceeding famously drowned in millions of fake comments — *before*
   generative AI existed.

So: **is AI now writing America's public comments?** Nobody had measured it.
We did — first broadly, then with a scalpel.

## How we measured (and how we kept ourselves honest)

We used the same family of methods that exposed AI text in scientific papers:
a lexicon of words and constructions that spiked in human writing only after
ChatGPT ("delve," "underscore," "it is important to note…"), scored as a rate
per 1,000 words. No single word proves anything — the signal is a *rate* and
its *change over time*.

Two design choices did the heavy lifting:

- **A built-in answer key.** Comments posted before November 2022 *cannot* be
  AI-generated. They are a guaranteed-human baseline. We set our "suspect"
  threshold so exactly ~10% of guaranteed-human comments trip it — then any
  excess above 10% in later comments is signal, not noise.
- **Plant-and-recover validation.** Before trusting any instrument on real
  data, we planted known AI text (and, later, synthetic paraphrase rings) in
  clean corpora and required the instrument to find them — and to find
  *nothing* in pure-human controls. Two early "exciting findings" died in
  these checks (a statistics bug, then a small-sample mirage). They never
  reached this page; that is the point of the method.

Data came from the public [Mirrulations](https://registry.opendata.aws/mirrulations/)
mirror of regulations.gov — no special access, fully reproducible.

## Finding 1 (CORRECTED): AI-register text in individually-written comments has roughly doubled

**This section replaces an earlier, underpowered null result. The original
conclusion was wrong, and the correction is instructive.**

Our first pass used 1,306 comments across six agencies and found no
post-ChatGPT change (10.1% vs 11.8%, p = 0.33). We published that as "the AI
flood has not arrived." We then built a nationally stratified sample — **42,140
comments from 3,583 dockets across every major agency, 2005-2026** — and the
null did not survive the added power:

| population | pre-ChatGPT (≤2022) | post-ChatGPT (≥2023) | change | p |
|---|---|---|---|---|
| **individually-written comments** | 5.86% | 11.36% | **+5.5 pp** | **< 0.0001** |
| campaign/duplicate comments | 13.94% | 21.46% | +7.5 pp | 0.27 (n.s.) |
| all comments pooled | 6.55% | 12.40% | +5.9 pp | 0.0014 |

Two checks make this defensible:

**Composition control.** The agency mix shifts sharply between eras (CDC and
FINCEN appear only post-2023; FWS and NOAA only pre-2022), and those agencies
have very different baseline rates — so the pooled result alone would be
confounded. Comparing *within* each agency that has data on both sides removes
this: **all four such agencies increased** (median +6.5 pp), with EPA the
best-powered case (8,776 pre vs 2,145 post comments, 4.8% → 11.1%).

**Clustering control.** All p-values come from permuting *dockets*, not
comments, because comments cluster heavily within dockets.

**Why our ESA study (Finding 3) found nothing.** That docket is 64% campaign
mail, and campaign mail is pre-written human text; the AI signal lives in the
individually-written minority, which that single-fight sample could not
resolve. The two results are consistent, not contradictory.

### What this does and does not show

It does **not** prove 11% of recent comments were written by ChatGPT. The
metric is *AI-register vocabulary*, and writing norms can drift for other
reasons. What it shows is that the linguistic signature associated with LLM
output has roughly doubled in individually-written public comments since
ChatGPT's release, holds within agencies, and is highly unlikely to be chance.

## Finding 2: what the "public" actually is — an autopsy

Averages hide structure, so we dissected a single battlefield end-to-end:
docket **FWS-HQ-ES-2025-0039**, the fiercely contested proposal to rewrite the
Endangered Species Act's definition of "harm." We pulled every comment —
35,714 — and clustered the 33,737 with usable text into families: exact
duplicates, lightly-edited templates, and *paraphrase rings* (same skeleton,
reworded — the signature LLM-era astroturf would leave).

The anatomy of the "public voice" on this rule:

![campaign structure](campaign_structure.png)

| who | share |
|---|---|
| **Exact-copy form letters** | **68.0%** |
| Lightly-edited templates | 10.3% |
| Paraphrase rings | 3.0% |
| Apparently individual comments | **18.6%** |

Concretely:

- **One single form letter appears 14,336 times — 42% of the entire docket.**
  One piece of text outweighs every individually-written comment combined.
- A 551-copy religious-themed letter arrived **100% on one day** — a
  coordinated batch dump, not a congregation moved to write.
- The largest paraphrase ring has 540 members spanning 20 days.

**And the machinery is human.** The docket-wide AI-register rate is 7.6% —
*below* the human baseline. Even the paraphrase rings score in the human
range; they look like advocacy-platform "personalize your message" tools, not
language models.


## Finding 3: the five-front war

The "harm definition" docket was one front of a coordinated 2025 offensive —
five companion dockets revising different pillars of the Endangered Species
Act. We pulled **all 118,284 comments** across the five and fingerprinted
every letter globally:

- **1,242 distinct letters hit multiple dockets.** The second-largest letter
  fired **14,400 copies across four dockets in near-perfectly equal shares**
  (3,592 / 3,643 / 3,583 / 3,582) — the signature of a mail cannon configured
  for four targets, not of people choosing where to write.
- **Synchronized bombardment days:** December 22 alone delivered 15,299
  comments across four fronts simultaneously; three more such multi-front
  wave days (Dec 8, 9, 18). The spring front had its own 18,133-comment
  single-day spike.
- **War-wide census** (112,221 usable comments, disjoint accounting — every
  comment counted exactly once): **17.8% exact copies, 45.2% template
  families, 1.2% paraphrase rings, 35.8% apparent individuals.** Roughly
  **two of every three comments in the entire war are campaign mail.** (The
  single-docket table above shows a harsher 4-of-5 ratio; the difference is
  real — fronts differ — and definitional: globally, exact copies that belong
  to a template family are counted with their family.)
- **AI register across the full war: 10.0% — exactly the human baseline.**
  The strongest-powered version of Finding 1: even in the most contested
  environmental rulemaking of 2025, the astroturf machinery is human-built.

A methodological note we insist on including: our first war-map run produced
an impossible total (a negative share) and a fictitious 32,742-member
"paraphrase ring" — an artifact of short comments chaining on shared topic
words. Both were caught by internal consistency checks, fixed (disjoint
accounting; length-and-density guards validated on planted rings), and only
then published. This is the third wrong number this project's own checks have
intercepted before publication.

## What this means

1. **Four out of five "public voices" on a major federal rule are
   mass-produced campaign mail.** When an agency says it received 35,000
   comments, the number of distinct human arguments may be two orders of
   magnitude smaller.
2. **The astroturf machine predates AI and hasn't needed it (yet).** The
   tooling that matters today is the email-this-form advocacy platform, not
   ChatGPT.
3. **When the AI wave does arrive, it will be visible.** This project leaves
   behind a validated, open-source instrument and a clean 2019–2025 baseline.
   The paraphrase-ring share (3%) and AI-register rate (7.6%) of this docket
   are now on the record; movement in those numbers is detectable the week it
   happens.

## Caveats, stated plainly

- A flagged comment is **not** an accusation against any individual — humans
  legitimately use every word in our lexicon. Only rates and trends carry
  meaning, which is why we report nothing about any named commenter.
- ~2,000 attachment-only comments (PDFs) were not analyzed.
- Our detector catches the heavy "ChatGPT register." Lightly-AI-assisted text
  that reads naturally is beyond its floor — documented, not hidden.
- Paraphrase rings indicate coordination, not necessarily any specific tool.

## Reproduce it

Everything — detector, clusterer, fetchers, validation suites, and the full
analysis — is in this repository. The data source is public. Start with
`README.md`; every claim above re-derives from committed code.

*Independent research, November 2026.*
