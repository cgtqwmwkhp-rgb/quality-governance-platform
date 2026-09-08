# PDF figure golden fixtures (INV-C15 / INV-C16)

Each file is the recorded sequence of drawing calls one figure makes on the PDF
object — geometry in millimetres, colours as RGB triples, fonts, shapes, and the
exact strings placed on the page. Harness: `tests/unit/_pdf_golden.py`.

## Why calls, not PDF bytes

A committed `.pdf` carries a creation timestamp and the fpdf2 version in
`/Producer`, and its page content is zlib-compressed. It would differ on every
run, and a real regression would surface as a binary diff. `requirements.txt`
also pins `fpdf2>=2.8.0,<3.0.0`, so a patch release emitting the same drawing
with different operator formatting would fail a byte golden while nothing about
the figure had changed.

Recording at our own API boundary instead keeps the diff reviewable and pins the
thing that matters: where the ink goes. The recorder wraps a **real** `FPDF`, so
text measurement, page breaks and rendering are not simulated, and the companion
test asserts the produced document is still a valid PDF.

Calls fpdf2 makes on itself (`multi_cell` → `cell`, the page footer during
output) go to the wrapped object and are deliberately absent: the fixture is
what the drawing layer asked for, not what fpdf2 did about it.

## Files

| Fixture | Figure |
|---|---|
| `investigation_chronology_two_lane.json` | Chronology with both origins: source-record entries above the time axis, the investigation's own below it |
| `investigation_chronology_single_event.json` | Chronology with one entry — zero time span, so the axis has a single centred stamp instead of two end dates |
| `investigation_icam_four_bands.json` | ICAM contributing factors with all four categories populated: sub-causes, all three HSG245 depths, and one factor whose depth nobody recorded (no chip, same text column) |
| `investigation_icam_partial_bands.json` | ICAM contributing factors in two categories only — the other two bands state "None recorded" rather than being dropped |

## Regenerating

```bash
UPDATE_PDF_GOLDEN=1 python -m pytest tests/unit/test_investigation_pack_draw.py
```

Regenerating rewrites **every** fixture, so check `git diff` shows only the
figures you meant to change.

That rewrites the fixtures and **fails on purpose**, so the diff has to be read
before it is committed. Re-run without the variable to confirm green.

A missing fixture fails rather than being created: a golden test that writes its
own expectation on first run passes in CI while asserting nothing.
