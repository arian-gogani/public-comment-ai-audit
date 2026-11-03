#!/usr/bin/env python3
"""Comment-family forensics: exact dups, template families, and PARAPHRASE RINGS
(LLM-era astroturf signature: same skeleton, different skin).

Tiers:
  T1 exact duplicates        (normalized hash)
  T2 template families       (MinHash/LSH on 3-word shingles, Jaccard >= 0.5)
  T3 paraphrase rings        (SimHash-bucketed TF-IDF cosine >= threshold,
                              threshold VALIDATED on planted paraphrase rings)
Stdlib + numpy only; scales to ~50k comments.
"""
import json, re, math, random, hashlib, collections, itertools
import numpy as np

WORD = re.compile(r"[a-z][a-z'-]*")
STOP = set("""the a an and or of to in for on with is are was were be been being it its this
that these those i we you they he she as at by from not no do does did have has had will
would can could should may might must about against between into through during before
after above below up down out off over under again further then once here there when where
why how all any both each few more most other some such only own same so than too very s t
just don now my your our their his her them us me""".split())

def norm(t):
    return re.sub(r"\s+", " ", (t or "").lower()).strip()

def toks(t):
    return [w for w in WORD.findall(norm(t))]

def content_toks(t):
    return [w for w in toks(t) if w not in STOP]

# ---------- T1: exact ----------
def exact_key(t):
    return hashlib.md5(norm(t).encode()).hexdigest()

# ---------- T2: MinHash over 3-shingles ----------
def minhash_sig(t, n_hash=48):
    ws = toks(t)
    sh = {" ".join(ws[i:i+3]) for i in range(len(ws)-2)} or {" ".join(ws)}
    hs = []
    for seed in range(n_hash):
        m = min((hash((seed, s)) & 0xffffffff) for s in sh)
        hs.append(m)
    return hs

def lsh_candidates(sigs, bands=24, rows=2):
    cand = set()
    for b in range(bands):
        buckets = collections.defaultdict(list)
        for i, s in enumerate(sigs):
            buckets[tuple(s[b*rows:(b+1)*rows])].append(i)
        for ids in buckets.values():
            if 1 < len(ids) <= 400:
                for a, c in itertools.combinations(ids, 2):
                    cand.add((a, c))
    return cand

def jaccard3(t1, t2):
    w1, w2 = toks(t1), toks(t2)
    s1 = {" ".join(w1[i:i+3]) for i in range(len(w1)-2)}
    s2 = {" ".join(w2[i:i+3]) for i in range(len(w2)-2)}
    if not s1 or not s2: return 0.0
    return len(s1 & s2) / len(s1 | s2)

# ---------- T3: TF-IDF cosine with SimHash bucketing ----------
def build_tfidf(texts):
    df = collections.Counter()
    docs = []
    for t in texts:
        c = collections.Counter(content_toks(t))
        docs.append(c)
        for w in c: df[w] += 1
    n = len(texts)
    idf = {w: math.log(n / (1 + d)) for w, d in df.items()}
    vecs = []
    for c in docs:
        v = {w: (1 + math.log(cnt)) * idf.get(w, 0) for w, cnt in c.items()}
        nrm = math.sqrt(sum(x*x for x in v.values())) or 1
        vecs.append({w: x/nrm for w, x in v.items()})
    return vecs, idf

def simhash(vec, planes):
    """64-bit sign signature of random projections."""
    bits = 0
    for j, pl in enumerate(planes):
        s = sum(pl.get(w, 0) * x for w, x in vec.items())
        if s >= 0: bits |= (1 << j)
    return bits

def make_planes(idf, n_planes=64, seed=7):
    rng = random.Random(seed)
    planes = []
    words = list(idf)
    for _ in range(n_planes):
        planes.append({w: rng.gauss(0, 1) for w in rng.sample(words, min(len(words), 4000))})
    return planes

def cos(v1, v2):
    if len(v2) < len(v1): v1, v2 = v2, v1
    return sum(x * v2.get(w, 0) for w, x in v1.items())

def cluster_pairs(n, pairs):
    """union-find"""
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    groups = collections.defaultdict(list)
    for i in range(n): groups[find(i)].append(i)
    return [g for g in groups.values() if len(g) > 1]

