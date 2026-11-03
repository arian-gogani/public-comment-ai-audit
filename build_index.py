#!/usr/bin/env python3
"""Build a full docket index: agency -> year -> [docket_ids].

Needed because big agencies (FDA 65k, FAA 52k) exceed one S3 list page, so naive
listing silently samples only the alphabetically-first dockets. This paginates
fully, once, and caches to docket_index.json for unbiased stratified sampling.
"""
import json, re, time, urllib.parse, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree

S3 = "https://mirrulations.s3.amazonaws.com/"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
YEAR_RE = re.compile(r"-((?:19|20)\d{2})-")

def s3_list(prefix, token=None):
    q = {"list-type": "2", "prefix": prefix, "delimiter": "/", "max-keys": "1000"}
    if token: q["continuation-token"] = token
    for _ in range(3):
        try:
            with urllib.request.urlopen(S3 + "?" + urllib.parse.urlencode(q), timeout=40) as r:
                root = ElementTree.parse(r).getroot()
            pres = [e.find(NS+"Prefix").text for e in root.findall(NS+"CommonPrefixes")]
            tok = root.find(NS+"NextContinuationToken")
            return pres, (tok.text if tok is not None else None)
        except Exception:
            time.sleep(1.5)
    return [], None

def index_agency(a):
    out, token = [], None
    while True:
        pres, token = s3_list(f"raw-data/{a}/", token)
        out += [p.rstrip("/").split("/")[-1] for p in pres]
        if not token: break
    by_year = collections.defaultdict(list)
    for d in out:
        m = YEAR_RE.search(d)
        if m: by_year[m.group(1)].append(d)
    return a, dict(by_year)

if __name__ == "__main__":
    cmap = json.load(open("corpus_map.json"))
    ags = list(cmap["agencies"].keys())
    idx, t0, done = {}, time.time(), 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for fut in as_completed([ex.submit(index_agency, a) for a in ags]):
            a, by_year = fut.result()
            idx[a] = by_year
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(ags)} ({time.time()-t0:.0f}s)", flush=True)
    total = sum(len(v) for ag in idx.values() for v in ag.values())
    json.dump(idx, open("docket_index.json", "w"))
    print(f"indexed {total:,} dated dockets across {len(idx)} agencies in {time.time()-t0:.0f}s")
    print("-> docket_index.json")
