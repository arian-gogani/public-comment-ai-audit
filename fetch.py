#!/usr/bin/env python3
"""Fetch public comments (with full text + dates) from regulations.gov.
Uses stdlib only. DEMO_KEY works but is rate-limited; set REGS_API_KEY env for
a free api.data.gov key to scale to millions."""
import os, json, time, urllib.parse, urllib.request, sys

API = "https://api.regulations.gov/v4"
KEY = os.environ.get("REGS_API_KEY", "DEMO_KEY")

def _get(path, params, retries=3):
    params = dict(params); params["api_key"] = KEY
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  rate-limited, sleeping 20s...", file=sys.stderr); time.sleep(20); continue
            raise
    raise RuntimeError("retries exhausted")

def search_comment_ids(term=None, date_ge=None, date_le=None, want=20):
    """Return up to `want` comment ids matching filters, posted in [date_ge, date_le]."""
    ids, page = [], 1
    while len(ids) < want:
        params = {"page[size]": 50, "page[number]": page, "sort": "postedDate"}
        if term: params["filter[searchTerm]"] = term
        if date_ge: params["filter[postedDate][ge]"] = date_ge
        if date_le: params["filter[postedDate][le]"] = date_le
        d = _get("comments", params)
        batch = d.get("data", [])
        if not batch: break
        ids += [c["id"] for c in batch]
        if not d.get("meta", {}).get("hasNextPage"): break
        page += 1
    return ids[:want]

def comment_text(cid):
    """Return (text, postedDate, docketId, organization) for one comment."""
    d = _get(f"comments/{cid}", {})["data"]["attributes"]
    return d.get("comment") or "", d.get("postedDate"), d.get("docketId"), d.get("organization")

def collect(term, date_ge, date_le, want, label):
    ids = search_comment_ids(term, date_ge, date_le, want)
    out = []
    for i, cid in enumerate(ids):
        try:
            txt, posted, docket, org = comment_text(cid)
        except Exception as e:
            print(f"  skip {cid}: {e}", file=sys.stderr); continue
        if txt and len(txt.split()) >= 25:  # skip trivially short / attachment-only
            out.append({"id": cid, "text": txt, "posted": posted, "docket": docket,
                        "org": org, "window": label})
        if (i+1) % 10 == 0: print(f"  {label}: {i+1}/{len(ids)} fetched", file=sys.stderr)
    return out

if __name__ == "__main__":
    term = sys.argv[1] if len(sys.argv) > 1 else "climate"
    want = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    data = []
    data += collect(term, "2020-01-01", "2021-12-31", want, "pre_chatgpt")
    data += collect(term, "2024-06-01", "2025-12-31", want, "post_chatgpt")
    with open("comments_sample.jsonl", "w") as f:
        for r in data: f.write(json.dumps(r) + "\n")
    print(f"saved {len(data)} comments to comments_sample.jsonl")
