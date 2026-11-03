#!/usr/bin/env python3
"""Powered analysis of the bulk Mirrulations sample.

Upgrades over the pilot:
 - form-letter dedup (shingle signatures)
 - docket-level permutation test (comments cluster within dockets; permuting
   docket era-labels is the honest null)
 - per-year time series and per-agency breakdown
"""
import json, math, re, statistics, collections, random, sys
from detector import score

rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "bulk_comments.jsonl")]
print(f"loaded {len(rows)}")

def shingle_sig(t, k=8):
    toks = re.sub(r"\s+", " ", t.lower()).split()
    if len(toks) < k: return tuple(toks)
    return tuple(sorted(hash(" ".join(toks[i:i+k])) for i in range(0, len(toks)-k+1, k))[:5])

seen, ded = set(), []
for r in rows:
    s = shingle_sig(r["text"])
    if s in seen: continue
    seen.add(s); ded.append(r)
print(f"after form-letter dedup: {len(ded)} ({len(rows)-len(ded)} removed)")

for r in ded:
    r["v"] = score(r["text"])["fp_rate_per_1k"]
    r["year"] = (r.get("posted") or "0000")[:4]

pre = [r for r in ded if r["era"] == "pre" and r["year"] <= "2022"]
post = [r for r in ded if r["era"] == "post" and r["year"] >= "2023"]
print(f"pre (<=2022): {len(pre)}   post (>=2023): {len(post)}")

import numpy as np
thr = float(np.percentile([r["v"] for r in pre], 90))
def srate(rs): return sum(1 for r in rs if r["v"] > thr) / len(rs) if rs else 0
p1, p2 = srate(pre), srate(post)
print(f"\nthreshold (90th pctile of guaranteed-human) = {thr:.2f}/1k")
print(f"PRE  suspect rate: {p1*100:.1f}%  (n={len(pre)}; ~10% by design)")
print(f"POST suspect rate: {p2*100:.1f}%  (n={len(post)})")
print(f"difference: {(p2-p1)*100:+.1f} pp")

# docket-level permutation: shuffle which DOCKETS are pre vs post
dockets = collections.defaultdict(list)
for r in pre + post: dockets[r["docket"]].append(r)
dlist = list(dockets.items())
n_post_dockets = len(set(r["docket"] for r in post))
obs = p2 - p1
rng = random.Random(0)
hits = 0; B = 5000
for _ in range(B):
    rng.shuffle(dlist)
    g_post = [r for _, rs in dlist[:n_post_dockets] for r in rs]
    g_pre = [r for _, rs in dlist[n_post_dockets:] for r in rs]
    if g_post and g_pre and (srate(g_post) - srate(g_pre)) >= obs: hits += 1
print(f"docket-level permutation p = {hits/B:.4f}  ({B} shuffles)")

# comment-level two-proportion (anti-conservative; report for comparison)
k1 = sum(1 for r in pre if r["v"] > thr); k2 = sum(1 for r in post if r["v"] > thr)
pooled = (k1 + k2)/(len(pre) + len(post))
se = math.sqrt(pooled*(1-pooled)*(1/len(pre) + 1/len(post)))
print(f"comment-level two-proportion z = {(p2-p1)/se:+.2f} (ignores docket clustering)")

print("\nper-year suspect rate:")
for y in sorted(set(r["year"] for r in ded)):
    rs = [r for r in ded if r["year"] == y]
    if len(rs) >= 30:
        print(f"  {y}: {srate(rs)*100:5.1f}%  (n={len(rs)})")

print("\nper-agency (post-2023):")
for ag in sorted(set(r["agency"] for r in post)):
    rs = [r for r in post if r["agency"] == ag]
    if len(rs) >= 20:
        print(f"  {ag}: {srate(rs)*100:5.1f}%  (n={len(rs)})")

print("\nmost AI-suspect post comments:")
for r in sorted(post, key=lambda r: -r["v"])[:5]:
    print(f"  [{r['v']:.0f}/1k {r['year']} {r['docket']}] {r['text'][:120].strip()}...")

json.dump({"n_pre": len(pre), "n_post": len(post), "threshold": thr,
           "pre_rate": p1, "post_rate": p2, "perm_p_docket": hits/B},
          open("bulk_results.json", "w"), indent=1)
print("\n-> bulk_results.json")
