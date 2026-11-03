#!/usr/bin/env python3
"""National stratified sample v2 — flat parallel docket queue.

v1 lesson: most dockets hold zero public comments, so random docket draws mostly
miss. Fix: (1) draw MANY candidate dockets per stratum, (2) probe them all in
parallel (one cheap S3 list each) to find comment-bearing ones, (3) fetch
comments only from those, capped per docket. Weighting info (docket comment
totals) is retained so national estimates stay unbiased.
"""
import json, random, re, sys, time, hashlib, collections, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree

S3 = "https://mirrulations.s3.amazonaws.com/"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
YEARS = [str(y) for y in range(2005, 2027)]
CANDIDATES_PER_CELL = int(sys.argv[1]) if len(sys.argv) > 1 else 40
COMMENTS_PER_DOCKET = 100
MIN_WORDS = 15

def s3_list(prefix, token=None, delimiter=None):
    q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
    if delimiter: q["delimiter"] = delimiter
    if token: q["continuation-token"] = token
    for _ in range(2):
        try:
            with urllib.request.urlopen(S3 + "?" + urllib.parse.urlencode(q), timeout=30) as r:
                root = ElementTree.parse(r).getroot()
            keys = [e.find(NS+"Key").text for e in root.findall(NS+"Contents")]
            tok = root.find(NS+"NextContinuationToken")
            return keys, (tok.text if tok is not None else None)
        except Exception:
            time.sleep(1)
    return [], None

def probe(item):
    """Return (agency, year, docket, comment_keys) — cheap single list call."""
    a, y, d = item
    keys, _ = s3_list(f"raw-data/{a}/{d}/text-{d}/comments/")
    return (a, y, d, [k for k in keys if "(" not in k])

def pull(key):
    try:
        with urllib.request.urlopen(S3 + urllib.parse.quote(key), timeout=25) as r:
            at = json.load(r)["data"]["attributes"]
        t = (at.get("comment") or "").strip()
        if len(t.split()) < MIN_WORDS or t.lower().startswith("see attached"):
            return None
        return {"text": t, "posted": at.get("postedDate", ""),
                "docket": at.get("docketId", ""), "agency": at.get("agencyId", "")}
    except Exception:
        return None

def norm_hash(t):
    return hashlib.md5(re.sub(r"\s+", " ", t.lower()).strip().encode()).hexdigest()

def main():
    IDX = json.load(open("docket_index.json"))
    cmap = json.load(open("corpus_map.json"))["agencies"]
    rng = random.Random(42)
    by_year = collections.defaultdict(list)
    for a, v in cmap.items():
        for y, n in v["by_year"].items():
            if y in YEARS and n >= 3: by_year[y].append((a, n))
    # candidate docket queue
    queue = []
    for y in YEARS:
        opts = sorted(by_year.get(y, []), key=lambda t: -t[1])
        chosen = opts[:5] + (rng.sample(opts[5:], min(5, len(opts[5:]))) if len(opts) > 5 else [])
        for a, _ in chosen:
            ds = IDX.get(a, {}).get(y, [])
            if not ds: continue
            pick = random.Random(hash((a, y)) & 0xffff).sample(ds, min(CANDIDATES_PER_CELL, len(ds)))
            queue += [(a, y, d) for d in pick]
    print(f"probing {len(queue):,} candidate dockets", flush=True)

    t0 = time.time()
    live = []
    with ThreadPoolExecutor(max_workers=40) as ex:
        done = 0
        for fut in as_completed([ex.submit(probe, it) for it in queue]):
            a, y, d, keys = fut.result()
            done += 1
            if keys: live.append((a, y, d, keys))
            if done % 500 == 0:
                print(f"  probed {done}/{len(queue)} | {len(live)} with comments | {time.time()-t0:.0f}s", flush=True)
    print(f"\n{len(live):,} comment-bearing dockets ({len(live)/len(queue)*100:.1f}% hit rate) in {time.time()-t0:.0f}s", flush=True)

    # fetch
    fetch_jobs = []
    for a, y, d, keys in live:
        sel = keys if len(keys) <= COMMENTS_PER_DOCKET else \
              random.Random(hash(d) & 0xffff).sample(keys, COMMENTS_PER_DOCKET)
        for k in sel: fetch_jobs.append((a, y, d, len(keys), k))
    print(f"fetching {len(fetch_jobs):,} comments", flush=True)

    out = open("national_sample.jsonl", "w")
    n = 0
    t1 = time.time()
    with ThreadPoolExecutor(max_workers=48) as ex:
        futs = {ex.submit(pull, j[4]): j for j in fetch_jobs}
        done = 0
        for fut in as_completed(futs):
            a, y, d, tot, _ = futs[fut]
            r = fut.result(); done += 1
            if r:
                r.update({"stratum_year": y, "stratum_agency": a,
                          "docket_total_comments": tot, "h": norm_hash(r["text"])})
                out.write(json.dumps(r) + "\n"); n += 1
            if done % 5000 == 0:
                out.flush()
                rate = done / (time.time()-t1)
                print(f"  {done:,}/{len(fetch_jobs):,} | {n:,} usable | {rate:.0f}/s | eta {(len(fetch_jobs)-done)/rate/60:.0f}m", flush=True)
    out.close()
    print(f"\nDONE {n:,} usable comments in {(time.time()-t0)/60:.1f}m -> national_sample.jsonl")

if __name__ == "__main__":
    main()