def analyze(texts, cos_thr, verbose=True):
    """Full tiered clustering. Returns dict with tiers and cluster assignments."""
    n = len(texts)
    # T1
    byk = collections.defaultdict(list)
    for i, t in enumerate(texts): byk[exact_key(t)].append(i)
    t1 = [g for g in byk.values() if len(g) > 1]
    t1_members = {i for g in t1 for i in g}
    # T2 on unique representatives
    reps = [g[0] for g in byk.values()]
    sigs = {i: minhash_sig(texts[i]) for i in reps}
    cands = lsh_candidates([sigs[i] for i in reps])
    repl = list(reps)
    t2_pairs, t3_cand = [], []
    for a, b in cands:
        i, j = repl[a], repl[b]
        jc = jaccard3(texts[i], texts[j])
        if jc >= 0.5: t2_pairs.append((a, b))
        elif jc >= 0.05: t3_cand.append((a, b))
    t2 = [[repl[i] for i in g] for g in cluster_pairs(len(repl), t2_pairs)]
    t2_members = {i for g in t2 for i in g}
    # T3: tf-idf cosine on remaining reps; candidates = LSH leftovers + simhash buckets
    vecs, idf = build_tfidf([texts[i] for i in repl])
    planes = make_planes(idf)
    sh = [simhash(v, planes) for v in vecs]
    buckets = collections.defaultdict(list)
    for i, h in enumerate(sh):
        for band in range(8):
            buckets[(band, (h >> (band*8)) & 0xff)].append(i)
    cand3 = set(t3_cand)
    for ids in buckets.values():
        if 1 < len(ids) <= 800:
            for a, b in itertools.combinations(ids, 2): cand3.add((a, b))
    # rare-word inverted index: pairs sharing any low-df content word
    posting = collections.defaultdict(list)
    for ri, v in enumerate(vecs):
        for w in v: posting[w].append(ri)
    nrep = len(repl)
    for w, ids in posting.items():
        if 1 < len(ids) <= max(20, nrep // 200):
            for a, b in itertools.combinations(ids, 2): cand3.add((a, b))
    t3_pairs = []
    for a, b in cand3:
        i, j = repl[a], repl[b]
        if i in t2_members and j in t2_members: continue
        if cos(vecs[a], vecs[b]) >= cos_thr:
            t3_pairs.append((a, b))
    t3 = [[repl[i] for i in g] for g in cluster_pairs(len(repl), t3_pairs)]
    t3 = [[i for i in g if i not in t2_members] for g in t3]
    t3 = [g for g in t3 if len(g) > 1]
    if verbose:
        print(f"  n={n}: T1 exact-dup groups={len(t1)} (members {sum(map(len,t1))}), "
              f"T2 template families={len(t2)} (members {sum(map(len,t2))}), "
              f"T3 paraphrase rings={len(t3)} (members {sum(map(len,t3))})")
    return {"t1": t1, "t2": t2, "t3": t3}

# ---------- validation: planted paraphrase rings ----------
SYN = {"protect": "safeguard", "important": "vital", "rule": "regulation", "animals": "wildlife",
       "oppose": "object to", "support": "back", "harm": "damage", "need": "require",
       "should": "ought to", "country": "nation", "many": "numerous", "help": "assist",
       "stop": "halt", "keep": "maintain", "change": "alter", "people": "citizens"}
def paraphrase(t, rng):
    ws = t.split()
    out = []
    for w in ws:
        lw = w.lower().strip(".,")
        if lw in SYN and rng.random() < 0.6:
            out.append(SYN[lw])
        elif rng.random() < 0.08:
            continue  # drop word
        else:
            out.append(w)
    if rng.random() < 0.5 and "." in t:  # shuffle sentences
        sents = [s.strip() for s in t.split(".") if s.strip()]
        rng.shuffle(sents)
        return ". ".join(sents) + "."
    return " ".join(out)

def validate():
    rng = random.Random(3)
    organic = [
        "I have lived near the wildlife refuge for thirty years and the changes I have seen are heartbreaking. Please do not weaken these protections.",
        "This proposal ignores the science. Habitat loss is the main driver of extinction and redefining harm will make it worse. I strongly oppose it.",
        "As a hunter and fisherman I depend on healthy ecosystems. Gutting the ESA is bad for everyone who loves the outdoors. Reconsider this.",
        "The endangered species act works. Bald eagles came back because of it. Why would we break something that works? I am against this change.",
        "My grandchildren deserve to see grizzly bears and whooping cranes in the wild, not just in books. Keep the protections strong.",
        "This rule change is a giveaway to developers and will not help ordinary people at all. I urge the service to withdraw it immediately.",
        "Economic growth and conservation can coexist. This change is a false choice. Protect the habitat and the species that depend on it.",
        "I am a biology teacher and I use the ESA as an example of effective policy. Narrowing the definition of harm guts its core protection.",
    ] * 40  # 320 organic
    seeds = ["We must protect endangered animals because the rule as written is important for our country and many species need help to survive. I oppose any change that would harm habitat protections and I support keeping the current rule.",
             "The proposed change should be stopped because it will harm many animals that people in this country care about. We need to keep strong protections and I oppose weakening the rule that helps wildlife survive."]
    rings = []
    for s in seeds:
        rings.append([paraphrase(s, rng) for _ in range(25)])
    labeled = [(t, None) for t in organic]
    for ri, ring in enumerate(rings): labeled += [(t, ri) for t in ring]
    rng.shuffle(labeled)
    texts = [t for t, _ in labeled]
    truth = [l for _, l in labeled]
    print("VALIDATION: 320 organic + 2 planted paraphrase rings of 25")
    for thr in (0.3, 0.35, 0.4, 0.45, 0.5):
        r = analyze(texts, thr, verbose=False)
        allc = r["t3"] + r["t2"]
        stats = []
        for ri in range(len(rings)):
            best = 0; pur = 0
            for g in allc:
                k = sum(1 for i in g if truth[i] == ri)
                if k > best: best, pur = k, k/len(g)
            stats.append((best, len(rings[ri]), pur))
        fp = sum(1 for g in allc for i in g if truth[i] is None and len(g) > 3)
        print(f"  cos_thr={thr}: ring recovery {[(b,n,round(p,2)) for b,n,p in stats]} (found/planted/purity); organic in big clusters: {fp}")

if __name__ == "__main__":
    validate()
