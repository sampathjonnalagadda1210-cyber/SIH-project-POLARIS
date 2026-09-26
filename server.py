#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 POLARIS - Procurement-Oriented Listing of Applicable References in
 Indian Standards. Team ATLAS builds the atlas; POLARIS is the star
 you navigate by.
 AI-Powered Recommendation Engine for Identifying Applicable Indian
 Standards for Procurement Specifications   (SIH 2026 - PS SIH26108)
============================================================================
 Zero-dependency prototype: Python standard library only. No pip installs.

 Runs at  ->  http://localhost:8000 (auto-falls back to 8001-8005 if busy)

 Endpoints:
   GET  /                       -> web app
   GET  /api/corpus             -> full corpus (for map + library)
   GET  /api/certifications     -> mandatory certification scheme summary
   POST /api/recommend          -> full analysis (recommend + graph + cert +
                                   versions + coverage + explanation)
        body: {"text": "...", "lang": "en"|"hi"}
   POST /api/chat               -> explainability Q&A over the last analysis
        body: {"question": "Why is IS 1786 recommended?"}
   POST /api/export             -> ready-to-paste specification block
        body: {"analysis": {...}} (or empty to use last analysis)
   POST /api/extract            -> raw file upload (.txt / .pdf) -> text
   GET  /api/report             -> printable HTML assessment report
   POST /api/reload             -> re-read data/standards.json
