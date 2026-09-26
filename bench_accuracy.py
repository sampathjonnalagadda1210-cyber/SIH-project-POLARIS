# -*- coding: utf-8 -*-
"""
bench_accuracy.py - ground-truth accuracy benchmark for POLARIS.
Run while server code is importable:  python bench_accuracy.py
Measures top-1 / top-3 accuracy on known product->standard pairs,
Hindi robustness, and honest-refusal on out-of-domain input.
"""
import importlib.util

spec = importlib.util.spec_from_file_location("s", "server.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
s.load_corpus()
s.build_index()

# (query, acceptable answer(s) for top-1, acceptable set for top-3)
CASES = [
    ("supply of TMT reinforcement bars Fe 500D for RCC works", ["IS 1786"], ["IS 1786", "IS 432"]),
    ("ordinary portland cement 43 grade in bags", ["IS 269"], ["IS 269", "IS 1489", "IS 455"]),
    ("portland pozzolana cement fly ash based", ["IS 1489"], ["IS 1489", "IS 269", "IS 455"]),
    ("PVC insulated cables for house wiring 1100 V", ["IS 694"], ["IS 694", "IS 1554", "IS 7098"]),
    ("XLPE insulated cables for power distribution", ["IS 7098"], ["IS 7098", "IS 1554", "IS 694"]),
    ("common burnt clay bricks for masonry walls", ["IS 1077"], ["IS 1077", "IS 3495", "IS 2212"]),
    ("industrial safety helmets for construction workers", ["IS 2925"], ["IS 2925", "IS 2927", "IS 15298"]),
    ("domestic gas stove for LPG use in kitchens", ["IS 4246"], ["IS 4246", "IS 3196", "IS 3224"]),
    ("aluminium pressure cookers for household", ["IS 2347"], ["IS 2347"]),
    ("ceiling fans and regulators for school buildings", ["IS 374"], ["IS 374", "IS 302"]),
    ("miniature circuit breakers MCB for distribution boards", ["IS 8828"], ["IS 8828", "IS 1293", "IS 732"]),
    ("ready mixed concrete M25 delivered in transit mixers", ["IS 4926"], ["IS 4926", "IS 456", "IS 1199"]),
    ("unplasticized PVC pipes for potable water supply", ["IS 4985"], ["IS 4985", "IS 2505", "IS 15778"]),
    ("rotomoulded polyethylene water storage tanks", ["IS 12701"], ["IS 12701", "IS 10146"]),
    ("static energy meters class 1 for domestic consumers", ["IS 13779"], ["IS 13779", "IS 779"]),
    ("borewell submersible pump sets for irrigation", ["IS 9079"], ["IS 9079", "IS 12615", "IS 5120"]),
    ("emulsion paint for interior and exterior walls", ["IS 120"], ["IS 120", "IS 101", "IS 2395"]),
    ("galvanized steel sheets for roofing and cladding", ["IS 277"], ["IS 277", "IS 2629"]),
    ("hot dip galvanizing practice for steel structures", ["IS 2629"], ["IS 2629", "IS 277"]),
    ("recommendations for installation and maintenance of pumps", ["IS 5120"], ["IS 5120", "IS 9079"]),
    ("code of practice for laying of plastics pipefittings", ["IS 7634"], ["IS 7634", "IS 4985"]),
    ("coarse and fine aggregates crushed stone sand for concrete", ["IS 383"], ["IS 383", "IS 2386"]),
    # Hindi (Devanagari) - top-3 family check
    ("सीमेंट की आपूर्ति करनी है", ["IS 269", "IS 1489", "IS 455"], ["IS 269", "IS 1489", "IS 455"]),
    ("सरिया और स्टील की आपूर्ति", ["IS 1786", "IS 432"], ["IS 1786", "IS 432"]),
    ("पानी की लाइन के लिए पीवीसी पाइप", ["IS 4985", "IS 2505"], ["IS 4985", "IS 2505", "IS 15778", "IS 7634"]),
]

top1_hits = top3_hits = 0
failures = []
for i, (q, t1_set, t3_set) in enumerate(CASES, 1):
    a = s.analyze(q)
    recs = [r["code"] for r in a["recommendations"][:3]]
    ok1 = recs[0] in t1_set if recs else False
    ok3 = any(c in t3_set for c in recs)
    top1_hits += ok1
    top3_hits += ok3
    if not ok1:
        failures.append((i, q, recs, t1_set))

n = len(CASES)
print("=" * 64)
print("RECOMMENDATION ACCURACY: %d ground-truth cases" % n)
print("  Top-1 accuracy : %d/%d = %.0f%%" % (top1_hits, n, 100 * top1_hits / n))
print("  Top-3 accuracy : %d/%d = %.0f%%" % (top3_hits, n, 100 * top3_hits / n))
if failures:
    print("  Top-1 misses:")
    for i, q, got, want in failures:
        print("   #%d %r -> got %s (wanted %s)" % (i, q[:52], got, want))

# honest-refusal / robustness checks
robust = []
gib = s.analyze("zx qv flickor bamboozle 44821 unknownproductxyz")
robust.append(("gibberish -> no crash, empty/low output",
               gib["primary_codes"] == [] or gib["spec_health"]["score"] <= 5))
med = s.analyze("supply of cardiac stents and MRI machine spare parts")
robust.append(("out-of-domain -> honest (no fake confident match)",
               med["primary_codes"] == [] or
               med["recommendations"][0]["score"] < 0.2))
v = s.version_check("Structural steel to IS-2062:2006 and cement to IS:269-2015")
flags = {x["code"]: x["status"] for x in v}
robust.append(("dash/colon citation styles detected (IS-2062 / IS:269)",
               flags.get("IS 2062") == "outdated" and "IS 269" in flags))
# full-coverage spec should score near-perfect
full = s.analyze("TMT bars to IS 1786:2008 with tensile testing per IS 1608, "
                 "chemical analysis per IS 228, concrete works per IS 456, cubes "
                 "per IS 1199, water per IS 3025, aggregates per IS 2386, cement "
                 "tests per IS 4031, terms per IS 4845")
robust.append(("full-coverage spec scores >= 85", full["spec_health"]["score"] >= 85))
print("-" * 64)
for name, ok in robust:
    print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
print("=" * 64)
