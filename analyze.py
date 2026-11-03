#!/usr/bin/env python3
"""Measure the LLM-fingerprint rate shift across the ChatGPT boundary.

Calibration logic: pre-ChatGPT comments (posted <= 2022-11) are guaranteed
human. We set the 'AI-suspect' threshold from the pre-ChatGPT distribution
(e.g. 99th percentile) so the human false-positive rate is fixed by
construction, then report how the suspect rate rises post-ChatGPT. This is the
same difference-in-difference logic used by the published paper-corpus studies.
"""
import json, sys, math, statistics
from detector import score

def load(path="comments_sample.jsonl"):
    rows = [json.loads(l) for l in open(path)]
    for r in rows:
        r["s"] = score(r["text"])
    return rows

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0, 0)
    p = k/n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return p, max(0, c-h), min(1, c+h)

def main(path="comments_sample.jsonl"):
    rows = load(path)
    pre = [r for r in rows if r["window"] == "pre_chatgpt"]
    post = [r for r in rows if r["window"] == "post_chatgpt"]
    print(f"loaded {len(rows)} comments: {len(pre)} pre-ChatGPT, {len(post)} post-ChatGPT\n")
    if not pre or not post:
        print("need both windows populated"); return

    pre_rates = sorted(r["s"]["fp_rate_per_1k"] for r in pre)
    # threshold = 90th percentile of human (pre) distribution -> ~10% human FPR by design
    import numpy as np
    thr = float(np.percentile(pre_rates, 90)) if len(pre_rates) >= 5 else max(pre_rates, default=0) + 1
    print(f"human (pre-ChatGPT) fp_rate/1k: median={statistics.median(pre_rates):.1f} "
          f"mean={statistics.mean(pre_rates):.1f} 90th-pctile(threshold)={thr:.1f}")
    post_rates = [r["s"]["fp_rate_per_1k"] for r in post]
    print(f"post-ChatGPT fp_rate/1k:        median={statistics.median(post_rates):.1f} "
          f"mean={statistics.mean(post_rates):.1f}")

    k_pre = sum(1 for r in pre if r["s"]["fp_rate_per_1k"] > thr)
    k_post = sum(1 for r in post if r["s"]["fp_rate_per_1k"] > thr)
    p_pre, lo_pre, hi_pre = wilson(k_pre, len(pre))
    p_post, lo_post, hi_post = wilson(k_post, len(post))
    print(f"\nsuspect rate (fp_rate > {thr:.1f}/1k):")
    print(f"  pre-ChatGPT:  {k_pre}/{len(pre)} = {p_pre*100:.0f}%  [{lo_pre*100:.0f}-{hi_pre*100:.0f}%]  (by design ~10%)")
    print(f"  post-ChatGPT: {k_post}/{len(post)} = {p_post*100:.0f}%  [{lo_post*100:.0f}-{hi_post*100:.0f}%]")

    # two-proportion z-test
    pooled = (k_pre + k_post) / (len(pre) + len(post))
    se = math.sqrt(pooled*(1-pooled)*(1/len(pre) + 1/len(post)))
    z = (p_post - p_pre)/se if se > 0 else 0
    print(f"\n  difference: {(p_post-p_pre)*100:+.0f} pp,  two-proportion z = {z:.1f}")
    print(f"  => {'SIGNIFICANT rise in AI-fingerprinted comments post-ChatGPT' if z > 2 else 'no significant shift in this sample (need more data)'}")

    # show the most AI-suspect post comments
    sus = sorted(post, key=lambda r: -r["s"]["fp_rate_per_1k"])[:3]
    print("\nmost AI-suspect post-ChatGPT comments:")
    for r in sus:
        print(f"  [{r['s']['fp_rate_per_1k']:.0f}/1k] {r['docket']} — {r['text'][:110].strip()}...")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "comments_sample.jsonl")