"""
import json
import math
import os
import re
import time
import unicodedata
import urllib.parse
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(ROOT, "data", "standards.json")
WEB_DIR = os.path.join(ROOT, "web")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
CORPUS = []          # list of standard dicts
BY_CODE = {}         # code -> record
LAST_ANALYSIS = None # last /api/recommend result (for chat + export)

# ---------------------------------------------------------------------------
# Load corpus
# ---------------------------------------------------------------------------
def load_corpus():
    global CORPUS, BY_CODE
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    CORPUS = data["records"]
    BY_CODE = {r["code"]: r for r in CORPUS}
    # ensure every referenced code resolves; note dangling refs for honesty
    dangling = set()
    for r in CORPUS:
        for ref in r.get("refs", []):
            base = ref.split("(")[0].strip()
            if base not in BY_CODE and ref not in BY_CODE:
                dangling.add(ref)
    return len(CORPUS), sorted(dangling)

# ---------------------------------------------------------------------------
# Text normalization + tokenization
# ---------------------------------------------------------------------------
STOPWORDS = set("""a an the and or of for in on to with by from as at is are be
this that it its into under over per their our your all any each other than
then also such which who whom whose what when where how not no nor but if
while during before after above below up down out off again further once here
there all more most some few own same so too very can will just should now
etc via using use used shall must may""".split())

SYNONYMS = {
    # multilingual / colloquial mappings -> canonical concepts
    "cement": "cement", "sement": "cement", "cimento": "cement",
    "concrete": "concrete", "concret": "concrete",
    "steel": "steel", "reinforcement": "reinforcement",
    "sariya": "steel", "sariya": "steel", "tmt": "reinforcement", "thok": "steel", "loha": "steel",
    "pipe": "pipe", "pipes": "pipe", "pipeline": "pipe", "nali": "pipe",
    "paani": "water", "pani": "water", "water": "water", "jal": "water",
    "drinking": "potable", "peene": "potable",
    "wire": "cable", "wires": "cable", "cable": "cable", "cables": "cable",
    "wiring": "wiring", "bijli": "electrical", "electric": "electrical",
    "electrical": "electrical", "electricity": "electrical",
    "switch": "switchgear", "plugs": "plug", "plug": "plug",
    "socket": "socket", "mcb": "mcb", "breaker": "mcb",
    "fan": "fan", "fans": "fan", "pankha": "fan",
    "led": "led", "lamp": "lamp", "bulb": "lamp", "light": "lighting",
    "lighting": "lighting",
    "brick": "brick", "bricks": "brick", "eent": "brick",
    "block": "block", "blocks": "block",
    "paint": "paint", "paints": "paint", "rang": "paint",
    "gas": "gas", "lpg": "lpg", "stove": "stove", "chulha": "stove",
    "cylinder": "cylinder", "regulator": "regulator", "hose": "hose",
    "cooker": "cooker", "cookware": "cooker", "pressure": "pressure",
    "helmet": "helmet", "safety": "safety", "footwear": "footwear",
    "shoes": "footwear", "joota": "footwear",
    "meter": "meter", "meters": "meter", "energy": "energy",
    "pump": "pump", "pumps": "pump", "motor": "motor", "motors": "motor",
    "pvc": "pvc", "upvc": "pvc", "cpvc": "cpvc", "plastic": "plastic",
    "plastics": "plastic", "hdpe": "plastic", "polyethylene": "polyethylene",
    "tank": "tank", "tanks": "tank",
    "fly": "fly", "ash": "ash", "flyash": "flyash", "pozzolana": "pozzolana",
    "aggregate": "aggregate", "aggregates": "aggregate", "sand": "aggregate",
    "reti": "aggregate", "crushed": "aggregate",
    "tender": "tender", "procurement": "procurement", "purchase": "procurement",
    "specification": "specification", "spec": "specification",
    "sheathing": "conduit", "conduit": "conduit", "conduits": "conduit",
    "sheet": "sheet", "sheets": "sheet", "galvanized": "galvanized",
    "galvanizing": "galvanized", "galvanize": "galvanized", "galvanised": "galvanized",
    "distribution": "distribution", "supply": "supply", "construction": "construction",
    "building": "building", "house": "building", "masonry": "masonry",
    "load": "load", "strength": "strength", "testing": "test", "test": "test",
    "quality": "quality", "grade": "grade", "grades": "grade",
}

# Devanagari (Hindi-script) concept bridge: maps Hindi words/phrases found in
# the query to canonical English concepts so Hindi input matches the corpus.
HINDI_MAP = {
    "\u0938\u0940\u092e\u0947\u0902\u091f": "cement",
    "\u0915\u0902\u0915\u094d\u0930\u0940\u091f": "concrete",
    "\u0938\u0930\u093f\u092f\u093e": "reinforcement", "\u0938\u094d\u091f\u0940\u0932": "steel",
    "\u0930\u0947\u0928\u092b\u093e\u0907\u0928\u092e\u0947\u0902\u091f": "reinforcement",
    "\u092a\u093e\u0907\u092a": "pipe", "\u0928\u0932\u0940": "pipe",
    "\u092a\u093e\u0928\u0940": "water", "\u091c\u0932": "water",
    "\u0924\u093e\u0930": "cable", "\u0915\u0947\u092c\u0932": "cable",
    "\u092c\u093f\u091c\u0932\u0940": "electrical", "\u0935\u093f\u0926\u094d\u092f\u0941\u0924": "electrical",
    "\u0908\u0902\u091f": "brick", "\u0908\u0902\u091f\u0947\u0902": "brick",
    "\u092a\u0947\u0902\u091f": "paint", "\u0930\u0902\u0917": "paint",
    "\u0917\u0948\u0938": "gas", "\u091a\u0942\u0932\u094d\u0939\u093e": "stove",
    "\u0938\u093f\u0932\u0947\u0902\u0921\u0930": "cylinder", "\u0915\u0941\u0915\u0930": "cooker",
    "\u092a\u0902\u0916\u093e": "fan", "\u092c\u0932\u094d\u092c": "lamp", "\u092c\u0924\u094d\u0924\u0940": "lamp",
    "\u0939\u0947\u0932\u092e\u0947\u091f": "helmet", "\u091c\u0942\u0924\u093e": "footwear",
    "\u092a\u0902\u092a": "pump", "\u092e\u094b\u091f\u0930": "motor",
    "\u092e\u0940\u091f\u0930": "meter", "\u092a\u094d\u0932\u093e\u0938\u094d\u091f\u093f\u0915": "plastic",
    "\u091f\u0902\u0915\u0940": "tank", "\u0939\u094c\u091c": "building", "\u092e\u0915\u093e\u0928": "building",
    "\u0928\u093f\u0930\u094d\u092e\u093e\u0923": "construction", "\u0916\u0930\u0940\u0926": "procurement",
    "\u092a\u0930\u0940\u0915\u094d\u0937\u0923": "test", "\u0917\u0941\u0923\u0935\u0924\u094d\u0924\u093e": "quality",
    "\u092e\u0930\u092e\u094d\u092e\u0924": "cement", "\u0930\u0947\u0924": "aggregate",
    "\u092c\u093e\u0932\u0942": "aggregate", "\u0906\u092a\u0942\u0930\u094d\u0924\u093f": "supply",
}

def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))

def tokenize(text, boost_concepts=False):
    # Hindi-script concept bridge runs on the RAW text first: NFKD
    # accent-stripping decomposes Devanagari combining marks and would
    # break the mapping (e.g. \u0938\u0940\u092e\u0947\u0902\u091f -> \u0938\u092e\u091f).
    bridged = []
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        for word in re.findall(r"[\u0900-\u097F]+", text):
            for dev, eng in HINDI_MAP.items():
                if dev in word:
                    bridged.append(eng)
    text = strip_accents(text.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    raw = text.split()
    out = []
    for t in raw:
        if t in STOPWORDS:
            continue
        out.append(t)
        syn = SYNONYMS.get(t)
        if not syn and t.endswith("s"):
            syn = SYNONYMS.get(t[:-1])   # simple plural -> singular mapping
        if syn and syn != t:
            out.append(syn)
    out.extend(bridged)
    if boost_concepts:
        # product nouns (cement, steel, pipe...) matter more than generic
        # words (supply, construction): duplicate concept tokens at query time
        concepts = set(SYNONYMS.values()) | set(HINDI_MAP.values())
        out.extend([t for t in out if t in concepts])
    return out

# ---------------------------------------------------------------------------
# Corpus indexing (mini semantic search: TF-IDF vectors + concept expansion)
# ---------------------------------------------------------------------------
def build_index():
    global DF, N_DOCS, VECTORS, TOKENIZED, NORMTITLES, NORMSCOPES
    TOKENIZED = []
    DF = {}
    for r in CORPUS:
        toks = tokenize(" ".join([
            r["code"], r["num"] and str(r["num"]) or "",
            r["category"], r["title"], r["scope"], r["kind"],
            r["cert"].get("scheme", ""),
            r["cert"].get("basis", ""),
        ]))
        TOKENIZED.append(toks)
        for t in set(toks):
            DF[t] = DF.get(t, 0) + 1
    N_DOCS = len(CORPUS)
    VECTORS = [tfidf_vector(toks) for toks in TOKENIZED]
    # normalized titles/scopes for phrase-boost matching ("Ready-Mixed" == "ready mixed")
    NORMTITLES = [re.sub(r"\s+", " ",
                   re.sub(r"[-\u2013\u2014/,:;]", " ", r["title"].lower())).strip()
                  for r in CORPUS]
    NORMSCOPES = [re.sub(r"\s+", " ",
                   re.sub(r"[-\u2013\u2014/,:;]", " ", r["scope"].lower())).strip()
                  for r in CORPUS]

def query_phrases(text, max_len=3):
    """Contiguous 2-4 word phrases from the query, built twice: from the
    stopword-filtered token stream ("energy meters" style) and from the raw
    stream ("installation and maintenance" keeps its 'and' so it still
    matches titles verbatim). Union used for title/scope boosting."""
    clean = re.sub(r"[^a-z0-9\s]", " ", strip_accents(text.lower()))
    raw_toks = [t for t in clean.split() if len(t) > 1]
    toks = [t for t in raw_toks if t not in STOPWORDS and len(t) > 2]
    phrases = set()
    for toks_list in (toks, raw_toks):
        for n in (2, 3, 4):
            for i in range(len(toks_list) - n + 1):
                phrases.add(" ".join(toks_list[i:i + n]))
    return phrases

def title_phrase_hits(phrases):
    """(title_hits, scope_hits): corpus indices whose normalized title/scope
    contains a query phrase. Title hits are strong evidence ("XLPE insulated
    cables" -> IS 7098); scope hits are supporting evidence ("energy meters"
    inside IS 13779's scope)."""
    thits, shits = set(), set()
    for i, nt in enumerate(NORMTITLES):
        if any(p in nt for p in phrases):
            thits.add(i)
    for i, ns in enumerate(NORMSCOPES):
        if i not in thits and any(p in ns for p in phrases):
            shits.add(i)
    return thits, shits

def tfidf_vector(tokens):
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    vec = {}
    for t, c in tf.items():
        idf = math.log((N_DOCS + 1) / (DF.get(t, 0) + 1)) + 1
        vec[t] = (c / len(tokens)) * idf if tokens else 0
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}

def cosine(a, b):
    if len(b) < len(a):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())

# ---------------------------------------------------------------------------
# Query understanding (intent + concept extraction)
# ---------------------------------------------------------------------------
def understand_query(text):
    toks = tokenize(text)
    concepts = sorted({t for t in toks if t in set(SYNONYMS.values())})
    return {"tokens": toks, "concepts": concepts,
            "char_count": len(text), "lang_hint": detect_lang_hint(text)}

def detect_lang_hint(text):
    devanagari = sum(1 for ch in text if "\u0900" <= ch <= "\u097F")
    return "hi" if devanagari > len(text) * 0.1 else "en"

CONCEPT_SET = None  # built after SYNONYMS/HINDI_MAP are defined

# Product nouns that deserve their own primary standard in a tender.
# Generic action words (supply, construction, procurement, test, quality)
# are deliberately excluded from champion selection.
PRODUCT_CONCEPTS = frozenset("""
    cement concrete steel reinforcement pipe water cable wiring electrical
    plug socket mcb fan led lamp lighting brick block paint gas stove
    cylinder regulator hose cooker helmet footwear meter energy pump motor
    pvc plastic polyethylene tank flyash pozzolana aggregate conduit sheet
    galvanized
""".split())

