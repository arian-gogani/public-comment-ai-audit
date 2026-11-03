#!/usr/bin/env python3
"""Forensic autopsy of one contested rulemaking docket.

Input: autopsy_<DOCKET>.jsonl (full comment pull from the mirror)
Output: campaign structure of the docket —
  organic singletons / exact-dup form letters (T1) / template families (T2) /
  paraphrase rings (T3) — with per-cluster timing, AI-register scoring, and
  representative excerpts. Writes autopsy_report_<DOCKET>.json.
"""
import json, sys, collections, statistics
from cluster import analyze
from detector import score

PATH = sys.argv[1] if len(sys.argv) > 1 else "autopsy_FWS-HQ-ES-2025-0039.jsonl"
DOCKET = PATH.split("autopsy_")[-1].replace(".jsonl", "")
COS_THR = 0.45

rows = [json.loads(l) for l in open(PATH)]
print(f"{DOCKET}: {len(rows)} records")
# usable text comments (attachment-only stubs excluded, noted honestly)
usable = [r for r in rows if len((r["text"] or "").split()) >= 15
          and not r["text"].lower().startswith("see attached")]
print(f"usable text comments (>=15 words): {len(usable)} "
      f"({len(rows)-len(usable)} attachment-only/short excluded)")

texts = [r["text"] for r in usable]
res = analyze(texts, COS_THR)

def day(r): return (r.get("posted") or "")[:10]

def cluster_stats(groups, tier):
    out = []
    for g in groups:
        mem = [usable[i] for i in g]
        days = collections.Counter(day(r) for r in mem)
        peak_day, peak_n = (days.most_common(1) or [("?", 0)])[0]
        fp = [score(r["text"])["fp_rate_per_1k"] for r in mem]
        lens = [len(r["text"].split()) for r in mem]
        out.append({
            "tier": tier, "size": len(g),
            "peak_day": peak_day, "peak_day_share": round(peak_n/len(g), 2),
            "n_days": len(days),
            "ai_register_mean": round(statistics.mean(fp), 1),
            "len_mean": round(statistics.mean(lens)),
            "len_cv": round((statistics.stdev(lens)/statistics.mean(lens)) if len(lens) > 1 and statistics.mean(lens) else 0, 2),
            "excerpt": mem[0]["text"][:160],
            "ids": [usable[i]["id"] for i in g[:5]],
        })
    out.sort(key=lambda c: -c["size"])
    return out

t1 = cluster_stats(res["t1"], "T1-exact")
t2 = cluster_stats(res["t2"], "T2-template")
t3 = cluster_stats(res["t3"], "T3-paraphrase")

n = len(usable)
in_t1 = sum(c["size"] for c in t1)
in_t2 = sum(c["size"] for c in t2)
in_t3 = sum(c["size"] for c in t3)
organic = n - in_t1 - in_t2 - in_t3
print(f"\nCAMPAIGN STRUCTURE of {DOCKET} (n={n} text comments):")
print(f"  exact-duplicate form letters (T1): {in_t1:6d}  ({in_t1/n*100:.1f}%) in {len(t1)} groups")
print(f"  template families (T2):            {in_t2:6d}  ({in_t2/n*100:.1f}%) in {len(t2)} families")
print(f"  paraphrase rings (T3):             {in_t3:6d}  ({in_t3/n*100:.1f}%) in {len(t3)} rings")
print(f"  apparent organic singletons:       {organic:6d}  ({organic/n*100:.1f}%)")

for label, cl in (("T1 exact-dup groups", t1), ("T2 template families", t2), ("T3 paraphrase rings", t3)):
    print(f"\ntop {label}:")
    for c in cl[:6]:
        print(f"  [{c['size']:5d}] peak {c['peak_day']} ({c['peak_day_share']*100:.0f}% that day, {c['n_days']} days) "
              f"AI-reg {c['ai_register_mean']}/1k lenCV {c['len_cv']}")
        print(f"         {c['excerpt'][:120]}...")

# docket-wide AI register vs the bulk baseline
fp_all = [score(r["text"])["fp_rate_per_1k"] for r in usable]
sus = sum(1 for v in fp_all if v > 5.0)  # bulk-run threshold
print(f"\ndocket-wide AI-register suspect rate (thr=5.0/1k): {sus}/{n} = {sus/n*100:.1f}% "
      f"(baseline human ~10%)")

json.dump({"docket": DOCKET, "n_records": len(rows), "n_usable": n,
           "pct_exact": in_t1/n, "pct_template": in_t2/n, "pct_paraphrase": in_t3/n,
           "pct_organic": organic/n, "suspect_rate": sus/n,
           "t1": t1[:20], "t2": t2[:20], "t3": t3[:40]},
          open(f"autopsy_report_{DOCKET}.json", "w"), indent=1)
print(f"\n-> autopsy_report_{DOCKET}.json")
