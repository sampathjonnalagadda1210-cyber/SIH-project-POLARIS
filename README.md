# POLARIS — AI-Powered Recommendation Engine for Indian Standards (PS SIH26108)

**Team ATLAS · Smart India Hackathon 2026**
**POLARIS** = **P**rocurement-**O**riented **L**isting of **A**pplicable **R**eferences in **I**ndian **S**tandards.
*Team ATLAS builds the atlas; POLARIS is the star you navigate by.*

Paste, upload, snap or speak a tender specification → get the **primary Indian Standards (semantic match)**, the **allied/normative-reference graph**, **current editions & amendments**, **mandatory certification flags (ISI/CRS)**, a **Specification Health Score** with **gap detection**, an **explainable assistant with citations**, a **printable assessment report**, and a **tender-ready export block**.

**Zero dependencies.** Python 3 standard library only — nothing to install, no internet needed.

---

## How to run (step by step)

### 1. Check Python (almost every laptop has it)
Command Prompt / Terminal →
```bash
python --version
```
Need 3.8+. If missing: [python.org/downloads](https://www.python.org/downloads/) — tick **"Add Python to PATH"** on Windows.

### 2. Start POLARIS
```bash
cd path\to\sihfinalproto
python server.py
```
(`py server.py` also works on Windows.)

You'll see:
```
========================================================================
  POLARIS - Procurement-Oriented Listing of Applicable References
           in Indian Standards  (Team ATLAS | PS SIH26108 | BIS)
========================================================================
  Corpus loaded : 69 standards
  Server running at: http://localhost:8000
  A browser tab should open automatically - if not, copy the URL above.
  To STOP: click this terminal window, then press Ctrl + C
========================================================================
```
The browser opens by itself. Keep the terminal window open — it *is* the server.
(If 8000 is busy it auto-tries 8001–8005 and tells you the final URL.)

### 3. Stop
Press `Ctrl + C` in the terminal.

---

## How POLARIS works (the pipeline — for the team & judges)

1. **Input** — type/paste (English, हिन्दी, Hinglish), upload `.txt`/`.pdf`, photo/screenshot of a document (in-browser OCR), or speak (voice).
2. **Understand** — tokenizer + Hindi→concept bridge (सीमेंट→cement, सरिया→steel) + synonym/plural expansion identifies product concepts.
3. **Semantic match** — TF-IDF vector space + cosine similarity ranks every standard by *meaning*, not keywords. Explicitly cited IS codes always lead; each mentioned product's best "concept champion" leads its family.
4. **Graph expansion** — BFS depth-2 over each primary standard's normative references reveals the allied standards the spec *implies* (test methods, terminology, safety, installation).
5. **Rules engine** — version/amendment compliance check · mandatory certification (ISI/CRS) mapping · gap detection.
6. **Score & explain** — Spec Health Score + conversational explainability with IS-code citations; honest refusals when data doesn't support an answer.
7. **Act** — tender-ready export block · printable assessment report · interactive Standards Map.

**Architecture:** single-page app (HTML/CSS/JS, zero frameworks) ⇄ Python stdlib REST server (`/api/recommend`, `/api/chat`, `/api/export`, `/api/extract`, `/api/report`, `/api/corpus`, `/api/certifications`) ⇄ `data/standards.json` (69 curated standards: title, scope, kind, edition, amendments, certification flag, normative-reference edges — schema mirrors the BIS catalog, so full-catalog ingest is a data task, not a redesign).

---

## Features & self-test demo cases

### F1. Semantic multi-standard recommendation
**What:** ranks applicable primary standards by meaning; explicit citations lead; per-product champions; category diversity.
**Test:** Analyze tab → **Demo: Tender (EN)** → Analyze → expect **IS 1786 (PRIMARY, 100%)**, IS 432, IS 1489 listed with PRIMARY badges and % scores.

### F2. Multilingual input (EN / हिन्दी / Hinglish)
**What:** Hindi words map to canonical concepts, so Hindi gets the same precision.
**Test:** **Demo: हिन्दी** → Analyze → expect IS 1489 (cement) / IS 1786 (steel) / IS 4985 (pipes) among primaries; health verdict = "Draft specification — no Indian Standards cited yet…".

### F3. Version & Amendment Guardian
**What:** flags outdated, current, amendment-pending citations.
**Test:** **Demo: Outdated citations** → Analyze → expect red **outdated** tags on IS 2062, IS 1239, IS 694 and amber **update amendments** on IS 1077.

### F4. Normative Reference Graph (Standards Map tab)
**What:** interactive graph of primary + allied standards; color = type; dashed red ring = mandatory certification; pan/zoom/tooltips.
**Test:** run any analysis → Standards Map tab → hover IS 4031 (tooltip shows title/edition), scroll to zoom, drag to pan, **click the node** → Assistant explains why it appears.

### F5. Explainable Assistant (Assistant tab)
**What:** intent-routed Q&A with citations and honest refusals.
**Tests:** after the EN demo analysis →
- `Why is IS 1786 recommended?` → semantic-match explanation + 🔗 citation.
- `What is missing from my specification?` → the exact gap list (IS 1608, IS 4031 …).
- `What are the certification requirements?` → mandatory list + scheme process.
- `Latest version of IS 694?` → edition + amendments.
- `Why is IS 4985 recommended?` (after the Hindi demo — IS 4985 not in that set) → honest "not part of the current recommendation set".

### F6. Specification Health Score + Gap Detector
**What:** 0–100 score, verdict, primary/allied citation ratios, missing-standards list.
**Tests:** EN demo → 20/100 "Critical gaps"; Hindi demo → 5/100 "Draft specification…"; a spec citing everything (`Supply of TMT bars Fe500 to IS 1786:2008 with tensile testing per IS 1608, chemical analysis per IS 228, concrete works per IS 456, cubes per IS 1199, water per IS 3025, aggregates per IS 2386, cement tests per IS 4031, terminology per IS 4845`) → score jumps toward full marks.

### F7. Document upload (.txt / .pdf)
**What:** server-side stdlib extraction (zlib inflate for text PDFs) → straight into the analysis textarea.
**Test:** Analyze tab → Upload document → drop any text-based PDF tender (or a .txt) → "✅ Extracted N characters" → Analyze. (Scanned PDFs → use the Image tab.)

### F8. Image/photo OCR (in-browser, honest)
**What:** binarize (Otsu) → glyph segmentation → template matching against runtime-rendered glyphs. Zero cloud, zero deps. Clear printed text works best.
**Test:** Image tab → upload a sharp screenshot of printed tender lines (e.g. large "SUPPLY OF CEMENT") → recognized text appears in the textarea (fix odd characters if any) → Analyze.

### F9. Voice input (mic)
**What:** browser speech recognition (Chrome/Edge), Hindi default.
**Test:** Voice tab → Start listening → say *"सीमेंट सरिया पाइप की आपूर्ति"* → transcript lands in the box → Analyze.

### F10. Standards Library (Library tab)
**What:** searchable/filterable corpus browser with expandable details (scope, edition, amendments, certification, clickable normative references).
**Test:** Library tab → search `1786` → open the row → click the `IS 1608` reference chip → list filters to it. Filter type = "Test Method" to see all test-method standards.

### F11. Assessment Report + tender-ready export (Report tab)
**What:** printable HTML report (score, recommendation table, version compliance, mandatory certifications, gaps) + copy-paste specification block.
**Test:** after any analysis → Report tab → Generate → "Open printable page ↗" → **Print / Save as PDF**; Copy block → paste into Word.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Nothing prints after `python server.py` | Server auto-skips busy ports and opens the browser. If blank, close old python windows and rerun |
| Port busy | Handled automatically (8000→8005), the banner shows the chosen port |
| "Backend unreachable" | The server window was closed — rerun `python server.py` |
| PDF extraction came back empty | It's a scanned/image PDF — use the Image OCR tab |
| Can I upload a REAL government tender? | Yes — tested on a 202-page port-authority tender PDF (CID fonts, 350k+ chars): extraction + smart auto-focus on specification sections + full analysis all work. Huge tenders are auto-excerpted for the best match quality |
| OCR quality poor | Use sharper/larger printed text; it's a demo-grade honest OCR, editable before analysis |
| Voice greyed out | Chrome/Edge only; use other input modes elsewhere |
| Nothing matched | Add material keywords (steel, cement, cable…) — curated 69-standard subset |

## Honesty note
Curated, hand-verified subset (69 standards, 16 categories); editions/amendments representative. Schema is production-shaped — point `data/standards.json` at a full BIS catalog export and nothing else changes. Verify live status at [services.bis.gov.in](https://services.bis.gov.in).