def concept_champions(text, max_champions=6):
    """For every product concept mentioned in the input (cement, steel,
    brick, cable...), find that concept's best-matching PRODUCT standard.
    These 'champions' lead the recommendation list so a multi-product spec
    surfaces each product family's primary standard, not just the family
    whose documents happen to match the most concepts."""
    global CONCEPT_SET
    if CONCEPT_SET is None:
        CONCEPT_SET = set(SYNONYMS.values()) | set(HINDI_MAP.values())
    toks = tokenize(text)
    seen = list(dict.fromkeys(toks))
    concepts = [t for t in seen if t in PRODUCT_CONCEPTS]
    champs = []
    phrases = query_phrases(text)
    thits, shits = title_phrase_hits(phrases)
    # full-query alignment vector: a family head should also fit the WHOLE
    # query, not just its own concept word ("TMT ... Fe 500D" must pull
    # IS 1786 ahead of IS 432 even though both are 'steel' products)
    qv_full = tfidf_vector(tokenize(text, boost_concepts=True))
    PROCESS_INTENT = bool(re.search(
        r"\b(practice|installation|installing|laying|erection|"
        r"maintenance|application|workmanship)\b", text, re.I))
    cop_kind = "Code of Practice / Installation"
    for c in concepts:
        qv = tfidf_vector([c, c])   # duplicated for query weight
        best_prod = (None, 0.0)
        best_any = (None, 0.0)
        for i in range(len(CORPUS)):
            s = cosine(qv, VECTORS[i])
            # boosts INSIDE the argmax so the right doc wins the family
            if i in thits:
                s += 0.28                       # title-phrase evidence
            elif i in shits:
                s += 0.12                       # scope-phrase evidence
            s += 0.10 * cosine(qv_full, VECTORS[i])  # whole-query alignment
            if s > best_any[1]:
                best_any = (i, s)
            if CORPUS[i]["kind"] == "Product / Specification" and s > best_prod[1]:
                best_prod = (i, s)
        # Process-intent: queries asking for a *practice/installation*
        # standard want a Code of Practice, not the product itself.
        if best_any[0] is not None and best_any[0] in thits:
            want_any = best_any[1] > best_prod[1] + 0.05 or (
                PROCESS_INTENT and CORPUS[best_any[0]]["kind"] == cop_kind)
        else:
            want_any = False
        if want_any:
            best_i, best_s = best_any
        else:
            best_i, best_s = best_prod if best_prod[1] > 0.08 else best_any
        if best_i is not None and best_s > 0.08:
            # intent-aware family ordering: when the query asks for a
            # practice/installation standard, a Code of Practice that
            # matched a query phrase leads the whole result list
            if PROCESS_INTENT and best_i in thits and CORPUS[best_i]["kind"] == cop_kind:
                best_s = min(1.0, best_s + 0.08)
        if best_i is not None and best_s > 0.08:
            r = CORPUS[best_i]
            champs.append({"code": r["code"], "title": r["title"],
                           "score": round(min(1.0, best_s), 4),
                           "category": r["category"], "kind": r["kind"],
                           "via_concept": c, "index": best_i})
    champs.sort(key=lambda x: -x["score"])
    out, seen_codes = [], set()
    for ch in champs:
        if ch["code"] not in seen_codes:
            out.append(ch)
            seen_codes.add(ch["code"])
    return out[:max_champions]

def search(text, top_k=8):
    qv = tfidf_vector(tokenize(text, boost_concepts=True))
    phrases = query_phrases(text)
    thits, shits = title_phrase_hits(phrases)
    scored = []
    for i, r in enumerate(CORPUS):
        s = cosine(qv, VECTORS[i])
        # small boost if the exact code appears in the query
        m = re.search(r"\bis\s*[:. ]?\s*(\d{2,6})", text, re.I)
        if m and str(r["num"]) == m.group(1):
            s = min(1.0, s + 0.55)
        # field-boosted matching: distinctive query phrases appearing
        # verbatim in a standard's title (strong) or scope (supporting)
        if s > 0.02:
            if i in thits:
                s = min(1.0, s + 0.28)
            elif i in shits:
                s = min(1.0, s + 0.12)
        scored.append((s, i))
    scored.sort(key=lambda x: -x[0])
    results = []
    for s, i in scored[:top_k]:
        r = CORPUS[i]
        if s <= 0.02:
            continue
        results.append({"code": r["code"], "title": r["title"],
                        "score": round(s, 4), "category": r["category"],
                        "kind": r["kind"], "index": i})
    return results

# ---------------------------------------------------------------------------
# Version check: find outdated citations inside the input text
# ---------------------------------------------------------------------------
IS_CODE_RE = re.compile(r"\bIS\s*[:.\-\u2013\u2014]?\s*(\d{2,6})", re.I)  # IS 269 | IS:269 | IS-269 | IS–269

def detect_cited(text):
    """Return the set of corpus codes explicitly cited in the input text."""
    cited = set()
    for m in IS_CODE_RE.finditer(text):
        rec = next((r for r in CORPUS if r["num"] == int(m.group(1))), None)
        if rec:
            cited.add(rec["code"])
    return cited

def version_check(text):
    findings = []
    for m in re.finditer(r"\bIS\s*[:.\-\u2013\u2014]?\s*(\d{2,6})\s*[:\-]?\s*(\d{4})?", text, re.I):
        num = m.group(1)
        cited_year = int(m.group(2)) if m.group(2) else None
        rec = next((r for r in CORPUS if r["num"] == int(num)), None)
        if not rec:
            continue
        entry = {"code": rec["code"], "cited_edition": cited_year,
                 "current_edition": rec["edition"],
                 "amendments": rec["amendments"],
                 "status": "unknown"}
        if cited_year is None:
            entry["status"] = "cite-edition-explicitly"
            entry["advice"] = ("Cite the edition explicitly, e.g. %s:%d, and "
                               "include all published amendments."
                               % (rec["code"], rec["edition"]))
        elif cited_year < rec["edition"]:
            entry["status"] = "outdated"
            entry["advice"] = ("%s:%d is superseded. Use %s:%d with amendments: %s."
                               % (rec["code"], cited_year, rec["code"],
                                  rec["edition"], ", ".join(rec["amendments"]) or "none"))
        elif cited_year == rec["edition"]:
            if rec["amendments"]:
                entry["status"] = "update-amendments"
                entry["advice"] = ("Edition is current; incorporate amendments: %s."
                                   % ", ".join(rec["amendments"]))
            else:
                entry["status"] = "current"
                entry["advice"] = "Latest edition, no amendments pending."
        else:
            entry["status"] = "future-cited"
            entry["advice"] = ("Cited year %d is later than the latest edition "
                               "(%d) in this corpus; verify on services.bis.gov.in."
                               % (cited_year, rec["edition"]))
        findings.append(entry)
    return findings

