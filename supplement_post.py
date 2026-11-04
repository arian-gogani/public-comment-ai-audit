#!/usr/bin/env python3
"""Targeted supplement: boost post-2023 coverage in agencies that already have
strong pre-2022 data, so the within-agency (confound-free) test has many more
agencies instead of 4. Appends to national_sample.jsonl."""
import json, random, collections, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import national_sample2 as ns

IDX = json.load(open("docket_index.json"))
rows = [json.loads(l) for l in open("national_sample.jsonl")]
pre = collections.Counter()
for r in rows:
    if r["stratum_year"] <= "2022": pre[r["stratum_agency"]] += 1
targets = [a for a, n in pre.items() if n >= 250]
print(f"{len(targets)} agencies with >=250 pre-2022 comments: {targets}", flush=True)

POST = ["2023", "2024", "2025", "2026"]
queue = []
for a in targets:
    for y in POST:
        ds = IDX.get(a, {}).get(y, [])
        if not ds: continue
        pick = random.Random(hash((a, y, "sup")) & 0xffff).sample(ds, min(200, len(ds)))
        queue += [(a, y, d) for d in pick]
print(f"probing {len(queue):,} post-2023 dockets", flush=True)

t0 = time.time(); live = []
with ThreadPoolExecutor(max_workers=40) as ex:
    done = 0
    for fut in as_completed([ex.submit(ns.probe, it) for it in queue]):
        a, y, d, keys = fut.result(); done += 1
        if keys: live.append((a, y, d, keys))
        if done % 1000 == 0:
            print(f"  probed {done}/{len(queue)} | {len(live)} live | {time.time()-t0:.0f}s", flush=True)
print(f"{len(live)} comment-bearing post-2023 dockets", flush=True)

jobs = []
for a, y, d, keys in live:
    sel = keys if len(keys) <= 100 else random.Random(hash(d) & 0xffff).sample(keys, 100)
    for k in sel: jobs.append((a, y, d, len(keys), k))
print(f"fetching {len(jobs):,}", flush=True)

out = open("national_sample.jsonl", "a"); n = 0
with ThreadPoolExecutor(max_workers=48) as ex:
    futs = {ex.submit(ns.pull, j[4]): j for j in jobs}
    done = 0
    for fut in as_completed(futs):
        a, y, d, tot, _ = futs[fut]
        r = fut.result(); done += 1
        if r:
            r.update({"stratum_year": y, "stratum_agency": a,
                      "docket_total_comments": tot, "h": ns.norm_hash(r["text"])})
            out.write(json.dumps(r) + "\n"); n += 1
        if done % 5000 == 0:
            out.flush(); print(f"  {done:,}/{len(jobs):,} | {n:,} usable", flush=True)
out.close()
print(f"\nADDED {n:,} post-2023 comments in {(time.time()-t0)/60:.1f}m")
