#!/usr/bin/env python3
"""LLM-fingerprint detector for public-comment text.

Method (same family as Kobak et al. PNAS 2024 'excess words' and the 7.3M-paper
spike-word detectors): score text by its density of vocabulary that became
sharply over-represented in human writing only AFTER ChatGPT (Nov 2022). These
words are not rare English words — they are ones LLMs over-produce. A single
word proves nothing; the SIGNAL is an elevated *rate* across a corpus, and the
honest measurement is the rate's CHANGE across the Nov-2022 boundary, calibrated
against pre-2022 comments that are guaranteed human.
"""
import re, math, collections

# Curated LLM-overrepresented lexicon. Robust subset of the empirically-derived
# 'excess words' literature (delve/intricate/underscore families etc.). Lemmas
# are matched with simple suffix expansion below.
FINGERPRINT_LEMMAS = [
    "delve", "intricate", "intricacy", "crucial", "pivotal", "realm", "showcase",
    "underscore", "comprehensive", "notably", "meticulous", "commendable",
    "seamless", "testament", "leverage", "align", "foster", "garner", "nuanced",
    "nuance", "holistic", "robust", "multifaceted", "interplay", "landscape",
    "navigate", "tapestry", "beacon", "bolster", "encompass", "elevate",
    "pertinent", "paramount", "myriad", "spearhead", "harness", "unveil",
    "endeavor", "delineate", "embark", "facilitate", "underpin", "cultivate",
    "profound", "vital", "vibrant", "intersection", "ever-evolving", "evolving",
    "transformative", "invaluable", "pivotal", "indelible", "resonate",
    "furthermore", "moreover", "additionally", "consequently", "nevertheless",
]
# suffix expansion -> surface forms
def expand(lemma):
    base = {lemma}
    if lemma.endswith("e"):
        base |= {lemma + "s", lemma[:-1] + "ing", lemma + "d", lemma[:-1] + "ed",
                 lemma[:-1] + "ement", lemma[:-1] + " es"}
    else:
        base |= {lemma + "s", lemma + "ing", lemma + "ed", lemma + "es"}
    # noun/adverb forms
    base |= {lemma + "ly", lemma + "ness", lemma + "tion", lemma + "ment"}
    return base

FINGERPRINT = set()
for lem in FINGERPRINT_LEMMAS:
    FINGERPRINT |= expand(lem)

# Structural tells LLMs over-use (counted separately, lighter weight)
STRUCT_PATTERNS = [
    (r"\bit['’]s (?:important|worth|crucial|essential) to (?:note|remember|recognize)\b", "it's-important-to"),
    (r"\bin (?:today|conclusion|summary|essence)['’]?s?\b", "in-conclusion"),
    (r"\bnot only\b.{0,60}\bbut also\b", "not-only-but-also"),
    (r"\bplays? a (?:crucial|vital|pivotal|significant|key) role\b", "plays-a-role"),
    (r"\ba (?:testament|beacon) (?:to|of)\b", "testament-to"),
    (r"\bwhen it comes to\b", "when-it-comes-to"),
    (r"\bnavigat(?:e|ing) the (?:complex|intricate|ever-)", "navigate-the-complex"),
]

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")

def tokenize(text):
    return [w.lower().replace("’", "'") for w in WORD_RE.findall(text or "")]

def score(text):
    """Return dict with fingerprint-word rate per 1000 words + structural hits."""
    toks = tokenize(text)
    n = len(toks)
    if n == 0:
        return {"n_words": 0, "fp_rate_per_1k": 0.0, "fp_hits": 0, "struct_hits": 0, "hit_words": []}
    hits = [t for t in toks if t in FINGERPRINT]
    struct = sum(1 for pat, _ in STRUCT_PATTERNS if re.search(pat, text, re.I))
    return {
        "n_words": n,
        "fp_hits": len(hits),
        "fp_rate_per_1k": len(hits) / n * 1000,
        "struct_hits": struct,
        "hit_words": collections.Counter(hits).most_common(8),
    }

if __name__ == "__main__":
    human = ("I am a small business owner and I strongly oppose this rule. It will "
             "raise my costs and make it harder to hire people in my town. Please "
             "reconsider. Thank you for listening to regular folks like me.")
    ai = ("I am writing to underscore the profound importance of this pivotal "
          "rulemaking. It is crucial to delve into the multifaceted and intricate "
          "landscape of stakeholder concerns. This comprehensive framework "
          "represents a testament to robust governance, and it is important to note "
          "that it plays a crucial role in fostering a seamless, holistic approach.")
    for label, t in [("HUMAN", human), ("AI-STYLE", ai)]:
        s = score(t)
        print(f"{label:9s} fp_rate/1k={s['fp_rate_per_1k']:6.1f} struct={s['struct_hits']} "
              f"hits={[w for w,_ in s['hit_words']]}")
