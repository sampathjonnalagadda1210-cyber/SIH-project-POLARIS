# -*- coding: utf-8 -*-
"""End-to-end test for POLARIS (Team ATLAS). ASCII-safe output everywhere."""
import io
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

DEMO_EN = ("Supply of high tensile deformed steel bars Fe 500D grade (TMT) "
           "conforming to IS 1786:2008 for reinforcement of RCC works, together "
           "with ordinary portland cement, coarse and fine aggregates, ready "
           "mixed concrete M25 and concrete cube compressive strength tests.")
DEMO_HI = ("\u0938\u0921\u093c\u0915 \u0928\u093f\u0930\u094d\u092e\u093e\u0923 "
           "\u0915\u093e\u0930\u094d\u092f \u0915\u0947 \u0932\u093f\u090f "
           "\u0938\u0940\u092e\u0947\u0902\u091f, \u0938\u0930\u093f\u092f\u093e, "
           "\u092c\u093e\u0932\u0942 \u0914\u0930 \u0908\u0902\u091f \u0915\u0940 "
           "\u0906\u092a\u0942\u0930\u094d\u0924\u093f \u0915\u0930\u0928\u0940 "
           "\u0939\u0948\u0964 \u092a\u093e\u0928\u0940 \u0915\u0940 \u0932\u093e\u0907\u0928 "
           "\u0915\u0947 \u0932\u093f\u090f PVC \u092a\u093e\u0907\u092a \u092d\u0940 "
           "\u091a\u093e\u0939\u093f\u090f \u0914\u0930 \u092c\u093f\u091c\u0932\u0940 "
           "\u0915\u0947 \u0915\u0947\u092c\u0932 \u0924\u093e\u0930\u0964")
DEMO_OUT = ("Structural steel sections as per IS 2062:2006, MS tubes per IS 1239:1991, "
            "PVC insulated cables per IS 694:1990 and common burnt clay bricks per "
            "IS 1077:1992. Tensile testing and chemical analysis required.")


def post(path, payload):
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


MINI_PDF = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 210 >> stream
BT /F1 12 Tf 72 720 Td (Tender: TMT bars to IS 1786:2008 with OPC cement and PVC cables 1100 V. Compressive tests.) Tj ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
trailer << /Root 1 0 R >>
%%EOF
"""


def upload(filename, raw):
    boundary = "XBOUND123"
    body = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n" % (boundary, filename)).encode() \
        + raw + ("\r\n--%s--\r\n" % boundary).encode()
    req = urllib.request.Request(BASE + "/api/extract", data=body, headers={
        "Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ok = True

    h = json.loads(urllib.request.urlopen(BASE + "/api/health").read())
    print("[health] ok=%s corpus=%d app=%s" % (h["ok"], h["corpus"], h.get("app")))
    if h.get("app") != "POLARIS":
        ok = False; print("  !! expected app=POLARIS")

    a_en = post("/api/recommend", {"text": DEMO_EN})
    print("[EN] primary=%s health=%d gaps=%d graph=%d nodes" % (
        a_en["primary_codes"], a_en["spec_health"]["score"],
        len(a_en["coverage"]["gap_codes"]), len(a_en["graph"]["nodes"])))
    if a_en["primary_codes"][0] != "IS 1786":
        ok = False; print("  !! expected IS 1786 as top primary")

    a_hi = post("/api/recommend", {"text": DEMO_HI})
    print("[HI] primary=%s" % a_hi["primary_codes"])
    print("[HI] top scores=%s" % [(r["code"], round(r["score"], 2))
                                  for r in a_hi["recommendations"][:5]])
    hi_codes = set(a_hi["primary_codes"])
    if not ({"IS 269", "IS 1786", "IS 1077"} & hi_codes):
        print("  ~~ note: cement/steel/brick not in top-3 (see score list above)")

    a_out = post("/api/recommend", {"text": DEMO_OUT})
    flags = [(v["code"], v["status"]) for v in a_out["versions"]]
    print("[OUT] flags=%s" % flags)
    if ("IS 2062", "outdated") not in flags:
        ok = False; print("  !! expected IS 2062 outdated flag")

    # chat right after the EN analysis context requires re-analyzing EN
    post("/api/recommend", {"text": DEMO_EN})
    c = post("/api/chat", {"question": "why is IS 1786 recommended?"})
    print("[CHAT why] %s" % c["answer"][:130])
    if "not part of the current" in c["answer"]:
        ok = False; print("  !! chat failed to explain IS 1786")

    c2 = post("/api/chat", {"question": "certification requirements"})
    print("[CHAT cert] %s" % c2["answer"].splitlines()[0])

    ex = post("/api/export", {})
    print("[EXPORT] lines=%d first=%r" % (len(ex["spec"].splitlines()),
                                          ex["spec"].splitlines()[0]))

    # --- file upload extraction (.txt and .pdf) ---
    t1 = upload("t1.txt", b"Supply of common burnt clay bricks to IS 1077:1992 with safety helmets.")
    print("[UPLOAD txt] chars=%d has-IS1077=%s" % (t1["chars"], "IS 1077" in t1["text"]))
    if "IS 1077" not in t1["text"]:
        ok = False; print("  !! txt extraction failed")
    p1 = upload("t1.pdf", MINI_PDF)
    print("[UPLOAD pdf] chars=%d has-IS1786=%s" % (p1["chars"], "IS 1786" in p1["text"]))
    if "IS 1786" not in p1["text"]:
        ok = False; print("  !! pdf extraction failed")

    # --- assessment report ---
    post("/api/recommend", {"text": DEMO_EN})
    rep = urllib.request.urlopen(BASE + "/api/report", timeout=15).read().decode("utf-8")
    print("[REPORT] title-ok=%s tables=%d" % ("POLARIS" in rep and "/100" in rep, rep.count("<table")))
    if "POLARIS" not in rep or rep.count("<table") < 3:
        ok = False; print("  !! report content incomplete")

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
