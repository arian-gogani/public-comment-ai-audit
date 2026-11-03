#!/usr/bin/env python3
"""Generate the campaign-structure chart for the writeup from war_map_results.json
(falls back to the single-docket autopsy report if the war map isn't done)."""
import json, os

if os.path.exists("war_map_results.json"):
    d = json.load(open("war_map_results.json"))
    pct = d["pct"]; n = d["n"]; title_n = f"{n:,} comments, five dockets"
else:
    d = json.load(open("autopsy_report_FWS-HQ-ES-2025-0039.json"))
    pct = {"exact": d["pct_exact"], "template": d["pct_template"],
           "ring": d["pct_paraphrase"], "organic": d["pct_organic"]}
    n = d["n_usable"]; title_n = f"{n:,} comments, one docket"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

labels = ["Exact-copy\nform letters", "Lightly-edited\ntemplates",
          "Paraphrase\nrings", "Apparent\nindividuals"]
vals = [pct["exact"]*100, pct["template"]*100, pct["ring"]*100, pct["organic"]*100]
colors = ["#b23b3b", "#d98841", "#c9b458", "#4a7c59"]

fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
bars = ax.barh(labels[::-1], vals[::-1], color=colors[::-1], edgecolor="none", height=0.62)
for b, v in zip(bars, vals[::-1]):
    ax.text(b.get_width() + 0.8, b.get_y() + b.get_height()/2, f"{v:.1f}%",
            va="center", fontsize=12, fontweight="bold")
ax.set_xlim(0, max(vals)*1.18)
ax.set_xlabel("share of comments")
ax.set_title(f"Who is the “public” in a federal comment war?\n"
             f"2025 Endangered Species Act rulemaking — {title_n}", fontsize=12)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("campaign_structure.png")
print("-> campaign_structure.png")
