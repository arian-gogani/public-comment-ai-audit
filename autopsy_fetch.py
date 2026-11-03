#!/usr/bin/env python3
"""Pull ALL text comments for one docket from the Mirrulations mirror (threaded)."""
import json, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree

S3 = "https://mirrulations.s3.amazonaws.com/"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

def s3_list(prefix, max_keys=1000, token=None):
    q = {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)}
    if token: q["continuation-token"] = token
    with urllib.request.urlopen(S3 + "?" + urllib.parse.urlencode(q), timeout=30) as r:
        root = ElementTree.parse(r).getroot()
    keys = [e.find(NS+"Key").text for e in root.findall(NS+"Contents")]
    tok = root.find(NS+"NextContinuationToken")
    return keys, (tok.text if tok is not None else None)

def pull(key, retries=3):
    for _ in range(retries):
        try:
            with urllib.request.urlopen(S3 + urllib.parse.quote(key), timeout=30) as r:
                d = json.load(r)["data"]["attributes"]
            return {"id": key.split("/")[-1][:-5],
                    "text": (d.get("comment") or "").strip(),
                    "posted": d.get("postedDate", ""),
                    "received": d.get("receiveDate", ""),
                    "title": d.get("title", ""),
                    "org": d.get("organization", ""),
                    "state": d.get("stateProvinceRegion", ""),
                    "attach": d.get("pageCount") is not None}
        except Exception:
            time.sleep(1)
    return None

def main(agency, docket, cap=45000):
    pref = f"raw-data/{agency}/{docket}/text-{docket}/comments/"
    keys, token = [], None
    while True:
        ks, token = s3_list(pref, token=token)
        keys += [k for k in ks if "(" not in k]
        print(f"  listed {len(keys)}", flush=True)
        if not token or len(keys) >= cap: break
    keys = keys[:cap]
    print(f"{docket}: pulling {len(keys)} comment files", flush=True)
    t0, done, out = time.time(), 0, []
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = [ex.submit(pull, k) for k in keys]
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r: out.append(r)
            if done % 2000 == 0:
                rate = done/(time.time()-t0)
                print(f"  {done}/{len(keys)} ({rate:.0f}/s, eta {(len(keys)-done)/rate/60:.0f}m)", flush=True)
    fn = f"autopsy_{docket}.jsonl"
    with open(fn, "w") as f:
        for r in out: f.write(json.dumps(r) + "\n")
    n_text = sum(1 for r in out if len(r["text"].split()) >= 5)
    print(f"DONE {len(out)} records ({n_text} with text) -> {fn} in {(time.time()-t0)/60:.1f}m", flush=True)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "FWS",
         sys.argv[2] if len(sys.argv) > 2 else "FWS-HQ-ES-2025-0039")
