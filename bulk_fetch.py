#!/usr/bin/env python3
"""Bulk comment sampler from the Mirrulations open-data S3 mirror (no key needed).

Strategy: docket IDs encode the filing year (EPA-HQ-OAR-2024-0004, FDA-2021-N-1234),
so we target PRE-ChatGPT dockets (2019-2021) and POST dockets (2023-2025) across
several agencies, sample dockets per era, list their comment JSONs, and pull text
+ postedDate. Output: bulk_comments.jsonl
"""
import json, re, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree

S3 = "https://mirrulations.s3.amazonaws.com/"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

def s3_list(prefix, delimiter=None, max_keys=1000, token=None):
    q = {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)}
    if delimiter: q["delimiter"] = delimiter
    if token: q["continuation-token"] = token
    url = S3 + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=30) as r:
        tree = ElementTree.parse(r)
    root = tree.getroot()
    prefixes = [e.find(NS+"Prefix").text for e in root.findall(NS+"CommonPrefixes")]
    keys = [e.find(NS+"Key").text for e in root.findall(NS+"Contents")]
    tok = root.find(NS+"NextContinuationToken")
    return prefixes, keys, (tok.text if tok is not None else None)

def fetch_json(key):
    with urllib.request.urlopen(S3 + urllib.parse.quote(key), timeout=30) as r:
        return json.load(r)

# agency -> prefix patterns per year (docket-ID styles differ per agency)
AGENCY_PATTERNS = {
    "EPA":  lambda y: f"raw-data/EPA/EPA-HQ-OAR-{y}",
    "FDA":  lambda y: f"raw-data/FDA/FDA-{y}",
    "CMS":  lambda y: f"raw-data/CMS/CMS-{y}",
    "DEA":  lambda y: f"raw-data/DEA/DEA-{y}",
    "OSHA": lambda y: f"raw-data/OSHA/OSHA-{y}",
    "FWS":  lambda y: f"raw-data/FWS/FWS-HQ-ES-{y}",
}
PRE_YEARS = [2019, 2020, 2021]
POST_YEARS = [2023, 2024, 2025]
DOCKETS_PER_CELL = 6          # dockets sampled per (agency, year)
COMMENTS_PER_DOCKET = 60      # comment files pulled per docket

def sample_dockets(agency, year, n):
    pref = AGENCY_PATTERNS[agency](year)
    prefixes, _, _ = s3_list(pref, delimiter="/", max_keys=200)
    # spread through list rather than taking the first n (less topical clustering)
    if len(prefixes) > n:
        step = len(prefixes) // n
        prefixes = prefixes[::step][:n]
    return prefixes

def docket_comment_keys(docket_prefix, cap):
    docket = docket_prefix.rstrip("/").split("/")[-1]
    cpref = f"{docket_prefix}text-{docket}/comments/"
    keys, token, out = [], None, []
    while len(out) < cap:
        _, ks, token = s3_list(cpref, max_keys=min(1000, cap*2), token=token)
        # skip "(1).json" duplicates
        out += [k for k in ks if "(" not in k]
        if not token or not ks: break
    return out[:cap]

def pull_comment(key):
    try:
        d = fetch_json(key)["data"]["attributes"]
        txt = (d.get("comment") or "").strip()
        if len(txt.split()) < 25 or txt.lower().startswith("see attached"):
            return None
        return {"id": key.split("/")[-1][:-5], "text": txt,
                "posted": d.get("postedDate", ""), "docket": d.get("docketId", ""),
                "agency": d.get("agencyId", "")}
    except Exception:
        return None

def main():
    rows, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=16) as ex:
        for era, years in (("pre", PRE_YEARS), ("post", POST_YEARS)):
            for agency in AGENCY_PATTERNS:
                for y in years:
                    try:
                        dockets = sample_dockets(agency, y, DOCKETS_PER_CELL)
                    except Exception as e:
                        print(f"  {agency} {y}: list failed {e}", flush=True); continue
                    keys = []
                    for dp in dockets:
                        try: keys += docket_comment_keys(dp, COMMENTS_PER_DOCKET)
                        except Exception: pass
                    got = 0
                    for fut in as_completed([ex.submit(pull_comment, k) for k in keys]):
                        r = fut.result()
                        if r:
                            r["era"] = era; rows.append(r); got += 1
                    print(f"  {era} {agency} {y}: {len(dockets)} dockets, {len(keys)} files, {got} usable ({time.time()-t0:.0f}s)", flush=True)
    with open("bulk_comments.jsonl", "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    import collections
    print(f"\nTOTAL {len(rows)} usable comments -> bulk_comments.jsonl")
    print(collections.Counter(r["era"] for r in rows))
    print(collections.Counter(r["agency"] for r in rows).most_common())

if __name__ == "__main__":
    main()
