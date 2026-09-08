"""Golden-fixture harness for PDF figures (INV-C15).

Why not compare PDF bytes
-------------------------
A committed ``.pdf`` golden is the obvious approach and the wrong one here:

* the file carries a creation timestamp and an fpdf2 version string in
  ``/Producer``, so it differs on every run and on every dependency bump;
* page content streams are zlib-compressed, so a real regression shows up as an
  unreadable binary diff;
* ``requirements.txt`` pins ``fpdf2>=2.8.0,<3.0.0``, so a patch release that
  emits the same drawing with different operator formatting would fail the
  golden while nothing about the figure had changed.

What is compared instead
------------------------
:class:`RecordingPdf` wraps a **real** ``FPDF`` and records the drawing calls the
code under test makes *through it*, then delegates each one. So the recording is
taken at our own API boundary — geometry, colours, shapes, fonts and the exact
strings drawn — while text measurement, page breaks and the actual rendering
stay real. A figure regression is then a readable JSON diff, and the produced
document is still a valid PDF that a companion test asserts on.

fpdf2 calls its own methods internally (``multi_cell`` calls ``cell``, the page
footer is invoked during output); those go to the wrapped object, not the proxy,
so they are deliberately absent from the recording. The recording is what our
drawing layer asked for, not what fpdf2 did about it.

Regenerating
------------
``UPDATE_PDF_GOLDEN=1 python -m pytest tests/unit/test_investigation_pack_draw.py``
rewrites the fixtures, then the diff is reviewed like any other change. A missing
fixture fails rather than being created silently: a golden test that writes its
own expectation on first run passes in CI while asserting nothing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import pytest

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "pdf"
UPDATE_ENV = "UPDATE_PDF_GOLDEN"

# Every call our drawing layer is allowed to make on the pdf object that changes
# what lands on the page. Anything not listed (measurement, cursor reads) still
# delegates, it just is not part of the fixture.
RECORDED_CALLS = (
    "add_page",
    "cell",
    "circle",
    "ellipse",
    "line",
    "multi_cell",
    "polygon",
    "rect",
    "set_dash_pattern",
    "set_draw_color",
    "set_fill_color",
    "set_font",
    "set_line_width",
    "set_text_color",
    "set_x",
    "set_xy",
    "set_y",
    "text",
)


def _normalise(value: Any) -> Any:
    """Make one argument JSON-comparable and free of float noise.

    Two decimal places is 0.01 mm — finer than any printer and far finer than a
    change worth reviewing, but coarse enough that binary floating point does not
    make a fixture flap. ``-0.0`` is folded onto ``0.0`` because JSON keeps the
    sign and ``0.0 == -0.0`` in Python, which would make the diff lie.
    """
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return round(value, 2) + 0.0
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalise(value[key]) for key in sorted(value, key=str)}
    return str(value)


class RecordingPdf:
    """Proxy over a real ``FPDF`` that records the drawing calls made through it."""

    def __init__(self, pdf: Any) -> None:
        object.__setattr__(self, "_pdf", pdf)
        object.__setattr__(self, "ops", [])

    @property
    def pdf(self) -> Any:
        return object.__getattribute__(self, "_pdf")

    def __getattr__(self, name: str) -> Any:
        attr = getattr(object.__getattribute__(self, "_pdf"), name)
        if name not in RECORDED_CALLS or not callable(attr):
            return attr

        def recorder(*args: Any, **kwargs: Any) -> Any:
            self.ops.append(
                {
                    "op": name,
                    "args": [_normalise(arg) for arg in args],
                    "kwargs": {key: _normalise(kwargs[key]) for key in sorted(kwargs)},
                }
            )
            return attr(*args, **kwargs)

        return recorder

    def __setattr__(self, name: str, value: Any) -> None:
        # Nothing in the drawing layer sets attributes on the pdf, but if that
        # changes the write must reach the real object rather than the proxy.
        setattr(object.__getattribute__(self, "_pdf"), name, value)


def figure_pdf() -> Any:
    """A pack-shaped A4 page: same margins, break margin and font as a real pack.

    Geometry recorded against different margins would be geometry from a
    different document, so the harness starts where the pack renderer starts.
    """
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(left=16, top=14, right=16)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.set_y(40)
    return pdf


def record(draw: Callable[[Any], Any]) -> tuple[list[dict[str, Any]], bytes, Any]:
    """Run ``draw`` against a recording pdf; return the ops, the PDF bytes and the result."""
    recorder = RecordingPdf(figure_pdf())
    result = draw(recorder)
    return list(recorder.ops), bytes(recorder.pdf.output()), result


def _first_difference(expected: Sequence[Any], actual: Sequence[Any]) -> Optional[str]:
    for index in range(max(len(expected), len(actual))):
        want = expected[index] if index < len(expected) else "<missing>"
        got = actual[index] if index < len(actual) else "<missing>"
        if want != got:
            return f"op {index}:\n  expected: {json.dumps(want)}\n  actual:   {json.dumps(got)}"
    return None


def assert_matches_golden(name: str, ops: Sequence[dict[str, Any]]) -> None:
    """Compare recorded ops with ``tests/fixtures/golden/pdf/<name>.json``."""
    path = GOLDEN_DIR / f"{name}.json"
    payload = json.dumps(list(ops), indent=2) + "\n"

    if os.environ.get(UPDATE_ENV) == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        pytest.fail(f"{UPDATE_ENV}=1 rewrote {path.name}; review the diff and re-run without it")

    if not path.exists():
        pytest.fail(f"Missing golden fixture {path}. Regenerate with {UPDATE_ENV}=1 and review the diff.")

    expected = json.loads(path.read_text(encoding="utf-8"))
    actual = json.loads(payload)
    if expected == actual:
        return

    difference = _first_difference(expected, actual) or "op counts differ"
    pytest.fail(
        f"{path.name} does not match the drawing.\n"
        f"expected {len(expected)} ops, recorded {len(actual)}.\n"
        f"{difference}\n"
        f"If the change is intended, regenerate with {UPDATE_ENV}=1 and review the diff."
    )