# ---------------------------------------------------------------------------
# Normative-reference graph expansion (BFS over refs, transitive)
# ---------------------------------------------------------------------------
def expand_graph(seed_codes, max_depth=2):
    nodes, edges, seen = {}, [], set(seed_codes)
    frontier = [(c, 0) for c in seed_codes]
    while frontier:
        code, depth = frontier.pop(0)
        rec = BY_CODE.get(code)
        if not rec:
            continue
        nodes[code] = node_from_rec(rec, depth)
        if depth >= max_depth:
            continue
        for ref in rec.get("refs", []):
            base = ref.split("(")[0].strip()
            target = BY_CODE.get(base) or BY_CODE.get(ref)
            if not target:
                continue
            edges.append({"from": code, "to": target["code"],
                          "from_title": rec["title"], "to_title": target["title"],
                          "to_kind": target["kind"]})
            if target["code"] not in seen:
                seen.add(target["code"])
                frontier.append((target["code"], depth + 1))
    # dedupe edges
    uniq = {(e["from"], e["to"]): e for e in edges}
    return {"nodes": list(nodes.values()), "edges": list(uniq.values())}

def node_from_rec(rec, depth):
    return {"code": rec["code"], "title": rec["title"], "kind": rec["kind"],
            "category": rec["category"], "depth": depth, "edition": rec["edition"],
            "amendments": rec["amendments"], "refs_count": len(rec.get("refs", [])),
            "cert_scheme": rec["cert"]["scheme"], "cert_mandatory": rec["cert"]["mandatory"]}

# ---------------------------------------------------------------------------
# Certification mapping
# ---------------------------------------------------------------------------
def cert_summary(codes):
    out = []
    for c in codes:
        rec = BY_CODE.get(c)
        if not rec:
            continue
        cert = rec["cert"]
        out.append({"code": rec["code"], "scheme": cert["scheme"],
                    "mandatory": cert["mandatory"], "basis": cert["basis"]})
    out.sort(key=lambda x: (not x["mandatory"], x["code"]))
    return out

# ---------------------------------------------------------------------------
# Coverage / gap analysis
# ---------------------------------------------------------------------------
KIND_WEIGHTS = {"Test Method": 3, "Terminology": 2, "Safety": 2,
                "Code of Practice / Installation": 2, "Product / Specification": 1}

def coverage(primary_codes, graph):
    primary = set(primary_codes)
    total_needed, covered, gaps = 0, 0, []
    for n in graph["nodes"]:
        if n["code"] in primary:
            continue
        total_needed += 1
        # covered if the input text mentioned this code (handled by caller via cited set)
    # Gaps = allied standards reachable from primaries that are typically
    # expected: test methods, terminology, safety, installation.
    for e in graph["edges"]:
        to_rec = BY_CODE.get(e["to"])
        if not to_rec:
            continue
        if to_rec["kind"] in KIND_WEIGHTS and to_rec["kind"] != "Product / Specification":
            if to_rec["code"] not in primary and to_rec["code"] not in gaps:
                gaps.append(to_rec["code"])
    expected = len(gaps) + len(primary)
    cited_allied = 0  # caller passes cited allied count via analysis
    return {"expected_allied": len(gaps), "gap_codes": gaps,
            "primary_count": len(primary)}

def spec_health(cited_codes, primary_codes, gap_codes):
    cited = set(cited_codes)
    prim = set(primary_codes)
    if not prim:
        return {"score": 0, "verdict": "No primary standard identified",
                "detail": {}}
    prim_hit = len(prim & cited)
    gaps = set(gap_codes)
    gap_hit = len(gaps & cited)
    if not cited:
        return {"score": 5,
                "verdict": ("Draft specification - no Indian Standards cited "
                            "yet; adopt the recommended set below"),
                "detail": {"primary_cited": 0, "primary_expected": len(prim),
                           "allied_cited": 0, "allied_expected": len(gaps)}}
    w_primary, w_allied = 60, 40
    score = (w_primary * prim_hit / len(prim)) + \
            (w_allied * (gap_hit / len(gaps)) if gaps else w_allied)
    score = round(score)
    if score >= 85:
        verdict = "Comprehensive specification"
    elif score >= 60:
        verdict = "Adequate, with minor omissions"
    elif score >= 35:
        verdict = "Incomplete - significant allied standards missing"
    else:
        verdict = "Critical gaps - high procurement-dispute risk"
    return {"score": score, "verdict": verdict,
            "detail": {"primary_cited": prim_hit, "primary_expected": len(prim),
                       "allied_cited": gap_hit, "allied_expected": len(gaps)}}

# ---------------------------------------------------------------------------
# Full analysis pipeline
# ---------------------------------------------------------------------------
def diversify(hits, k=3, max_per_category=2):
    """MMR-style diversification so primaries span the whole spec: prefer
    product/specification standards (what a tender actually 'supplies'),
    cap siblings per category, fill from the rest."""
    product_kinds = {"Product / Specification"}
    picked, cats = [], {}
    for h in hits:
        if h.get("kind") not in product_kinds:
            continue
        c = h.get("category")
        if cats.get(c, 0) >= max_per_category:
            continue
        picked.append(h["code"])
        cats[c] = cats.get(c, 0) + 1
        if len(picked) == k:
            return picked
    for h in hits:
        if h["code"] in picked:
            continue
        picked.append(h["code"])
        if len(picked) == k:
            break
    return picked

