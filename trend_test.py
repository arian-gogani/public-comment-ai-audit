#!/usr/bin/env python3
"""Secular-trend control for the post-ChatGPT AI-register finding.

A raw pre/post comparison is confounded if AI-register vocabulary was ALREADY
rising before ChatGPT. It was (+0.2pp/yr). This fits a comment-weighted linear
trend on 2005-2022 and asks whether post-2023 years exceed what that trend
predicts. Also regenerates the two-panel findings figure with the trend drawn.
"""
import json, collections, statistics
from detector import score
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

rows = [json.loads(l) for l in open("national_sample.jsonl")]
hc = collections.Counter(r["h"] for r in rows)
bd = collections.defaultdict(list)
for r in rows: bd[r["docket"]].append(r)

recs = []
for dk, rs in bd.items():
    uniq = [r for r in rs if hc[r["h"]] == 1]          # individually-written only
    if not uniq: continue
    ai = [score(r["text"])["fp_rate_per_1k"] for r in uniq]
    recs.append({"a": rs[0]["stratum_agency"], "y": int(rs[0]["stratum_year"]),
                 "n": len(uniq), "ai": sum(1 for v in ai if v > 5.0)/len(ai)})

def wm(rr):
    d = sum(r["n"] for r in rr)
    return sum(r["ai"]*r["n"] for r in rr)/d if d else 0

ys = sorted({r["y"] for r in recs})
series = [(y, wm([r for r in recs if r["y"] == y]), sum(r["n"] for r in recs if r["y"] == y)) for y in ys]
series = [s for s in series if s[2] >= 300]
pre = [s for s in series if s[0] <= 2022]
post = [s for s in series if s[0] >= 2023]

sw = sum(n for _, _, n in pre)
mx = sum(y*n for y, _, n in pre)/sw; my = sum(v*n for _, v, n in pre)/sw
b = sum(n*(y-mx)*(v-my) for y, v, n in pre)/sum(n*(y-mx)**2 for y, _, n in pre)
a = my - b*mx
resid = [v - (a + b*y) for y, v, n in pre]
sd = statistics.pstdev(resid)

print(f"pre-2023 secular trend: {b*100:+.3f} pp/year, residual sd {sd*100:.2f}pp")
print(f"{'year':6s} {'obs':>7s} {'pred':>7s} {'excess':>8s} {'z':>6s}")
exc = []
for y, v, n in post:
    p = a + b*y; exc.append(v-p)
    print(f"{y:6d} {v*100:6.1f}% {p*100:6.1f}% {(v-p)*100:+7.1f}pp {(v-p)/sd:+6.2f}")
print(f"mean excess over trend: {statistics.mean(exc)*100:+.2f}pp | "
      f"all post years above trend: {all(e>0 for e in exc)} | "
      f"max pre-period residual: {max(resid)*100:+.2f}pp")

# ---- figure ----
fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=150)
ax = axes[0]
xs = [y for y, _, _ in series]; vals = [v*100 for _, v, _ in series]
ax.plot(xs, vals, marker="o", color="#b23b3b", lw=2, label="observed")
tx = list(range(min(xs), max(xs)+1))
ax.plot(tx, [(a+b*y)*100 for y in tx], ls=":", color="#777", lw=2,
        label=f"pre-ChatGPT trend ({b*100:+.2f} pp/yr)")
ax.axvline(2022.9, ls="--", color="#444", lw=1.5)
ax.text(2022.75, max(vals)*0.97, "ChatGPT\nreleased", ha="right", fontsize=9, color="#444")
ax.set_title("AI-register vocabulary in individually-written\nUS federal public comments", fontsize=11)
ax.set_ylabel("% of comments above threshold"); ax.set_xlabel("year")
ax.legend(fontsize=9, frameon=False); ax.spines[["top","right"]].set_visible(False)

ax = axes[1]
diffs = []
for ag in sorted({r["a"] for r in recs}):
    p = [r for r in recs if r["a"] == ag and r["y"] <= 2022]
    q = [r for r in recs if r["a"] == ag and r["y"] >= 2023]
    if sum(r["n"] for r in p) >= 200 and sum(r["n"] for r in q) >= 200:
        diffs.append((wm(q)*100 - wm(p)*100, ag))
diffs.sort()
ax.barh([x[1] for x in diffs], [x[0] for x in diffs],
        color=["#4a7c59" if d < 0 else "#b23b3b" for d, _ in diffs])
ax.axvline(0, color="#333", lw=1)
ax.set_title("Change after ChatGPT, within each agency\n(controls for shifting agency mix)", fontsize=11)
ax.set_xlabel("percentage-point change"); ax.spines[["top","right"]].set_visible(False)
plt.tight_layout(); plt.savefig("national_findings.png")
print("-> national_findings.png")
json.dump({"slope_pp_per_year": b*100, "resid_sd_pp": sd*100,
           "post": [{"year": y, "observed": v, "predicted": a+b*y, "excess": v-(a+b*y)} for y, v, _ in post],
           "mean_excess_pp": statistics.mean(exc)*100},
          open("trend_results.json", "w"), indent=1)
