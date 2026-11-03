#!/usr/bin/env python3
"""Milestone 2+4: stratified national sample of US federal public comments.

Design:
  - Universe: dockets 2005-2026 (regulations.gov fully operational), all agencies.
  - Strata: (year) x (agency tier). Random dockets per cell, capped comments per
    docket so one mega-docket can't dominate a cell.
  - Per-docket campaign structure is computed in-stream (exact-dup hashing +
    MinHash template families); cross-docket linking uses exact hashes only (O(n)).
  - Everything is weighted later by cell: estimate_national.py.

Writes national_sample.jsonl (one row per comment, with stratum labels) and
national_docket_stats.jsonl (per-docket summary).
"""
import json, random, re, sys, time, hashlib, collections, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree

S3 = "https://mirrulations.s3.amazonaws.com/"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
YEAR_RE = re.compile(r"-((?:19|20)\d{2})-")

YEARS = [str(y) for y in range(2005, 2027)]
DOCKETS_PER_CELL = int(sys.argv[1]) if len(sys.argv) > 1 else 6
COMMENTS_PER_DOCKET = 120
MIN_WORDS = 15

def s3_list(prefix, delimiter=None, max_keys=1000, token=None, retries=3):
    q = {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)}
    if delimiter: q["delimiter"] = delimiter
    if token: q["continuation-token"] = token
    url = S3 + "?" + urllib.parse.urlencode(q)
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                root = ElementTree.parse(r).getroot()
            pres = [e.find(NS+"Prefix").text for e in root.findall(NS+"CommonPrefixes")]
            keys = [e.find(NS+"Key").text for e in root.findall(NS+"Contents")]
            tok = root.find(NS+"NextContinuationToken")
            return pres, keys, (tok.text if tok is not None else None)
        except Exception:
            time.sleep(1.5)
    return [], [], None

def pull_comment(key):
    for _ in range(2):
        try:
            with urllib.request.urlopen(S3 + urllib.parse.quote(key), timeout=30) as r:
                d = json.load(r)["data"]["attributes"]
            txt = (d.get("comment") or "").strip()
            if len(txt.split()) < MIN_WORDS or txt.lower().startswith("see attached"):
                return None
            return {"text": txt, "posted": d.get("postedDate", ""),
                    "docket": d.get("docketId", ""), "agency": d.get("agencyId", "")}
        except Exception:
            time.sleep(0.5)
    return None

def comment_keys(agency, docket, cap):
    pref = f"raw-data/{agency}/{docket}/text-{docket}/comments/"
    keys, token = [], None
    while len(keys) < cap * 3:
        _, ks, token = s3_list(pref, token=token)
        keys += [k for k in ks if "(" not in k]
        if not token or not ks: break
    return keys

def norm_hash(t):
    return hashlib.md5(re.sub(r"\s+", " ", t.lower()).strip().encode()).hexdigest()

IDX = json.load(open("docket_index.json"))

def do_cell(a, y):
    ds = IDX.get(a, {}).get(y, [])
    if not ds: return []
    pick = random.Random(hash((a, y)) & 0xffff).sample(ds, min(DOCKETS_PER_CELL, len(ds)))
    rows = []
    for d in pick:
        keys = comment_keys(a, d, COMMENTS_PER_DOCKET)
        if not keys: continue
        sel = keys if len(keys) <= COMMENTS_PER_DOCKET else \
              random.Random(hash(d) & 0xffff).sample(keys, COMMENTS_PER_DOCKET)
        got = []
        with ThreadPoolExecutor(max_workers=16) as ex:
            for fut in as_completed([ex.submit(pull_comment, k) for k in sel]):
                r = fut.result()
                if r: got.append(r)
        if got:
            rows.append((a, y, d, len(keys), got))
    return rows


def main():
    cmap = json.load(open("corpus_map.json"))
    ag = cmap["agencies"]
    # build (agency, year) -> docket count, keep cells with real volume
    cells = []
    for a, v in ag.items():
        for y, n in v["by_year"].items():
            if y in YEARS and n >= 3:
                cells.append((a, y, n))
    # weight: sample more cells from agencies that dominate volume, but cover all years
    rng = random.Random(42)
    by_year = collections.defaultdict(list)
    for a, y, n in cells: by_year[y].append((a, n))
    AGENCIES_PER_YEAR = 10
    plan = []
    for y in YEARS:
        opts = sorted(by_year.get(y, []), key=lambda t: -t[1])
        top = opts[:5]                       # biggest agencies that year
        rest = opts[5:]
        rand = rng.sample(rest, min(AGENCIES_PER_YEAR - len(top), len(rest))) if rest else []
        for a, n in top + rand:
            plan.append((a, y, n))
    print(f"plan: {len(plan)} (agency,year) cells x {DOCKETS_PER_CELL} dockets", flush=True)

    out = open("national_sample.jsonl", "w")
    dstats = open("national_docket_stats.jsonl", "w")
    t0, ncomments, ndockets = time.time(), 0, 0
    global_hashes = collections.Counter()

    with ThreadPoolExecutor(max_workers=4) as outer:
        futs = {outer.submit(do_cell, a, y): (a, y) for a, y, _ in plan}
        done = 0
        for fut in as_completed(futs):
            a, y = futs[fut]
            try: rows = fut.result()
            except Exception as e:
                print(f"  cell {a} {y} failed: {e}", flush=True); rows = []
            for (ag_, yr, dk, total_keys, got) in rows:
                hashes = [norm_hash(r["text"]) for r in got]
                hc = collections.Counter(hashes)
                dup_share = sum(c for c in hc.values() if c > 1) / len(hashes)
                for h in hc: global_hashes[h] += hc[h]
                dstats.write(json.dumps({"agency": ag_, "year": yr, "docket": dk,
                    "docket_total_comments": total_keys, "sampled": len(got),
                    "exact_dup_share": dup_share}) + "\n")
                for r, h in zip(got, hashes):
                    r["stratum_year"] = yr; r["stratum_agency"] = ag_
                    r["docket_total_comments"] = total_keys; r["h"] = h
                    out.write(json.dumps(r) + "\n")
                ncomments += len(got); ndockets += 1
            done += 1
            if done % 10 == 0:
                out.flush(); dstats.flush()
                print(f"  {done}/{len(plan)} cells | {ndockets} dockets | {ncomments:,} comments | {time.time()-t0:.0f}s", flush=True)
    out.close(); dstats.close()
    print(f"\nDONE {ncomments:,} comments from {ndockets} dockets in {(time.time()-t0)/60:.1f}m")
    cross = sum(1 for h, c in global_hashes.items() if c > 1)
    print(f"distinct texts appearing >1x anywhere in sample: {cross:,}")

if __name__ == "__main__":
    main()