def analyze(text, lang="en"):
    global LAST_ANALYSIS
    t0 = time.time()
    uq = understand_query(text)
    hits = search(text, top_k=8)
    champs = concept_champions(text, max_champions=6)

    # ---- ranked candidate merge -----------------------------------------
    # 1) explicitly cited corpus standards always lead (the tender's own refs)
    # 2) concept champions lead their own product family, one per category
    # 3) semantic hits fill remaining slots
    cited = detect_cited(text)
    # order cited codes by appearance, product standards first:
    # "primary" = what the tender buys; test methods/supporting standards
    # belong to the allied graph, not the primary top-3.
    cited_order = []
    for m in IS_CODE_RE.finditer(text):
        rec = next((r for r in CORPUS if r["num"] == int(m.group(1))), None)
        if rec and rec["code"] not in cited_order:
            cited_order.append(rec["code"])
    cited_sorted = sorted(
        cited_order,
        key=lambda c: 0 if BY_CODE.get(c, {}).get("kind") == "Product / Specification" else 1)
    merged, seen_codes = [], set()
    for c in cited_sorted:
        r = BY_CODE.get(c)
        if r:
            merged.append({"code": r["code"], "title": r["title"], "score": 1.0,
                           "category": r["category"], "kind": r["kind"],
                           "via": "cited in input", "index": CORPUS.index(r)})
            seen_codes.add(c)
    used_cats = {}
    for r0 in merged:
        used_cats[r0["category"]] = used_cats.get(r0["category"], 0) + 1
    for ch in champs:
        if used_cats.get(ch["category"], 0) >= 2 or ch["code"] in seen_codes:
            continue
        ch["via"] = "concept: " + ch["via_concept"]
        merged.append(ch)
        seen_codes.add(ch["code"])
        used_cats[ch["category"]] = used_cats.get(ch["category"], 0) + 1
    for h in hits:
        if h["code"] not in seen_codes:
            h.setdefault("via", "semantic match")
            merged.append(h)
            seen_codes.add(h["code"])
    hits = merged[:8]
    primary = [h["code"] for h in hits[:3]]
    graph = expand_graph(primary, max_depth=2)
    versions = version_check(text)
    certs = cert_summary([n["code"] for n in graph["nodes"]])
    cov = coverage(primary, graph)

    # cited codes from the input (for health scoring) — already detected above
    health = spec_health(cited, primary, cov["gap_codes"])

    explanation = build_explanation(uq, hits, graph, versions, certs, health, primary)

    result = {
        "query": {"text": text, "lang": lang, **uq},
        "recommendations": hits,
        "primary_codes": primary,
        "graph": graph,
        "versions": versions,
        "certifications": certs,
        "coverage": cov,
        "cited_codes": sorted(cited),
        "spec_health": health,
        "explanation": explanation,
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "corpus_size": len(CORPUS),
        "honesty_note": ("Corpus is a curated subset of %d standards; "
                         "editions/amendments are representative. Verify live "
                         "status on services.bis.gov.in." % len(CORPUS)),
    }
    LAST_ANALYSIS = result
    return result

