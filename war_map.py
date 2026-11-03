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
in_t1 = sum(len(v) for v in byk.values() if len(v) > 1)
t2m = members_of(res["t2"]); t3m = members_of(res["t3"])
in_t2 = sum(t for t, _, _ in t2m); in_t3 = sum(t for t, _, _ in t3m)
organic = n - in_t1 - in_t2 - in_t3
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
