#!/usr/bin/env python3
"""Milestone 5: national estimates from the stratified sample.

Produces, with uncertainty:
  - share of federal public comments that are mass-produced (exact dup / template)
  - AI-register rate, by year (the ChatGPT question at national scale)
  - per-agency rankings
  - the 20-year time series

Clustering is done PER DOCKET (campaigns operate within dockets), which keeps it
O(n) overall; cross-docket repetition is caught by exact hashes.
Bootstrap CIs resample DOCKETS, not comments, because comments cluster within
dockets and comment-level CIs would be far too narrow.
"""
import json, collections, random, statistics, sys
from detector import score
from cluster import analyze

PATH = sys.argv[1] if len(sys.argv) > 1 else "national_sample.jsonl"
rows = [json.loads(l) for l in open(PATH)]
print(f"loaded {len(rows):,} comments")

by_docket = collections.defaultdict(list)
for r in rows: by_docket[r["docket"]].append(r)
print(f"{len(by_docket):,} dockets")

# ---- per-docket campaign structure ----
docket_rec = []
for dk, rs in by_docket.items():
    hs = collections.Counter(r["h"] for r in rs)
    n = len(rs)
    exact = sum(c for c in hs.values() if c > 1)
    # template detection only where it can mean anything
    tmpl = 0
    if 8 <= n <= 4000:
        uniq_idx = {}
        for i, r in enumerate(rs):
            uniq_idx.setdefault(r["h"], i)
        reps = list(uniq_idx.values())
        if len(reps) > 3:
            try:
                res = analyze([rs[i]["text"] for i in reps], 0.45, verbose=False)
                members = {i for g in res["t2"] for i in g}
                tmpl = sum(hs[rs[reps[i]]["h"]] for i in members if i < len(reps))
            except Exception:
                tmpl = 0
    ai = [score(r["text"])["fp_rate_per_1k"] for r in rs]
    docket_rec.append({
        "docket": dk, "agency": rs[0]["stratum_agency"], "year": rs[0]["stratum_year"],
        "n": n, "exact_share": exact / n, "template_share": min(tmpl, n - exact) / n,
        "ai_rates": ai, "docket_total": rs[0].get("docket_total_comments", n),
    })

def wmean(recs, field):
    """comment-weighted mean of a per-docket share"""
    num = sum(d[field] * d["n"] for d in recs)
    den = sum(d["n"] for d in recs)
    return num / den if den else 0.0

def boot_ci(recs, field, B=1000):
    if len(recs) < 2: return (0, 0)
    rng = random.Random(7)
    vals = []
    for _ in range(B):
        samp = [recs[rng.randrange(len(recs))] for _ in range(len(recs))]
        vals.append(wmean(samp, field))
    vals.sort()
    return (vals[int(0.025*B)], vals[int(0.975*B)])

AI_THR = 5.0
for d in docket_rec:
    d["ai_share"] = sum(1 for v in d["ai_rates"] if v > AI_THR) / len(d["ai_rates"])

print("\n=== NATIONAL ESTIMATES (comment-weighted, docket-bootstrap 95% CI) ===")
for field, label in (("exact_share", "exact-duplicate comments"),
                     ("template_share", "template-family comments"),
                     ("ai_share", "AI-register comments")):
    m = wmean(docket_rec, field); lo, hi = boot_ci(docket_rec, field)
    print(f"  {label:28s} {m*100:5.1f}%   95% CI [{lo*100:.1f}, {hi*100:.1f}]")
mass = wmean(docket_rec, "exact_share") + wmean(docket_rec, "template_share")
print(f"  {'TOTAL mass-produced':28s} {mass*100:5.1f}%")

print("\n=== BY YEAR ===")
print(f"  {'year':6s} {'n':>8s} {'dockets':>8s} {'exact%':>8s} {'tmpl%':>8s} {'AI%':>7s}")
for y in sorted({d["year"] for d in docket_rec}):
    recs = [d for d in docket_rec if d["year"] == y]
    n = sum(d["n"] for d in recs)
    if n < 100: continue
    print(f"  {y:6s} {n:8,d} {len(recs):8,d} {wmean(recs,'exact_share')*100:7.1f}% "
          f"{wmean(recs,'template_share')*100:7.1f}% {wmean(recs,'ai_share')*100:6.1f}%")

print("\n=== BY AGENCY (>=300 sampled comments) ===")
rankings = []
for a in sorted({d["agency"] for d in docket_rec}):
    recs = [d for d in docket_rec if d["agency"] == a]
    n = sum(d["n"] for d in recs)
    if n < 300: continue
    rankings.append((wmean(recs, "exact_share") + wmean(recs, "template_share"), a, n,
                     wmean(recs, "ai_share")))
rankings.sort(reverse=True)
print(f"  {'agency':10s} {'n':>8s} {'mass%':>8s} {'AI%':>7s}")
for mass_a, a, n, ai in rankings[:15]:
    print(f"  {a:10s} {n:8,d} {mass_a*100:7.1f}% {ai*100:6.1f}%")

json.dump({"n_comments": len(rows), "n_dockets": len(by_docket),
           "national": {f: wmean(docket_rec, f) for f in ("exact_share","template_share","ai_share")},
           "by_year": {y: {"n": sum(d["n"] for d in docket_rec if d["year"]==y),
                            "exact": wmean([d for d in docket_rec if d["year"]==y], "exact_share"),
                            "template": wmean([d for d in docket_rec if d["year"]==y], "template_share"),
                            "ai": wmean([d for d in docket_rec if d["year"]==y], "ai_share")}
                       for y in sorted({d["year"] for d in docket_rec})},
           "by_agency": [{"agency": a, "n": n, "mass": m, "ai": ai} for m, a, n, ai in rankings]},
          open("national_results.json", "w"), indent=1)
print("\n-> national_results.json")