def build_explanation(uq, hits, graph, versions, certs, health, primary=None):
    lines = []
    if uq["concepts"]:
        lines.append("Identified concepts: %s." % ", ".join(uq["concepts"]))
    primary = primary or [h["code"] for h in hits[:3]]
    if primary:
        top = next((h for h in hits if h["code"] == primary[0]), hits[0] if hits else None)
        if top:
            lines.append("Primary match %s (%s) selected by semantic similarity "
                         "score %.2f against title, scope and category - not "
                         "keyword matching." % (top["code"], top["title"], top["score"]))
    allied = sorted({e["to"] for e in graph["edges"]
                     if e["to"] not in primary})
    if allied:
        kinds = {}
        for c in allied:
            r = BY_CODE.get(c)
            if r:
                kinds.setdefault(r["kind"], []).append(c)
        parts = ["%s -> %s" % (k, ", ".join(v)) for k, v in kinds.items()]
        lines.append("Normative-reference expansion added %d allied standards: %s."
                     % (len(allied), "; ".join(parts)))
    if versions:
        for v in versions:
            lines.append("Version check: %s -> %s. %s" % (v["code"], v["status"], v["advice"]))
    mand = [c for c in certs if c["mandatory"]]
    if mand:
        lines.append("Mandatory certification applies to: %s." %
                     ", ".join("%s (%s)" % (c["code"], c["scheme"]) for c in mand))
    lines.append("Spec Health Score: %d/100 - %s." % (health["score"], health["verdict"]))
    return {"summary": " ".join(lines), "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

# ---------------------------------------------------------------------------
# Chat (explainability over last analysis; honest refusals)
# ---------------------------------------------------------------------------
def chat(question):
    if not LAST_ANALYSIS:
        return {"answer": "Please run an analysis first - paste a specification "
                          "and press Analyze. Then I can explain the results.",
                "cited": []}
    a = LAST_ANALYSIS
    q = question.lower()
    cited = []

    def mention(code, why):
        cited.append({"code": code, "why": why})

    m = re.search(r"\bis\s*[:. ]?\s*(\d{2,6})", question, re.I)
    ask_code = None
    if m:
        rec = next((r for r in CORPUS if r["num"] == int(m.group(1))), None)
        if rec:
            ask_code = rec["code"]

    # Intent: why recommended
    if any(w in q for w in ("why", "reason", "kaise", "kyun", "kyu", "kuen")):
        if ask_code:
            rec = BY_CODE.get(ask_code)
            top = next((h for h in a["recommendations"] if h["code"] == ask_code), None)
            if top:
                paths = [e for e in a["graph"]["edges"]
                         if e["to"] == ask_code and e["from"] in a["primary_codes"]]
                if paths:
                    ans = ("%s is recommended as an allied standard because %s "
                           "(your primary match) references it normatively (%s: %s)."
                           % (ask_code, paths[0]["from_title"], ask_code, rec["title"]))
                    mention(ask_code, "normative reference of " + paths[0]["from"])
                else:
                    ans = ("%s (%s) matched your query with semantic score %.2f. "
                           "Scope: %s" % (ask_code, rec["title"], top["score"], rec["scope"]))
                    mention(ask_code, "semantic match, score %.2f" % top["score"])
                return {"answer": ans, "cited": cited}
            return {"answer": ("%s is not part of the current recommendation set. "
                               "Re-run the analysis with more context, or check the "
                               "graph explorer." % ask_code), "cited": []}
        top = next((h for h in a["recommendations"]
                    if a["primary_codes"] and h["code"] == a["primary_codes"][0]),
                   a["recommendations"][0] if a["recommendations"] else None)
        if top:
            mention(top["code"], "primary match, semantic score %.2f" % top["score"])
            return {"answer": a["explanation"]["summary"], "cited": cited}
        return {"answer": "No recommendation available yet.", "cited": []}

    # Intent: certification
    if any(w in q for w in ("certif", "isi", "crs", "hallmark", "licence", "license")):
        mand = [c for c in a["certifications"] if c["mandatory"]]
        if mand:
            lines = ["Mandatory certification requirements identified:"]
            for c in mand:
                lines.append("- %s: %s (%s)" % (c["code"], c["scheme"], c["basis"]))
                mention(c["code"], "mandatory certification: " + c["scheme"])
            lines.append("Scheme process: apply on BIS ManakOnline portal, product "
                         "testing in a BIS-recognized lab, factory inspection, then "
                         "licence grant with marking fee.")
            return {"answer": "\n".join(lines), "cited": cited}
        return {"answer": "None of the recommended standards carry mandatory "
                          "certification in this corpus. BIS licences may still be "
                          "voluntary - see /api/certifications.", "cited": []}

    # Intent: labs
    if any(w in q for w in ("lab", "laborator", "testing", "test where")):
        cats = sorted({BY_CODE[c]["category"] for c in a["primary_codes"] if c in BY_CODE})
        return {"answer": ("For testing, use a BIS-recognized laboratory for the "
                           "product category: %s. The mandatory test methods are %s. "
                           "The BIS Lab Recognition directory (services.bis.gov.in) "
                           "lists labs by product and location."
                           % (", ".join(cats) or "general",
                              ", ".join([r["code"] for r in CORPUS
                                         if r["kind"] == "Test Method"
                                         and r["code"] in a["coverage"]["gap_codes"]]) or "as per the standard")),
                "cited": [{"code": c, "why": "test method required"}
                          for c in a["coverage"]["gap_codes"]
                          if c in BY_CODE and BY_CODE[c]["kind"] == "Test Method"]}

    # Intent: versions
    if any(w in q for w in ("version", "edition", "latest", "amendment", "current")):
        if a["versions"]:
            lines = []
            for v in a["versions"]:
                lines.append("%s -> %s: %s" % (v["code"], v["status"], v["advice"]))
            return {"answer": "\n".join(lines), "cited": [{"code": v["code"], "why": "version check"} for v in a["versions"]]}
        return {"answer": "No explicit edition citations were found in your input. "
                          "I recommend citing IS codes with their year, e.g. IS 1786:2008.",
                "cited": []}

    # Intent: allied / missing
    if any(w in q for w in ("missing", "gap", "allied", "related", "also")):
        gaps = a["coverage"]["gap_codes"]
        if gaps:
            lines = ["Allied standards typically expected but not cited in your input:"]
            for c in gaps:
                r = BY_CODE.get(c)
                lines.append("- %s (%s): %s" % (c, r["kind"], r["title"]))
            return {"answer": "\n".join(lines),
                    "cited": [{"code": c, "why": "normative-reference expansion"}
                              for c in gaps]}
        return {"answer": "No gaps found - your specification covers the expected "
                          "allied standards in this corpus.", "cited": []}

    # Default: explain the whole analysis
    return {"answer": a["explanation"]["summary"], "cited": []}

# ---------------------------------------------------------------------------
# Export: ready-to-paste specification block
# ---------------------------------------------------------------------------
def export_spec(a=None):
    a = a or LAST_ANALYSIS
    if not a:
        return {"spec": "Run an analysis first.", "markdown": "Run an analysis first."}
    L = []
    L.append("TECHNICAL SPECIFICATION - INDIAN STANDARDS REFERENCES")
    L.append("Generated by POLARIS (Team ATLAS - PS SIH26108) on " + time.strftime("%d-%m-%Y %H:%M"))
    L.append("")
    L.append("1. APPLICABLE INDIAN STANDARDS")
    L.append("")
    L.append("1.1 Primary Standards")
    for h in a["recommendations"][:3]:
        r = BY_CODE[h["code"]]
        amd = (", ".join(r["amendments"])) or "no amendments"
        cert = r["cert"]
        certtxt = ("Mandatory %s certification applies." % cert["scheme"]
                   if cert["mandatory"] else "BIS licence recommended (voluntary).")
        L.append("  - %s : %s (Ed %d; %s). %s" % (r["code"], r["title"], r["edition"], amd, certtxt))
    L.append("")
    L.append("1.2 Allied / Normative-Reference Standards")
    allied = sorted({e["to"] for e in a["graph"]["edges"]
                     if e["to"] not in [x["code"] for x in a["recommendations"][:3]]})
    for c in allied:
        r = BY_CODE.get(c)
        if r:
            L.append("  - %s : %s (Ed %d)" % (r["code"], r["title"], r["edition"]))
    L.append("")
    L.append("2. CERTIFICATION REQUIREMENTS")
    mand = [c for c in a["certifications"] if c["mandatory"]]
    if mand:
        for c in mand:
            L.append("  - %s: %s - %s" % (c["code"], c["scheme"], c["basis"]))
    else:
        L.append("  - No mandatory certification identified for the recommended standards.")
    L.append("")
    L.append("3. VERSION COMPLIANCE NOTES")
    if a["versions"]:
        for v in a["versions"]:
            L.append("  - %s: %s" % (v["code"], v["advice"]))
    else:
        L.append("  - Cite each IS code with its edition year and applicable amendments.")
    L.append("")
    L.append("4. SPECIFICATION HEALTH")
    L.append("  - Score: %d/100 - %s" % (a["spec_health"]["score"], a["spec_health"]["verdict"]))
    if a["coverage"]["gap_codes"]:
        L.append("  - Suggested additions: " + ", ".join(a["coverage"]["gap_codes"]))
    L.append("")
    L.append("Note: Verify current status of all standards on services.bis.gov.in.")
    spec = "\n".join(L)
    md = "```\n" + spec + "\n```"
    return {"spec": spec, "markdown": md}

# ---------------------------------------------------------------------------
# File extraction: .txt and .pdf (stdlib zlib inflate + naive text gather)
# ---------------------------------------------------------------------------
def _is_binary_junk(data):
    """Heuristic: font programs / xobjects decode to control-char soup."""
    if not data:
        return True
    sample = data[:1500]
    printable = sum(1 for b in sample if 32 <= b <= 126 or b in (9, 10, 13))
    return printable / len(sample) < 0.55

def _readable_word_count(data):
    return len(re.findall(rb"[A-Za-z]{4,}", data))

def _decode_pdf_string(s):
    return (s.replace("\\(", "(").replace("\\)", ")")
             .replace("\\\\", "\\").replace("\\n", " "))

def _parse_tounicode(data):
    """Parse a ToUnicode CMap stream -> {source_code:int -> unicode_str}.
    Handles beginbfchar and beginbfrange (both destination forms)."""
    gmap = {}
    txt = data.decode("latin-1", "ignore")
    for section in re.findall(r"beginbfchar(.*?)endbfchar", txt, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", section):
            try:
                key = int(src, 16)
                val = "".join(chr(int(dst[i:i + 4], 16)) for i in range(0, len(dst), 4))
                gmap[key] = val
            except Exception:
                continue
    for section in re.findall(r"beginbfrange(.*?)endbfrange", txt, re.S):
        # form 1: <lo> <hi> <dstStart>  — contiguous unicode range
        for lo, hi, dst in re.findall(
                r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>",
                section):
            try:
                lo_i, hi_i = int(lo, 16), int(hi, 16)
                base = int(dst, 16)
                for k in range(hi_i - lo_i + 1):
                    gmap[lo_i + k] = chr(base + k)
            except Exception:
                continue
        # form 2: <lo> <hi> [<d1> <d2> ...] — explicit destination list
        for lo, items in re.findall(
                r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[((?:<[^>]*>\s*)+)\]",
                section, re.S):
            try:
                lo_i = int(lo, 16)
                codes = re.findall(r"<([0-9A-Fa-f]+)>", items)
                for k, c in enumerate(codes):
                    val = "".join(chr(int(c[j:j + 4], 16)) for j in range(0, len(c), 4))
                    gmap[lo_i + k] = val
            except Exception:
                continue
    return gmap

def _decode_hex_codes(hexstr, gmap):
    """Decode <gId gId ...> operand bytes through the merged gid->unicode map.
    Tries 2-byte codes first (Identity-H), falls back to 1-byte."""
    hx = re.sub(r"[^0-9A-Fa-f]", "", hexstr)
    if not hx:
        return ""
    data = bytes.fromhex(hx + "0" * (len(hx) % 2))
    out = []
    if len(data) % 2 == 0 and len(data) >= 2:
        ok2 = sum(1 for i in range(0, len(data), 2)
                  if (data[i] << 8) | data[i + 1] in gmap)
        if ok2 >= max(1, len(data) // 4):
            for i in range(0, len(data), 2):
                code = (data[i] << 8) | data[i + 1]
                out.append(gmap.get(code, ""))
            return "".join(out)
    for b in data:
        out.append(gmap.get(b, chr(b) if 32 <= b <= 126 else ""))
    return "".join(out)

def extract_pdf_text(raw):
    """Stdlib PDF text extraction, tuned for real government tenders:
    1. decompress every FlateDecode stream,
    2. drop binary junk (font programs decode to garbage),
    3. build a merged glyph->Unicode map from every ToUnicode CMap
       (real tenders use CID/Identity-H subset fonts — without this the
       text is unrecoverable glyph IDs),
    4. gather text from Tj / TJ operands: literal strings AND hex strings
       decoded through the CMap.
    Scanned/image-only PDFs return empty and the app points to OCR."""
    streams = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        data = m.group(1)
        try:
            data = zlib.decompress(data)
        except Exception:
            if _is_binary_junk(data):
                continue
        if _is_binary_junk(data):
            continue
        streams.append(data)

    # merged ToUnicode map across all fonts
    gmap = {}
    for data in streams:
        if b"beginbfchar" in data or b"beginbfrange" in data:
            gmap.update(_parse_tounicode(data))

    texts = []
    for data in streams:
        try:
            txt = data.decode("latin-1", "ignore")
        except Exception:
            continue
        if not re.search(r"\b(BT|Tj|TJ)\b", txt):
            continue
        out = []
        # literal strings with Tj / ' operators
        for tm in re.finditer(r"\((?:[^()\\]|\\.)*\)\s*(?:Tj|')", txt):
            parts = re.findall(r"\((?:[^()\\]|\\.)*\)", tm.group(0))
            out.append("".join(_decode_pdf_string(p[1:-1]) for p in parts))
        # TJ arrays: literal and hex strings mixed
        for tm in re.finditer(r"\[((?:[^\[\]\\]|\\.)*?)\]\s*TJ", txt):
            frag = tm.group(1)
            for lit in re.findall(r"\((?:[^()\\]|\\.)*\)", frag):
                out.append(_decode_pdf_string(lit[1:-1]))
            for hx in re.findall(r"<([0-9A-Fa-f\s]+)>", frag):
                if gmap:
                    out.append(_decode_hex_codes(hx, gmap))
        # standalone hex Tj (some producers use <...> Tj)
        if gmap:
            for tm in re.finditer(r"<([0-9A-Fa-f\s]{4,})>\s*Tj", txt):
                out.append(_decode_hex_codes(tm.group(1), gmap))
        joined = "".join(out)
        # quality gate: keep streams that yield real words
        if len(re.findall(r"[A-Za-z]{4,}", joined)) >= 3:
            texts.append(joined)
    text = "\n".join(texts)
    return re.sub(r"\s+", " ", text).strip()

def smart_excerpt(text, max_chars=18000):
    """Real tenders run 50-200+ pages (the 202-page port-tender PDF used
    for testing extracts to millions of characters). Ranking quality is far
    better on the densest part, so keep the sections that matter:
    technical specifications / IS references / scope-of-supply chunks,
    filled up to max_chars, always keeping the document head."""
    if len(text) <= max_chars:
        return text
    # split into ~2k blocks and score each for specification relevance
    blocks = [text[i:i + 2000] for i in range(0, len(text), 2000)]
    hot = re.compile(
        r"\bIS\s*[:. ]?\s*\d{3,5}\b|IS:\s*\d{3,5}|specification|technical|"
        r"scope|supply of|schedule of|material|cement|steel|paint|cable|pipe|"
        r"concrete|BIS|certification|conform", re.I)
    scored = sorted(
        range(len(blocks)),
        key=lambda i: (len(hot.findall(blocks[i])), -i),
        reverse=True)
    keep, total = [0], len(blocks[0])
    for i in scored:
        if total >= max_chars:
            break
        if i in keep:
            continue
        keep.append(i)
        total += len(blocks[i])
    keep = sorted(set(keep))
    excerpt = "".join(blocks[i] for i in keep)
    return excerpt[:max_chars] + " …"

def extract_text_from_upload(filename, raw):
    low = (filename or "").lower()
    if low.endswith(".pdf") or raw[:5] == b"%PDF-":
        return extract_pdf_text(raw), "pdf"
    if low.endswith(".txt") or low.endswith(".md"):
        for enc in ("utf-8", "utf-16", "latin-1"):
            try:
                return raw.decode(enc), "text"
            except Exception:
                continue
        return raw.decode("utf-8", "ignore"), "text"
    return "", "unknown"

def esc_html(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

# alias used by the report renderer
esc = esc_html

def render_report_html(a):
    """Printable assessment report (browser print -> save as PDF)."""
    h = a["spec_health"]; d = h.get("detail", {})
    rows_rec = "".join(
        "<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%.0f%%</td><td>%s</td></tr>"
        % (esc(r["code"]), esc(r["title"]), esc(r.get("kind", "")),
           r["score"] * 100, esc(r.get("via", "")))
        for r in a["recommendations"][:6])
    rows_ver = "".join(
        "<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>"
        % (esc(v["code"]), esc(v["status"]), esc(v["advice"]))
        for v in a["versions"]) or "<tr><td colspan=3>No explicit citations found.</td></tr>"
    rows_cert = "".join(
        "<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>"
        % (esc(c["code"]), esc(c["scheme"]),
           "MANDATORY" if c["mandatory"] else "voluntary")
        for c in a["certifications"] if c["mandatory"]) or "<tr><td colspan=3>None mandatory.</td></tr>"
    gaps = a["coverage"]["gap_codes"]
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>POLARIS Assessment Report</title><style>
 body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:24px auto;color:#111}
 h1{border-bottom:3px solid #2456a0;padding-bottom:8px}
 .score{font-size:44px;font-weight:800;color:#2456a0}
 table{border-collapse:collapse;width:100%%;margin:10px 0 22px}
 td,th{border:1px solid #bbb;padding:6px 9px;font-size:14px;text-align:left}
 th{background:#eef3fb}
 .mut{color:#666;font-size:13px}
 @media print{.noprint{display:none}}
</style></head><body>
<h1>POLARIS — Specification Assessment Report</h1>
<p class="mut">PS SIH26108 · generated %s · corpus subset note: verify on services.bis.gov.in</p>
<p class="score">%d/100</p><p><b>%s</b></p>
<p class="mut">Primary cited %s/%s · Allied cited %s/%s · Analysis %.1f ms</p>
<h3>Recommended standards</h3>
<table><tr><th>Code</th><th>Title</th><th>Kind</th><th>Match</th><th>Basis</th></tr>%s</table>
<h3>Version compliance</h3>
<table><tr><th>Code</th><th>Status</th><th>Advice</th></tr>%s</table>
<h3>Mandatory certification</h3>
<table><tr><th>Code</th><th>Scheme</th><th>Status</th></tr>%s</table>
<h3>Missing allied standards (gaps)</h3>
<p>%s</p>
<p class="noprint"><button onclick="window.print()" style="padding:10px 18px;font-size:15px">Print / Save as PDF</button></p>
</body></html>""" % (
        time.strftime("%d-%m-%Y %H:%M"), h["score"], esc(h["verdict"]),
        d.get("primary_cited", 0), d.get("primary_expected", 0),
        d.get("allied_cited", 0), d.get("allied_expected", 0),
        a["elapsed_ms"], rows_rec, rows_ver, rows_cert,
        ", ".join(gaps) if gaps else "None — specification covers expected allied standards.")
    return html

# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[POLARIS] " + fmt % args)

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/corpus":
            return self._send(200, {"size": len(CORPUS), "records": CORPUS})
        if path == "/api/certifications":
            mand = [{"code": r["code"], "title": r["title"], "scheme": r["cert"]["scheme"],
                     "basis": r["cert"]["basis"]} for r in CORPUS if r["cert"]["mandatory"]]
            return self._send(200, {"mandatory_count": len(mand), "records": mand})
        if path == "/api/health":
            return self._send(200, {"ok": True, "corpus": len(CORPUS), "app": "POLARIS"})
        if path == "/api/report":
            if not LAST_ANALYSIS:
                return self._send(400, {"error": "Run an analysis first."})
            return self._send(200, render_report_html(LAST_ANALYSIS).encode("utf-8"), "text/html")
        if path == "/" or path == "/index.html":
            return self._static("index.html", "text/html")
        if path == "/app.js":
            return self._static("app.js", "text/javascript")
        if path == "/style.css":
            return self._static("style.css", "text/css")
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        return self._send(404, {"error": "Not found"})

    def _parse_multipart(self):
        """Parse a single-file multipart/form-data upload -> (filename, bytes)."""
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r"boundary=(?:\"([^\"]+)\"|([^;\s]+))", ctype)
        if not m:
            return None
        boundary = (m.group(1) or m.group(2)).encode()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        parts = body.split(b"--" + boundary)
        for part in parts:
            if b"filename=" not in part:
                continue
            head, _, data = part.partition(b"\r\n\r\n")
            fm = re.search(rb"filename=\"([^\"]*)\"", head)
            filename = fm.group(1).decode("utf-8", "ignore") if fm else "upload.bin"
            if data.endswith(b"\r\n"):
                data = data[:-2]
            return filename, data
        return None

    def _static(self, name, ctype):
        fp = os.path.join(WEB_DIR, name)
        if not os.path.exists(fp):
            return self._send(404, {"error": "missing " + name})
        with open(fp, "rb") as f:
            return self._send(200, f.read(), ctype)

    def do_POST(self):
        if self.path.startswith("/api/extract"):
            # must be handled BEFORE the generic JSON body read below:
            # multipart uploads are not JSON and the stream can be read once
            ctype = self.headers.get("Content-Type", "")
            try:
                if ctype.startswith("application/json"):
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                    text, kind = body.get("text", ""), body.get("kind", "ocr")
                else:
                    fs = self._parse_multipart()
                    if not fs:
                        return self._send(400, {"error": "No file received."})
                    filename, raw = fs
                    text, kind = extract_text_from_upload(filename, raw)
                    if not text.strip():
                        return self._send(422, {"error": "Could not extract readable text from %r. "
                                       "It may be a scanned/image PDF — use the Image OCR option "
                                       "or paste the specification text directly." % filename})
            except Exception as e:
                return self._send(400, {"error": "Extraction failed: %s" % e})
            full_chars = len(text)
            if kind == "pdf":
                excerpt = smart_excerpt(text)
                truncated = len(excerpt) < full_chars
            else:
                excerpt, truncated = text, False
            return self._send(200, {"text": excerpt, "kind": kind, "chars": len(excerpt),
                                    "full_chars": full_chars, "truncated": truncated})
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            return self._send(400, {"error": "bad json: %s" % e})
        if self.path.startswith("/api/recommend"):
            text = (body.get("text") or "").strip()
            if not text:
                return self._send(400, {"error": "Field 'text' is required."})
            if len(text) > 20000:
                return self._send(400, {"error": "Text too long (max 20000 chars)."})
            return self._send(200, analyze(text, body.get("lang", "en")))
        if self.path.startswith("/api/chat"):
            q = (body.get("question") or "").strip()
            if not q:
                return self._send(400, {"error": "Field 'question' is required."})
            return self._send(200, chat(q))
        if self.path.startswith("/api/export"):
            analysis = body.get("analysis")
            return self._send(200, export_spec(analysis))
        if self.path.startswith("/api/reload"):
            n, dangling = load_corpus()
            build_index()
            return self._send(200, {"ok": True, "size": n, "dangling_refs": dangling})
        return self._send(404, {"error": "Not found"})

def main():
    import sys
    import threading
    import webbrowser

    try:  # banner appears instantly, even when output is piped/redirected
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    n, dangling = load_corpus()
    build_index()

    # ---- pick the first free port (8000, 8001, 8002 ...) ----------------
    port, srv = None, None
    last_err = None
    for p in (8000, 8001, 8002, 8003, 8004, 8005):
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", p), Handler)
            port = p
            break
        except OSError as e:
            last_err = e
            print("  [!] Port %d is busy (probably an older POLARIS "
                  "window) - trying %d..." % (p, p + 1))
    if srv is None:
        print("  [X] Could not open any port from 8000-8005.")
        print("      Last error: %s" % last_err)
        print("      Fix: close old python windows, or reboot, then retry.")
        return

    url = "http://localhost:%d" % port
    globals()["_PORT"] = port
    print("=" * 72)
    print("  POLARIS - Procurement-Oriented Listing of Applicable References")
    print("           in Indian Standards  (Team ATLAS | PS SIH26108 | BIS)")
    print("=" * 72)
    print("  Corpus loaded : %d standards%s" % (n, "" if not dangling else
          "  [WARNING: %d dangling refs: %s]" % (len(dangling), ", ".join(sorted(dangling)))))
    print("  Server running at: %s" % url)
    print("  A browser tab should open automatically - if not, copy the URL above.")
    print("  To STOP: click this terminal window, then press Ctrl + C")
    print("=" * 72)

    # ---- auto-open the browser shortly after the server is listening ----
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down. Bye!")
    finally:
        srv.server_close()

if __name__ == "__main__":
    main()
