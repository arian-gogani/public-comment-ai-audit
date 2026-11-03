#!/usr/bin/env python3
"""Cross-docket war map of the 2025 ESA rulemaking offensive.

Loads every autopsy_FWS-*.jsonl, fingerprints form letters globally, and maps:
  - which letters/templates/rings hit which fronts (dockets)
  - synchronized submission waves across fronts
  - per-front campaign structure + the all-front totals
"""
import json, glob, collections, statistics
from cluster import analyze, exact_key, norm
from detector import score

files = sorted(glob.glob("autopsy_FWS-*.jsonl"))
print("fronts:", [f.split("autopsy_")[-1][:-6] for f in files])

ALL = []
for f in files:
    docket = f.split("autopsy_")[-1][:-6]
    for line in open(f):
        r = json.loads(line)
        if len((r["text"] or "").split()) >= 15 and not r["text"].lower().startswith("see attached"):
            r["front"] = docket
            ALL.append(r)
print(f"total usable comments across fronts: {len(ALL)}")

# ---------- global exact-letter fingerprinting ----------
byk = collections.defaultdict(list)
for r in ALL: byk[exact_key(r["text"])].append(r)
letters = [(len(v), v) for v in byk.values() if len(v) > 1]
letters.sort(reverse=True, key=lambda x: x[0])

multi_front = [(n, v) for n, v in letters if len(set(r["front"] for r in v)) > 1]
print(f"\nduplicated letters: {len(letters)}; hitting MULTIPLE fronts: {len(multi_front)}")
print("\ntop cross-front letters (copies, fronts, peak day):")
for n, v in multi_front[:10]:
    fronts = collections.Counter(r["front"] for r in v)
    days = collections.Counter((r.get("posted") or "")[:10] for r in v)
    peak = days.most_common(1)[0]
    print(f"  [{n:6d} copies over {len(fronts)} fronts] peak {peak[0]} ({peak[1]})")
    print(f"      fronts: {dict(fronts)}")
    print(f"      text: {v[0]['text'][:110]}...")

# ---------- synchronized waves ----------
print("\nsubmission waves (day x front, top days):")
daymat = collections.defaultdict(collections.Counter)
for r in ALL:
    daymat[(r.get("posted") or "")[:10]][r["front"]] += 1
days_sorted = sorted(daymat.items(), key=lambda kv: -sum(kv[1].values()))[:8]
for d, c in days_sorted:
    tot = sum(c.values())
    print(f"  {d}: {tot:6d} total — " + ", ".join(f"{k.split('-')[-1]}:{v}" for k, v in c.most_common()))

# ---------- global campaign structure (unique texts across all fronts) ----------
uniq_reps = [v[0] for v in byk.values()]
print(f"\nglobal clustering over {len(uniq_reps)} unique texts...")
res = analyze([r["text"] for r in uniq_reps], 0.45, verbose=True)
# guard: dissolve T3 clusters dominated by short texts, and enforce density on big clusters
import random as _rnd
from cluster import build_tfidf as _bt, cos as _cos
def _dense_enough(g, texts, thr=0.45, sample=60):
    if len(g) <= 10: return True
    vs, _ = _bt([texts[i] for i in g[:400]])
    rng = _rnd.Random(1)
    idx = list(range(len(vs)))
    sims = []
    for _i in range(min(sample, len(idx)*(len(idx)-1)//2)):
        a, b = rng.sample(idx, 2)
        sims.append(_cos(vs[a], vs[b]))
    return sum(sims)/len(sims) >= thr
_texts = [r["text"] for r in uniq_reps]
res["t3"] = [g for g in res["t3"]
             if statistics.mean(len(_texts[i].split()) for i in g) >= 30
             and _dense_enough(g, _texts)]
print(f"after guards: T3 rings={len(res['t3'])} (members {sum(map(len,res['t3']))})")

def members_of(groups):
    out = []
    for g in groups:
        tot = sum(len(byk[exact_key(uniq_reps[i]["text"])]) for i in g)
        fronts = set()
        for i in g:
            for r in byk[exact_key(uniq_reps[i]["text"])]: fronts.add(r["front"])
        out.append((tot, len(fronts), uniq_reps[g[0]]["text"][:100]))
    out.sort(reverse=True)
    return out

n = len(ALL)
t2m = members_of(res["t2"]); t3m = members_of(res["t3"])
# DISJOINT accounting: each comment belongs to exactly one population.
t2_set = {i for g in res["t2"] for i in g}
t3_set = {i for g in res["t3"] for i in g}
in_t1 = in_t2 = in_t3 = organic = 0
for ui, rep in enumerate(uniq_reps):
    copies = len(byk[exact_key(rep["text"])])
    if ui in t2_set: in_t2 += copies
    elif ui in t3_set: in_t3 += copies
    elif copies > 1: in_t1 += copies
    else: organic += 1
assert in_t1 + in_t2 + in_t3 + organic == n, (in_t1, in_t2, in_t3, organic, n)
print(f"\nWAR TOTALS (n={n}):")
print(f"  exact-copy letters:   {in_t1:6d} ({in_t1/n*100:.1f}%)")
print(f"  template families:    {in_t2:6d} ({in_t2/n*100:.1f}%)")
print(f"  paraphrase rings:     {in_t3:6d} ({in_t3/n*100:.1f}%)")
print(f"  apparent individuals: {organic:6d} ({organic/n*100:.1f}%)")

print("\ntop template families (total copies, fronts):")
for t, nf, ex in t2m[:5]: print(f"  [{t:5d} / {nf} fronts] {ex}...")
print("\ntop paraphrase rings (total members, fronts):")
for t, nf, ex in t3m[:5]: print(f"  [{t:5d} / {nf} fronts] {ex}...")

# AI register, war-wide
fp = [score(r["text"])["fp_rate_per_1k"] for r in ALL]
sus = sum(1 for v in fp if v > 5.0)
print(f"\nwar-wide AI-register suspect rate: {sus}/{n} = {sus/n*100:.1f}% (human baseline ~10%)")

json.dump({"fronts": [f.split('autopsy_')[-1][:-6] for f in files], "n": n,
           "pct": {"exact": in_t1/n, "template": in_t2/n, "ring": in_t3/n, "organic": organic/n},
           "multi_front_letters": len(multi_front), "suspect_rate": sus/n},
          open("war_map_results.json", "w"), indent=1)
print("\n-> war_map_results.json")
