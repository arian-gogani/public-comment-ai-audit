#!/usr/bin/env python3
"""Milestone 1: survey the full Mirrulations corpus.

We cannot download hundreds of millions of comments. So first we map the terrain:
how many agencies, how many dockets, what years they span. That tells us how to
draw a stratified sample that supports NATIONAL estimates (agency x year cells)
rather than one-fight anecdotes.

Cheap by design: lists docket prefixes only (no comment files), parses the year
out of docket IDs, writes corpus_map.json.
"""
import json, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree

S3 = "https://mirrulations.s3.amazonaws.com/"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
YEAR_RE = re.compile(r"-((?:19|20)\d{2})-")

def s3_list(prefix, delimiter="/", max_keys=1000, token=None):
    q = {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)}
    if delimiter: q["delimiter"] = delimiter
    if token: q["continuation-token"] = token
    url = S3 + "?" + urllib.parse.urlencode(q)
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                root = ElementTree.parse(r).getroot()
            pres = [e.find(NS+"Prefix").text for e in root.findall(NS+"CommonPrefixes")]
            keys = [e.find(NS+"Key").text for e in root.findall(NS+"Contents")]
            tok = root.find(NS+"NextContinuationToken")
            return pres, keys, (tok.text if tok is not None else None)
        except Exception:
            time.sleep(2)
    return [], [], None

def agencies():
    pres, _, tok = s3_list("raw-data/")
    out = [p.split("/")[1] for p in pres]
    while tok:
        pres, _, tok = s3_list("raw-data/", token=tok)
        out += [p.split("/")[1] for p in pres]
    return sorted(set(out))

def dockets_for(agency):
    """All docket ids for one agency (paginated)."""
    out, token = [], None
    while True:
        pres, _, token = s3_list(f"raw-data/{agency}/", token=token)
        out += [p.rstrip("/").split("/")[-1] for p in pres]
        if not token: break
    return out

def main():
    t0 = time.time()
    ags = agencies()
    print(f"{len(ags)} agencies", flush=True)
    corpus = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(dockets_for, a): a for a in ags}
        done = 0
        for fut in as_completed(futs):
            a = futs[fut]
            try: ds = fut.result()
            except Exception: ds = []
            years = {}
            for d in ds:
                m = YEAR_RE.search(d)
                y = m.group(1) if m else "unknown"
                years[y] = years.get(y, 0) + 1
            corpus[a] = {"n_dockets": len(ds), "by_year": years}
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(ags)} agencies mapped ({time.time()-t0:.0f}s)", flush=True)
    total = sum(v["n_dockets"] for v in corpus.values())
    print(f"\nTOTAL DOCKETS: {total:,} across {len(ags)} agencies ({time.time()-t0:.0f}s)")
    top = sorted(corpus.items(), key=lambda kv: -kv[1]["n_dockets"])[:20]
    print("\ntop agencies by docket count:")
    for a, v in top:
        yrs = [y for y in v["by_year"] if y != "unknown"]
        span = f"{min(yrs)}-{max(yrs)}" if yrs else "?"
        print(f"  {a:10s} {v['n_dockets']:7,d} dockets   {span}")
    allyears = {}
    for v in corpus.values():
        for y, n in v["by_year"].items():
            allyears[y] = allyears.get(y, 0) + n
    print("\ndockets per year (corpus-wide):")
    for y in sorted(k for k in allyears if k != "unknown"):
        print(f"  {y}: {allyears[y]:,}")
    json.dump({"agencies": corpus, "total_dockets": total, "by_year": allyears},
              open("corpus_map.json", "w"), indent=1)
    print("\n-> corpus_map.json")

if __name__ == "__main__":
    main()
