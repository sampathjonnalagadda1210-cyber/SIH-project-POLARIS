#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_demo_pdf.py — regenerates demo_tender.pdf as a fully valid PDF
(proper xref table, exact stream lengths, escaped text) using only the
Python standard library. Run:  python make_demo_pdf.py
"""
def esc(s):
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

PAGES = [
    {
        "title": "PUBLIC WORKS DEPARTMENT - TENDER FOR STRUCTURAL STEEL WORKS",
        "body": [
            "Tender No: PWD/Steel/2026/042  |  Demo document for POLARIS testing",
            "",
            "1. STRUCTURAL STEEL: All structural steel sections, plates, angles and",
            "beams for fabrication of roof trusses shall conform to IS 2062:2011.",
            "",
            "2. BOLTS AND WELDING: High tensile structural bolts shall conform to",
            "IS 3757. Metal arc welding shall follow IS 816 code of practice.",
            "",
            "3. PIPING: Mild steel tubes for water lines shall conform to IS 1239:2004.",
            "Electrically welded steel pipes for the sewage line shall conform to",
            "IS 3589 with hydrostatic testing.",
            "",
            "4. WIRING: PVC insulated cables for 1100 V supply shall conform to",
            "IS 694:2010. Electrical wiring installation shall follow IS 732.",
            "",
            "5. CERTIFICATION: Products under mandatory BIS certification must",
            "carry a valid ISI mark. Licences shall remain valid through delivery.",
            "",
            "6. TESTING: Tensile testing per IS 1608 and chemical analysis shall be",
            "witnessed by the Engineer-in-charge. Cable test reports per IS 10810.",
            "",
            "(End of page 1 - demo file for POLARIS upload testing)",
        ],
    },
    {
        "title": "ANNEXURE A - COMPLIANCE CHECKLIST",
        "body": [
            "A1. Bidders shall quote prices inclusive of all duties and taxes.",
            "",
            "A2. Galvanized steel sheets for roofing shall conform to IS 277.",
            "",
            "A3. Rigid PVC conduits for electrical wiring shall conform to IS 9537.",
            "",
            "A4. Miniature circuit breakers shall conform to IS 8828:2019 with",
            "valid CRS registration as applicable to electrical accessories.",
            "",
            "A5. LED lamps for site offices shall carry CRS registration per",
            "IS 16102 Part 1 safety requirements.",
            "",
            "A6. Any reference to a standard includes all amendments published",
            "up to the last date of receipt of bids.",
            "",
            "(This annexure is part of the demo document for upload testing.)",
        ],
    },
]

Y_TOP, Y_MIN, LINE_H = 745, 60, 20


def page_content(page):
    lines = [("T", page["title"])] + [("B", b) for b in page["body"]]
    out = ["BT", "/F1 13 Tf", "60 760 Td"]
    first = True
    for kind, text in lines:
        if not first:
            out.append("0 -%d Td" % LINE_H)
        out.append("(%s) Tj" % esc(text if kind == "B" else text))
        if kind == "T":
            out.append("/F1 11 Tf")
        first = False
    out.append("ET")
    return "\n".join(out).encode("latin-1", "replace")


def build():
    objs = {}  # num -> bytes (without "N 0 obj" wrapper)

    n_pages = len(PAGES)
    page_ids = [3 + i * 2 for i in range(n_pages)]
    content_ids = [4 + i * 2 for i in range(n_pages)]

    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join("%d 0 R" % pid for pid in page_ids)
    objs[2] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n_pages)).encode()
    objs[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for i, page in enumerate(PAGES):
        pid, cid = page_ids[i], content_ids[i]
        objs[pid] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     "/Contents %d 0 R /Resources << /Font << /F1 5 0 R >> >> >>" % cid).encode()
        content = page_content(page)
        objs[cid] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += ("%d 0 obj\n" % num).encode() + objs[num] + b"\nendobj\n"

    xref_pos = len(out)
    max_num = max(objs)
    out += ("xref\n0 %d\n" % (max_num + 1)).encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, max_num + 1):
        out += ("%010d 00000 n \n" % offsets[num]).encode()
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (max_num + 1, xref_pos)).encode()
    return bytes(out)


if __name__ == "__main__":
    data = build()
    with open("demo_tender.pdf", "wb") as f:
        f.write(data)
    print("demo_tender.pdf written: %d bytes, valid xref, %d pages" % (len(data), len(PAGES)))
