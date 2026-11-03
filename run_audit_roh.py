#!/usr/bin/env python3
"""First real audit: ro-h/regulatory_comments dataset (1,593 comments, 274 dockets,
1996-2024). Pre-2023 = guaranteed-human calibration set; post-2023 = test set.
Includes form-letter dedup (exact + near-dup via shingle hashing)."""
import json, math, statistics, collections, re
from detector import score

d = json.load(open("data_roh.json"))
rows = []
for docket in d:
    for c in docket.get("comments", []):
        txt = (c.get("text") or "").strip()
        dt = c.get("comment_date", "")
        if not txt or not dt or len(txt.split()) < 25:
            continue
        rows.append({"id": c.get("comment_id"), "text": txt, "date": dt,
                     "docket": docket.get("id"), "agency": docket.get("agency")})
print(f"usable comments (>=25 words, dated): {len(rows)}")

# --- dedup: exact and near-duplicate (form letters) ---
def normtext(t):
    return re.sub(r"\s+", " ", t.lower()).strip()
def shingle_sig(t, k=8):
    toks = normtext(t).split()
    if len(toks) < k: return tuple(toks)
    shingles = [" ".join(toks[i:i+k]) for i in range(0, len(toks)-k+1, k)]
    return tuple(sorted(hash(s) for s in shingles)[:5])  # min-hash-ish signature

seen, deduped, dupes = set(), [], 0
for r in rows:
    sig = shingle_sig(r["text"])
    if sig in seen:
        dupes += 1; continue
    seen.add(sig); deduped.append(r)
print(f"after form-letter dedup: {len(deduped)} unique ({dupes} near-dupes removed)")

for r in deduped:
    r["s"] = score(r["text"])

pre = [r for r in deduped if r["date"][:4] <= "2022"]
post = [r for r in deduped if r["date"][:4] >= "2023"]
print(f"pre-ChatGPT (<=2022, guaranteed human): {len(pre)}")
print(f"post-ChatGPT (>=2023): {len(post)}\n")

import numpy as np
pre_rates = [r["s"]["fp_rate_per_1k"] for r in pre]
post_rates = [r["s"]["fp_rate_per_1k"] for r in post]
print(f"fingerprint-word rate per 1k words:")
print(f"  pre : mean={statistics.mean(pre_rates):.2f} median={statistics.median(pre_rates):.2f}")
print(f"  post: mean={statistics.mean(post_rates):.2f} median={statistics.median(post_rates):.2f}")
# Mann-Whitney-ish: rank-based comparison
both = [(v, 0) for v in pre_rates] + [(v, 1) for v in post_rates]
both.sort()
ranks = {}
r_sum = 0
for i, (v, g) in enumerate(both):
    if g == 1: r_sum += i + 1
n1, n2 = len(pre_rates), len(post_rates)
mu = n2 * (n1 + n2 + 1) / 2
sd = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
z_mw = (r_sum - mu) / sd
print(f"  rank-test z (post vs pre distribution shift): {z_mw:+.2f}")

thr = float(np.percentile(pre_rates, 90))
k_pre = sum(1 for v in pre_rates if v > thr)
k_post = sum(1 for v in post_rates if v > thr)
p1, p2 = k_pre/n1, k_post/n2
pooled = (k_pre + k_post)/(n1 + n2)
se = math.sqrt(pooled*(1-pooled)*(1/n1 + 1/n2))
z = (p2 - p1)/se if se else 0
print(f"\nsuspect threshold (90th pctile of human) = {thr:.1f}/1k")
print(f"  pre  suspect rate: {k_pre}/{n1} = {p1*100:.1f}% (fixed ~10% by design)")
print(f"  post suspect rate: {k_post}/{n2} = {p2*100:.1f}%")
print(f"  two-proportion z = {z:+.2f}")
excess = max(0, p2 - p1)
print(f"  implied AI-register excess in post-2023 comments: {excess*100:.1f} pp")

print("\ntop suspect post-2023 comments:")
for r in sorted(post, key=lambda r: -r["s"]["fp_rate_per_1k"])[:5]:
    hw = [w for w, _ in r["s"]["hit_words"]]
    print(f"  [{r['s']['fp_rate_per_1k']:.0f}/1k {r['date']} {r['docket']}] {hw}")
    print(f"    {r['text'][:140].strip()}...")

json.dump({"n_pre": n1, "n_post": n2, "threshold": thr,
           "pre_suspect": p1, "post_suspect": p2, "z_two_prop": z, "z_rank": z_mw},
          open("audit_roh_results.json", "w"), indent=1)
print("\nresults -> audit_roh_results.json")
