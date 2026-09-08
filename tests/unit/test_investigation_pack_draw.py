"""Unit tests for the pack drawing helpers, the chronology figure (INV-C15) and the ICAM diagram (INV-C16)."""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.domain.services import investigation_pack_draw as draw
from src.domain.services.investigation_pack_draw import (
    ICAM_CATEGORIES,
    ICAM_CATEGORY_LABELS,
    ICAM_DEPTH_LABELS,
    ICAM_DEPTH_SHAPES,
    ICAM_DEPTHS,
    ORIGIN_INVESTIGATION,
    ORIGIN_SOURCE,
    ChronologyEvent,
    ChronologySet,
    Frame,
    IcamFactor,
    IcamFactorSet,
    LegendEntry,
    chronology_summary_line,
    content_width,
    draw_arrow,
    draw_chronology_figure,
    draw_icam_factors_figure,
    draw_legend,
    draw_marker,
    draw_text,
    fit_text,
    format_date,
    format_stamp,
    humanise_key,
    icam_figure_height,
    icam_summary_line,
    linear_positions,
    mix,
    normalise_chronology_events,
    normalise_icam_factors,
    pdf_safe,
    plural,
    readable_text_rgb,
    relative_luminance,
    reserve_frame,
    shade,
    space_remaining,
    tint,
    vector_state,
)
from tests.unit._pdf_golden import assert_matches_golden, figure_pdf, record

BASE = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)


def _event(
    offset_days: float,
    *,
    origin: str = ORIGIN_SOURCE,
    event_type: str = "SOURCE_AUDIT",
    label: str | None = "Incident \u00b7 update",
    value: str | None = "Field changed",
    row_id: int = 1,
) -> dict:
    """One timeline event in the shape `GET /investigations/{id}/timeline` serialises."""
    metadata: dict = {"origin": origin}
    if label is not None:
        metadata["source_label"] = label
    return {
        "id": row_id,
        "event_type": event_type,
        "field_path": None,
        "old_value": None,
        "new_value": value,
        "actor_id": None,
        "actor_name": None,
        "event_metadata": metadata,
        "version": None,
        "created_at": (BASE + timedelta(days=offset_days)).isoformat(),
    }


def _fixture_events() -> list[dict]:
    """A fixed, readable chronology: a case running before an investigation was raised."""
    events = [
        _event(0, row_id=-11, label="Incident \u00b7 create"),
        _event(3.5, row_id=-21, label="Incident \u00b7 running sheet", event_type="SOURCE_RUNNING_SHEET"),
        _event(9, row_id=-31, label="Incident \u00b7 update"),
        _event(16, row_id=-41, label="Incident \u00b7 status_changed"),
    ]
    events += [
        _event(
            16.25, origin=ORIGIN_INVESTIGATION, event_type="INVESTIGATION_CREATED", label=None, row_id=1, value=None
        ),
        _event(21, origin=ORIGIN_INVESTIGATION, event_type="SECTION_UPDATED", label=None, row_id=2, value="section_1"),
        _event(30, origin=ORIGIN_INVESTIGATION, event_type="STATUS_CHANGED", label=None, row_id=3, value="completed"),
    ]
    return events


class TestTextPrimitives:
    def test_latin1_replacement_never_invents_content(self) -> None:
        assert pdf_safe("Ystrad \u2014 Mynach") == "Ystrad ? Mynach"
        assert pdf_safe(None) == ""
        assert pdf_safe("abcdef", max_len=5) == "ab..."

    def test_carriage_returns_are_normalised(self) -> None:
        assert pdf_safe("a\r\nb\rc") == "a\nb\nc"

    def test_humanise_key_matches_the_pack_renderer_contract(self) -> None:
        assert humanise_key("section_1_details") == "Section 1 details"
        assert humanise_key("") == "Untitled"

    def test_fit_text_ellipsizes_to_the_rendered_width(self) -> None:
        pdf = figure_pdf()
        pdf.set_font("Helvetica", "", 8)

        fitted = fit_text(pdf, "A very long chronology entry label " * 6, 40)

        assert fitted.endswith("...")
        assert pdf.get_string_width(fitted) <= 40

    def test_fit_text_returns_empty_rather_than_overflowing_a_tiny_cell(self) -> None:
        pdf = figure_pdf()
        pdf.set_font("Helvetica", "", 8)

        assert fit_text(pdf, "anything at all", 0.5) == ""

    def test_plural_always_states_the_count(self) -> None:
        assert plural(1, "entry", "entries") == "1 entry"
        assert plural(0, "entry", "entries") == "0 entries"
        assert plural(4, "entry", "entries") == "4 entries"


class TestColourHelpers:
    def test_mix_is_clamped_and_ordered(self) -> None:
        assert mix((0, 0, 0), (255, 255, 255), 0.0) == (0, 0, 0)
        assert mix((0, 0, 0), (255, 255, 255), 1.0) == (255, 255, 255)
        assert mix((0, 0, 0), (255, 255, 255), 0.5) == (128, 128, 128)
        assert mix((0, 0, 0), (255, 255, 255), 5.0) == (255, 255, 255)
        assert mix((0, 0, 0), (255, 255, 255), -5.0) == (0, 0, 0)

    def test_tint_and_shade_move_in_opposite_directions(self) -> None:
        brand = (78, 118, 10)

        assert tint(brand, 0.5) > brand
        assert shade(brand, 0.5) < brand

    def test_readable_text_picks_contrast_not_a_fixed_colour(self) -> None:
        assert readable_text_rgb((255, 255, 255)) == (0, 0, 0)
        assert readable_text_rgb((78, 118, 10)) == (255, 255, 255)
        assert relative_luminance((0, 0, 0)) == pytest.approx(0.0)
        assert relative_luminance((255, 255, 255)) == pytest.approx(1.0)


class TestFrameAndReservation:
    def test_frame_geometry(self) -> None:
        frame = Frame(10, 20, 100, 40)

        assert (frame.right, frame.bottom) == (110, 60)
        assert (frame.cx, frame.cy) == (60, 40)
        assert frame.inset(5) == Frame(15, 25, 90, 30)
        assert frame.inset(200).w == 0

    def test_reserve_frame_uses_the_content_width_and_advances_the_cursor(self) -> None:
        pdf = figure_pdf()
        start = pdf.get_y()

        frame = reserve_frame(pdf, 30, top_gap=2)

        assert frame.x == pdf.l_margin
        assert frame.w == pytest.approx(content_width(pdf))
        assert frame.y == pytest.approx(start + 2)
        assert pdf.get_y() == pytest.approx(frame.bottom)

    def test_reserve_frame_breaks_the_page_rather_than_drawing_over_the_footer(self) -> None:
        pdf = figure_pdf()
        pdf.set_y(pdf.h - pdf.b_margin - 10)

        frame = reserve_frame(pdf, 40)

        assert pdf.page_no() == 2
        assert frame.y == pytest.approx(pdf.t_margin)
        assert frame.bottom <= pdf.h - pdf.b_margin

    def test_reserve_frame_clamps_a_figure_taller_than_a_page(self) -> None:
        pdf = figure_pdf()

        frame = reserve_frame(pdf, 10_000)

        assert frame.bottom <= pdf.h - pdf.b_margin

    def test_reserve_frame_refuses_a_non_positive_height(self) -> None:
        with pytest.raises(ValueError):
            reserve_frame(figure_pdf(), 0)

    def test_space_remaining_respects_the_break_margin(self) -> None:
        pdf = figure_pdf()

        assert space_remaining(pdf) == pytest.approx(pdf.h - pdf.b_margin - pdf.get_y())


class TestVectorState:
    def test_restores_font_and_line_width_after_drawing(self) -> None:
        pdf = figure_pdf()
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_line_width(0.75)

        with vector_state(pdf):
            pdf.set_font("Helvetica", "I", 6)
            pdf.set_line_width(0.1)
            pdf.set_dash_pattern(dash=2, gap=2)

        assert (pdf.font_style, round(pdf.font_size_pt), pdf.line_width) == ("B", 12, 0.75)

    def test_restores_state_even_when_the_figure_raises(self) -> None:
        pdf = figure_pdf()
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_line_width(0.75)

        with pytest.raises(RuntimeError):
            with vector_state(pdf):
                pdf.set_line_width(0.1)
                raise RuntimeError("figure failed")

        assert (pdf.font_style, round(pdf.font_size_pt), pdf.line_width) == ("B", 12, 0.75)


class TestDrawingPrimitives:
    def test_marker_shapes_use_distinct_operations_so_mono_print_still_reads(self) -> None:
        shapes = {}
        for shape in ("circle", "square", "diamond", "triangle"):
            ops, _, _ = record(lambda pdf, shape=shape: draw_marker(pdf, 50, 50, 2, shape=shape, fill=(0, 0, 0)))
            shapes[shape] = [op["op"] for op in ops if op["op"] in {"ellipse", "rect", "polygon"}]

        assert shapes["circle"] == ["ellipse"]
        assert shapes["square"] == ["rect"]
        assert shapes["diamond"] == ["polygon"]
        assert shapes["triangle"] == ["polygon"]

    def test_unknown_marker_shape_falls_back_to_a_circle_rather_than_nothing(self) -> None:
        ops, _, _ = record(lambda pdf: draw_marker(pdf, 50, 50, 2, shape="hexagram", fill=(0, 0, 0)))

        assert [op["op"] for op in ops if op["op"] in {"ellipse", "rect", "polygon"}] == ["ellipse"]

    def test_marker_is_centred_on_its_point(self) -> None:
        ops, _, _ = record(lambda pdf: draw_marker(pdf, 50, 60, 4, shape="circle", fill=(0, 0, 0)))
        ellipse = next(op for op in ops if op["op"] == "ellipse")

        assert ellipse["args"] == [48.0, 58.0, 4.0, 4.0]

    def test_zero_length_arrow_draws_nothing(self) -> None:
        ops, _, _ = record(lambda pdf: draw_arrow(pdf, 20, 20, 20, 20))

        assert ops == []

    def test_arrow_draws_a_shaft_and_a_filled_head(self) -> None:
        ops, _, _ = record(lambda pdf: draw_arrow(pdf, 20, 20, 60, 20))

        assert [op["op"] for op in ops if op["op"] in {"line", "polygon"}] == ["line", "polygon"]
        head = next(op for op in ops if op["op"] == "polygon")
        assert head["kwargs"]["style"] == "F"
        assert head["args"][0][0] == [60.0, 20.0]

    def test_draw_text_alignment_moves_the_origin_not_the_string(self) -> None:
        ops, _, drawn = record(lambda pdf: draw_text(pdf, 100, 50, "Chronology", size=8, align="R"))
        placed = next(op for op in ops if op["op"] == "text")

        assert drawn == "Chronology"
        assert placed["args"][0] < 100
        assert placed["args"][2] == "Chronology"

    def test_draw_text_refuses_to_paint_outside_its_width(self) -> None:
        ops, _, drawn = record(lambda pdf: draw_text(pdf, 20, 50, "x" * 400, size=8, max_width=20))
        placed = next(op for op in ops if op["op"] == "text")

        assert drawn.endswith("...")
        assert placed["args"][2] == drawn

    def test_legend_truncates_instead_of_overflowing(self) -> None:
        entries = [LegendEntry(f"Legend entry number {i}", (0, 0, 0)) for i in range(8)]

        ops, _, width = record(lambda pdf: draw_legend(pdf, 16, 50, entries, max_width=40))

        assert width <= 40
        assert 0 < len([op for op in ops if op["op"] == "text"]) < 8


class TestLinearPositions:
    def test_maps_values_across_the_span(self) -> None:
        assert linear_positions([0, 5, 10], 0, 100) == [0, 50, 100]

    def test_zero_span_lands_on_the_midpoint_rather_than_dividing_by_zero(self) -> None:
        assert linear_positions([7, 7, 7], 20, 120) == [70, 70, 70]
        assert linear_positions([7], 20, 120) == [70]

    def test_empty_input_is_empty_output(self) -> None:
        assert linear_positions([], 0, 100) == []


class TestOriginContract:
    def test_origin_values_match_the_c9_timeline_module(self) -> None:
        # The drawing layer copies these rather than importing the C9 module,
        # which pulls in four ORM models. This test is what stops them drifting.
        from src.domain.services import investigation_parent_timeline as c9

        assert (ORIGIN_SOURCE, ORIGIN_INVESTIGATION) == (c9.ORIGIN_SOURCE, c9.ORIGIN_INVESTIGATION)


class TestNormaliseChronologyEvents:
    def test_orders_oldest_first_across_string_and_datetime_timestamps(self) -> None:
        raw = [
            {"event_type": "B", "created_at": datetime(2026, 5, 3, 9, 0, tzinfo=timezone.utc)},
            {"event_type": "A", "created_at": "2026-05-01T09:00:00+00:00"},
            {"event_type": "C", "created_at": "2026-05-05T09:00:00Z"},
        ]

        chronology = normalise_chronology_events(raw)

        assert [event.label for event in chronology.events] == ["A", "B", "C"]

    def test_naive_timestamps_are_read_as_utc_not_local(self) -> None:
        chronology = normalise_chronology_events([{"event_type": "A", "created_at": "2026-05-01T09:00:00"}])

        assert chronology.events[0].at == datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)

    def test_offset_timestamps_are_converted_to_utc(self) -> None:
        chronology = normalise_chronology_events([{"event_type": "A", "created_at": "2026-05-01T09:00:00+02:00"}])

        assert chronology.events[0].at == datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc)

    def test_origin_comes_from_c9_metadata_and_defaults_to_the_investigation(self) -> None:
        raw = [
            _event(0, origin=ORIGIN_SOURCE),
            _event(1, origin=ORIGIN_INVESTIGATION, label=None),
            {"event_type": "PRE_C9_EVENT", "created_at": "2026-05-03T09:00:00+00:00"},
            {"event_type": "NO_ORIGIN", "created_at": "2026-05-04T09:00:00+00:00", "event_metadata": {}},
            {"event_type": "ODD", "created_at": "2026-05-05T09:00:00+00:00", "event_metadata": {"origin": "elsewhere"}},
        ]

        origins = [event.origin for event in normalise_chronology_events(raw).events]

        assert origins == [
            ORIGIN_SOURCE,
            ORIGIN_INVESTIGATION,
            ORIGIN_INVESTIGATION,
            ORIGIN_INVESTIGATION,
            ORIGIN_INVESTIGATION,
        ]

    def test_source_label_is_preferred_and_event_type_is_the_fallback(self) -> None:
        raw = [
            _event(0, origin=ORIGIN_SOURCE, label="Incident \u00b7 running sheet"),
            _event(1, origin=ORIGIN_SOURCE, label=None, event_type="SOURCE_AUDIT"),
            _event(2, origin=ORIGIN_INVESTIGATION, label="ignored for investigation rows"),
            {"created_at": "2026-05-09T09:00:00+00:00"},
        ]

        labels = [event.label for event in normalise_chronology_events(raw).events]

        assert labels == ["Incident \u00b7 running sheet", "Source audit", "Source audit", "Timeline entry"]

    def test_shouting_event_types_are_not_rendered_shouting(self) -> None:
        chronology = normalise_chronology_events(
            [{"event_type": "STATUS_CHANGED", "created_at": "2026-05-01T09:00:00+00:00"}]
        )

        assert chronology.events[0].label == "Status changed"

    def test_undated_entries_are_counted_not_dropped_silently(self) -> None:
        raw = [
            _event(0),
            {"event_type": "A", "created_at": None},
            {"event_type": "B", "created_at": "not a date"},
            {"event_type": "C"},
        ]

        chronology = normalise_chronology_events(raw)

        assert len(chronology.events) == 1
        assert chronology.unplaceable == 3

    def test_malformed_input_yields_an_empty_set_rather_than_raising(self) -> None:
        for raw in (None, "nonsense", 7, {"created_at": "2026-05-01T09:00:00+00:00"}):
            assert normalise_chronology_events(raw) == ChronologySet()

    def test_junk_entries_inside_a_list_are_counted_as_unplaceable(self) -> None:
        chronology = normalise_chronology_events([None, 3, "x", _event(0)])

        assert (len(chronology.events), chronology.unplaceable) == (1, 3)

    def test_row_objects_work_as_well_as_dicts(self) -> None:
        class Row:
            created_at = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
            event_type = "SOURCE_AUDIT"
            new_value = "Reporter added"
            event_metadata = {"origin": "source", "source_label": "Incident \u00b7 update"}

        chronology = normalise_chronology_events([Row()])

        assert chronology.events[0].origin == ORIGIN_SOURCE
        assert chronology.events[0].label == "Incident \u00b7 update"

    def test_detail_is_bounded_and_latin1_safe(self) -> None:
        chronology = normalise_chronology_events(
            [_event(0, value="\u2014 " + "x" * 5000)],
        )

        detail = chronology.events[0].detail
        assert detail is not None
        assert len(detail) <= draw._DETAIL_CHARS
        assert detail.encode("latin-1").decode("latin-1") == detail
        assert detail.startswith("? ")

    def test_non_scalar_values_do_not_become_a_repr_on_the_page(self) -> None:
        chronology = normalise_chronology_events(
            [{"event_type": "A", "created_at": "2026-05-01T09:00:00+00:00", "new_value": {"old": "x"}}]
        )

        assert chronology.events[0].detail is None

    def test_the_cap_keeps_the_newest_and_reports_what_it_dropped(self) -> None:
        raw = [_event(index) for index in range(30)]

        chronology = normalise_chronology_events(raw, cap=10)

        assert len(chronology.events) == 10
        assert chronology.omitted == 20
        assert chronology.events[-1].at == max(event.at for event in chronology.events)
        assert chronology.events[0].at == BASE + timedelta(days=20)

    def test_default_cap_is_bounded(self) -> None:
        assert draw.CHRONOLOGY_EVENT_CAP == 500
        assert len(normalise_chronology_events([_event(i) for i in range(600)]).events) == 500


class TestChronologySummaryLine:
    def test_states_counts_per_origin_and_the_span(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())

        line = chronology_summary_line(chronology)

        assert line == (
            "7 entries between 01 May 2026 and 31 May 2026: " "4 from the source record, 3 from the investigation."
        )

    def test_single_event_reads_as_a_date_not_a_span(self) -> None:
        line = chronology_summary_line(normalise_chronology_events([_event(0)]))

        assert line == "1 entry on 01 May 2026: 1 from the source record, 0 from the investigation."

    def test_empty_set_says_so_rather_than_claiming_a_span(self) -> None:
        assert chronology_summary_line(ChronologySet()) == "No chronology entries are recorded for this investigation."

    def test_dates_are_locale_independent(self) -> None:
        assert format_date(BASE) == "01 May 2026"
        assert format_stamp(BASE) == "01 May 2026 08:00 UTC"


class TestChronologyFigure:
    def test_two_lane_figure_matches_the_golden_fixture(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())

        ops, pdf_bytes, frame = record(
            lambda pdf: draw_chronology_figure(pdf, chronology, brand=(78, 118, 10)),
        )

        assert_matches_golden("investigation_chronology_two_lane", ops)
        assert pdf_bytes.startswith(b"%PDF-")
        assert frame.h == pytest.approx(draw.CHRONOLOGY_FIGURE_HEIGHT)

    def test_single_event_figure_matches_the_golden_fixture(self) -> None:
        chronology = normalise_chronology_events([_event(0, label="Incident \u00b7 create")])

        ops, pdf_bytes, _ = record(lambda pdf: draw_chronology_figure(pdf, chronology, brand=(78, 118, 10)))

        assert_matches_golden("investigation_chronology_single_event", ops)
        assert pdf_bytes.startswith(b"%PDF-")

    def test_source_events_sit_above_the_axis_and_investigation_events_below(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())

        ops, _, frame = record(lambda pdf: draw_chronology_figure(pdf, chronology, brand=(78, 118, 10)))

        circles = [op["args"][1] for op in ops if op["op"] == "ellipse"]
        squares = [op["args"][1] for op in ops if op["op"] == "rect"]
        assert len(circles) == 4 + 1  # four source markers plus the legend key
        assert len(squares) == 3 + 1  # three investigation markers plus the legend key
        figure_circles = [y for y in circles if y > frame.y + 8]
        figure_squares = [y for y in squares if y > frame.y + 8]
        assert max(figure_circles) < min(figure_squares)

    def test_markers_are_placed_by_time_not_by_index(self) -> None:
        # Two events a day apart then one a month later must not be evenly spaced.
        raw = [_event(0, row_id=1), _event(1, row_id=2), _event(31, row_id=3)]
        chronology = normalise_chronology_events(raw)

        ops, _, _ = record(lambda pdf: draw_chronology_figure(pdf, chronology, brand=(78, 118, 10)))
        xs = sorted(op["args"][0] for op in ops if op["op"] == "ellipse")[1:]  # drop the legend key

        assert xs[1] - xs[0] < (xs[2] - xs[1]) / 10

    def test_every_event_gets_a_marker_even_when_timestamps_collide(self) -> None:
        raw = [_event(0, row_id=index) for index in range(6)]
        chronology = normalise_chronology_events(raw)

        ops, _, _ = record(lambda pdf: draw_chronology_figure(pdf, chronology, brand=(78, 118, 10)))
        xs = [op["args"][0] for op in ops if op["op"] == "ellipse"][1:]

        assert len(xs) == 6
        assert len(set(xs)) == 1  # identical timestamps really are the same instant

    def test_figure_stays_inside_its_frame_and_the_printable_page(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())
        pdf = figure_pdf()

        frame = draw_chronology_figure(pdf, chronology, brand=(78, 118, 10))

        assert frame.bottom <= pdf.h - pdf.b_margin
        assert frame.right <= pdf.w - pdf.r_margin

    def test_empty_chronology_reserves_nothing_it_cannot_fill(self) -> None:
        ops, _, frame = record(lambda pdf: draw_chronology_figure(pdf, ChronologySet(), brand=(78, 118, 10)))

        assert ops == [{"op": "set_y", "args": [frame.bottom], "kwargs": {}}]

    def test_figure_breaks_the_page_rather_than_drawing_over_the_footer(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())
        pdf = figure_pdf()
        pdf.set_y(pdf.h - pdf.b_margin - 12)

        frame = draw_chronology_figure(pdf, chronology, brand=(78, 118, 10))

        assert pdf.page_no() == 2
        assert frame.bottom <= pdf.h - pdf.b_margin

    def test_colour_and_font_state_is_left_clean_for_the_next_section(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())
        pdf = figure_pdf()
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_line_width(0.6)

        draw_chronology_figure(pdf, chronology, brand=(78, 118, 10))

        assert (pdf.font_style, round(pdf.font_size_pt), pdf.line_width) == ("B", 11, 0.6)

    def test_figure_text_is_latin1_safe(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())

        ops, _, _ = record(lambda pdf: draw_chronology_figure(pdf, chronology, brand=(78, 118, 10)))

        for op in ops:
            if op["op"] == "text":
                assert op["args"][2].encode("latin-1").decode("latin-1") == op["args"][2]


class TestGoldenHarness:
    def test_a_changed_drawing_fails_the_golden_comparison(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())
        ops, _, _ = record(lambda pdf: draw_chronology_figure(pdf, chronology, brand=(1, 2, 3)))

        with pytest.raises(pytest.fail.Exception, match="does not match the drawing"):
            assert_matches_golden("investigation_chronology_two_lane", ops)

    def test_a_missing_fixture_fails_rather_than_being_written(self) -> None:
        with pytest.raises(pytest.fail.Exception, match="Missing golden fixture"):
            assert_matches_golden("investigation_chronology_no_such_fixture", [])

    def test_recording_delegates_to_a_real_pdf_document(self) -> None:
        ops, pdf_bytes, _ = record(lambda pdf: draw_text(pdf, 20, 50, "Recorded", size=9))

        assert ops[-1]["op"] == "text"
        assert pdf_bytes.startswith(b"%PDF-")
        from pypdf import PdfReader

        assert "Recorded" in (PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text() or "")

    def test_fixtures_are_committed_json_a_reviewer_can_read(self) -> None:
        from tests.unit._pdf_golden import GOLDEN_DIR

        for name in ("investigation_chronology_two_lane", "investigation_chronology_single_event"):
            payload = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
            assert payload and all({"op", "args", "kwargs"} == set(entry) for entry in payload)


class TestChronologyEventShape:
    def test_origin_label_falls_back_rather_than_showing_a_raw_key(self) -> None:
        event = ChronologyEvent(at=BASE, origin="something-else", label="x")

        assert event.origin_label == "Investigation"
        assert ChronologyEvent(at=BASE, origin=ORIGIN_SOURCE, label="x").origin_label == "Source record"

    def test_chronology_set_reports_its_own_span_and_counts(self) -> None:
        chronology = normalise_chronology_events(_fixture_events())

        assert chronology.first == BASE
        assert chronology.last == BASE + timedelta(days=30)
        assert chronology.count_for(ORIGIN_SOURCE) == 4
        assert bool(ChronologySet()) is False
        assert ChronologySet().first is None


# ---------------------------------------------------------------------------
# ICAM contributing-factor figure (INV-C16)
# ---------------------------------------------------------------------------

BRAND = (78, 118, 10)

ORGANISATIONAL = "organisational_factors"
TASK_ENVIRONMENTAL = "task_environmental_conditions"
INDIVIDUAL_TEAM = "individual_team_actions"
ABSENT_DEFENCES = "absent_failed_defences"


def _factor(**overrides: object) -> dict:
    """One stored ICAM factor in the shape the pack payload carries."""
    entry: dict = {
        "id": 1,
        "category": ORGANISATIONAL,
        "cause": "No refresher training schedule",
        "sub_causes": [],
        "depth": None,
    }
    entry.update(overrides)
    return entry


def _fixture_factors() -> dict:
    """Factors in all four ICAM categories: sub-causes, all three depths, and one unclassified."""
    return {
        "factors": [
            _factor(
                id=4,
                cause="No refresher training schedule",
                sub_causes=["Budget withdrawn", "No owner named"],
                depth="underlying",
            ),
            _factor(id=7, cause="Guard removal needs no permit to work", depth="root"),
            _factor(
                id=2,
                category=TASK_ENVIRONMENTAL,
                cause="Mill floor poorly lit at shift change",
                depth="immediate",
            ),
            _factor(id=9, category=INDIVIDUAL_TEAM, cause="Operator reached into the running mill"),
            _factor(
                id=5,
                category=ABSENT_DEFENCES,
                cause="Interlock bypassed with a spare key",
                depth="immediate",
            ),
        ],
        "unmapped_categories": [],
        "unpresentable": 0,
    }


def _texts(ops: list[dict]) -> list[str]:
    return [op["args"][2] for op in ops if op["op"] == "text"]


def _baseline_of(ops: list[dict], needle: str) -> float:
    return next(op["args"][1] for op in ops if op["op"] == "text" and needle in op["args"][2])


class TestIcamVocabularyContract:
    def test_categories_labels_and_depths_are_pinned_to_the_c12_service(self) -> None:
        # The drawing layer copies this vocabulary rather than importing the
        # factors service, which pulls in four ORM models. This test is what
        # stops a taxonomy change silently emptying a band.
        from src.domain.models.rca_tools import CausalDepth
        from src.domain.services import investigation_factors_service as c12

        assert ICAM_CATEGORIES == tuple(category.value for category in c12.ICAM_CATEGORY_ORDER)
        assert ICAM_CATEGORY_LABELS == {
            category.value: c12.CATEGORY_LABELS[category] for category in c12.ICAM_CATEGORY_ORDER
        }
        assert ICAM_DEPTHS == tuple(depth.value for depth in CausalDepth)
        assert ICAM_DEPTH_LABELS == {depth.value: c12.DEPTH_LABELS[depth].capitalize() for depth in CausalDepth}
        assert draw._ICAM_SUB_CAUSE_CAP == c12.FACTOR_SUB_CAUSES_MAX

    def test_every_depth_has_its_own_marker_shape_so_mono_print_still_reads(self) -> None:
        assert set(ICAM_DEPTH_SHAPES) == set(ICAM_DEPTHS)
        assert len(set(ICAM_DEPTH_SHAPES.values())) == len(ICAM_DEPTHS)

    def test_there_is_no_fifth_taxonomy_and_no_6m_band(self) -> None:
        for legacy in ("people", "machine", "material", "measurement", "method", "mother_nature"):
            assert legacy not in ICAM_CATEGORIES
            assert legacy not in ICAM_CATEGORY_LABELS


class TestNormaliseIcamFactors:
    def test_reads_ids_categories_sub_causes_and_depth_from_the_stored_causes(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())

        assert [(f.id, f.category, f.depth) for f in factors.factors] == [
            (4, ORGANISATIONAL, "underlying"),
            (7, ORGANISATIONAL, "root"),
            (2, TASK_ENVIRONMENTAL, "immediate"),
            (9, INDIVIDUAL_TEAM, None),
            (5, ABSENT_DEFENCES, "immediate"),
        ]
        assert factors.factors[0].sub_causes == ("Budget withdrawn", "No owner named")
        assert factors.with_depth == 4

    def test_orders_by_icam_category_then_stored_position_not_by_id(self) -> None:
        raw = {
            "factors": [
                _factor(id=99, category=ABSENT_DEFENCES, cause="last category, lowest position"),
                _factor(id=1, category=ORGANISATIONAL, cause="first category, second position"),
                _factor(id=2, category=ORGANISATIONAL, cause="first category, first position"),
            ]
        }

        factors = normalise_icam_factors(raw)

        assert [f.cause for f in factors.factors] == [
            "first category, second position",
            "first category, first position",
            "last category, lowest position",
        ]

    def test_a_bare_list_is_accepted_as_well_as_the_payload_mapping(self) -> None:
        factors = normalise_icam_factors(_fixture_factors()["factors"])

        assert len(factors.factors) == 5
        assert factors.unpresentable == 0

    def test_an_investigation_factor_object_from_c12_reads_unchanged(self) -> None:
        # Proves the enum members are unwrapped to their stored values rather
        # than str()-ed into "FishboneCategory.ORGANISATIONAL".
        from src.domain.models.rca_tools import CausalDepth, FishboneCategory
        from src.domain.services.investigation_factors_service import InvestigationFactor

        row = InvestigationFactor(
            id=3,
            investigation_id=11,
            category=FishboneCategory.ABSENT_FAILED_DEFENCES,
            cause="Interlock bypassed",
            sub_causes=["Spare key kept on the panel"],
            depth=CausalDepth.ROOT,
        )

        factors = normalise_icam_factors([row])

        assert [(f.id, f.category, f.depth) for f in factors.factors] == [(3, ABSENT_DEFENCES, "root")]
        assert factors.factors[0].label == "Interlock bypassed (Spare key kept on the panel)"

    def test_a_pre_dec1_6m_key_is_counted_and_named_never_recategorised(self) -> None:
        raw = {
            "factors": [
                _factor(id=1, cause="A real ICAM factor"),
                _factor(id=2, category="machine", cause="Conveyor belt worn"),
                _factor(id=3, category="people", cause="Operator not briefed"),
            ]
        }

        factors = normalise_icam_factors(raw)

        assert [f.cause for f in factors.factors] == ["A real ICAM factor"]
        assert factors.unmapped_categories == ("machine", "people")
        assert factors.unpresentable == 2
        for category in ICAM_CATEGORIES:
            assert "Conveyor belt worn" not in [f.cause for f in factors.for_category(category)]

    def test_c12_counts_on_the_payload_are_carried_not_recomputed(self) -> None:
        raw = {
            "factors": [_factor(id=1)],
            "unmapped_categories": ["mother_nature"],
            "unpresentable": 3,
        }

        factors = normalise_icam_factors(raw)

        assert factors.unmapped_categories == ("mother_nature",)
        assert factors.unpresentable == 3

    def test_an_entry_with_no_usable_cause_is_counted_not_guessed_at(self) -> None:
        raw = {
            "factors": [
                _factor(id=1, cause="   "),
                _factor(id=2, cause=None),
                _factor(id=3, cause={"nested": "object"}),
                _factor(id=4, cause="Kept"),
            ]
        }

        factors = normalise_icam_factors(raw)

        assert [f.cause for f in factors.factors] == ["Kept"]
        assert factors.unpresentable == 3

    def test_an_unrecognised_depth_reads_as_no_recorded_depth_not_as_immediate(self) -> None:
        factors = normalise_icam_factors([_factor(id=1, depth="catastrophic"), _factor(id=2, depth="")])

        assert [f.depth for f in factors.factors] == [None, None]
        assert [f.depth_label for f in factors.factors] == [None, None]

    def test_depth_is_case_insensitive_but_never_invented(self) -> None:
        assert normalise_icam_factors([_factor(depth="ROOT")]).factors[0].depth == "root"
        assert normalise_icam_factors([_factor(depth=" Underlying ")]).factors[0].depth == "underlying"

    def test_junk_and_malformed_input_yields_an_empty_set_rather_than_raising(self) -> None:
        for raw in (None, "nonsense", 7, {"factors": "nonsense"}, {}):
            assert normalise_icam_factors(raw).factors == ()

    def test_junk_entries_inside_a_list_are_counted_as_unpresentable(self) -> None:
        factors = normalise_icam_factors([None, 3, "x", _factor(id=1)])

        assert (len(factors.factors), factors.unpresentable) == (1, 3)

    def test_counts_survive_a_payload_whose_factor_list_is_unusable(self) -> None:
        factors = normalise_icam_factors({"factors": None, "unmapped_categories": ["people"], "unpresentable": 2})

        assert factors.factors == ()
        assert factors.unmapped_categories == ("people",)
        assert factors.unpresentable == 2

    def test_sub_causes_are_bounded_latin1_and_keep_their_order(self) -> None:
        factors = normalise_icam_factors(
            [_factor(sub_causes=["\u2014 first", "", None, {"a": 1}, "x" * 5000] + [f"s{i}" for i in range(40)])]
        )

        sub_causes = factors.factors[0].sub_causes
        assert sub_causes[0] == "? first"
        assert len(sub_causes) <= draw._ICAM_SUB_CAUSE_CAP
        for text in sub_causes:
            assert len(text) <= draw._ICAM_SUB_CAUSE_CHARS
            assert text.encode("latin-1").decode("latin-1") == text

    def test_cause_text_is_bounded_and_latin1_safe(self) -> None:
        factors = normalise_icam_factors([_factor(cause="\u2014 " + "x" * 5000)])

        cause = factors.factors[0].cause
        assert len(cause) <= draw._ICAM_CAUSE_CHARS
        assert cause.startswith("? ")

    def test_a_missing_id_reads_as_zero_rather_than_raising(self) -> None:
        factors = normalise_icam_factors([_factor(id=None), _factor(id="not a number"), _factor(id="12")])

        assert [f.id for f in factors.factors] == [0, 0, 12]

    def test_the_cap_keeps_icam_order_and_reports_what_it_dropped(self) -> None:
        raw = [_factor(id=index, cause=f"Factor {index}") for index in range(40)]

        factors = normalise_icam_factors(raw, cap=10)

        assert len(factors.factors) == 10
        assert factors.omitted == 30
        assert [f.cause for f in factors.factors] == [f"Factor {index}" for index in range(10)]

    def test_default_cap_keeps_the_figure_inside_one_page(self) -> None:
        assert draw.ICAM_FACTOR_CAP == 24
        capped = normalise_icam_factors([_factor(id=index) for index in range(200)])
        assert len(capped.factors) == 24
        assert icam_figure_height(capped) < draw.usable_page_height(figure_pdf())

    def test_factor_label_is_the_c12_line_without_its_prefix_or_bracket(self) -> None:
        from src.domain.models.rca_tools import CausalDepth, FishboneCategory
        from src.domain.services.investigation_factors_service import factor_line

        factor = normalise_icam_factors(
            [_factor(cause="No refresher schedule", sub_causes=["Budget withdrawn"], depth="underlying")]
        ).factors[0]
        c12_line = factor_line(
            FishboneCategory.ORGANISATIONAL,
            "No refresher schedule",
            ["Budget withdrawn"],
            CausalDepth.UNDERLYING,
        )

        assert factor.label == "No refresher schedule (Budget withdrawn)"
        assert c12_line == f"{factor.category_label}: {factor.label} [{factor.depth_label.lower()}]"

    def test_set_helpers_report_their_own_shape(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())

        assert bool(factors) is True
        assert bool(IcamFactorSet()) is False
        assert len(factors.for_category(ORGANISATIONAL)) == 2
        assert factors.for_category("machine") == ()
        assert IcamFactor(id=1, category="machine", cause="x").category_label == "Machine"


class TestIcamSummaryLine:
    def test_states_the_count_and_how_many_carry_a_depth(self) -> None:
        line = icam_summary_line(normalise_icam_factors(_fixture_factors()))

        assert line == (
            "5 contributing factors recorded across the four ICAM categories, " "4 with a recorded HSG245 causal depth."
        )

    def test_single_factor_reads_as_one(self) -> None:
        line = icam_summary_line(normalise_icam_factors([_factor(depth=None)]))

        assert line == (
            "1 contributing factor recorded across the four ICAM categories, " "0 with a recorded HSG245 causal depth."
        )

    def test_empty_set_says_so_rather_than_claiming_a_diagram(self) -> None:
        assert icam_summary_line(IcamFactorSet()) == (
            "No ICAM contributing factors are recorded for this investigation."
        )

    def test_a_capped_diagram_reports_what_is_recorded_not_what_it_drew(self) -> None:
        # "10 contributing factors recorded" would be false on an investigation
        # with 40 of them, even with the shortfall stated a line later.
        factors = normalise_icam_factors([_factor(id=index, depth="root") for index in range(40)], cap=10)

        assert factors.recorded == 40
        assert icam_summary_line(factors) == (
            "40 contributing factors recorded across the four ICAM categories; the diagram shows the first 10, "
            "10 of them with a recorded HSG245 causal depth."
        )


class TestIcamFigure:
    def test_four_band_figure_matches_the_golden_fixture(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())

        ops, pdf_bytes, frame = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))

        assert_matches_golden("investigation_icam_four_bands", ops)
        assert pdf_bytes.startswith(b"%PDF-")
        assert frame.h == pytest.approx(icam_figure_height(factors))

    def test_partly_populated_figure_matches_the_golden_fixture(self) -> None:
        raw = {"factors": [_factor(id=1, depth="root"), _factor(id=2, category=INDIVIDUAL_TEAM, cause="Reached in")]}
        factors = normalise_icam_factors(raw)

        ops, pdf_bytes, _ = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))

        assert_matches_golden("investigation_icam_partial_bands", ops)
        assert pdf_bytes.startswith(b"%PDF-")

    def test_draws_all_four_icam_bands_in_c12_order(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())

        ops, _, _ = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))

        baselines = [_baseline_of(ops, ICAM_CATEGORY_LABELS[category]) for category in ICAM_CATEGORIES]
        assert baselines == sorted(baselines)
        assert len(baselines) == 4

    def test_each_factor_is_drawn_inside_its_own_category_band(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())

        ops, _, _ = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))

        organisational = _baseline_of(ops, ICAM_CATEGORY_LABELS[ORGANISATIONAL])
        task = _baseline_of(ops, ICAM_CATEGORY_LABELS[TASK_ENVIRONMENTAL])
        individual = _baseline_of(ops, ICAM_CATEGORY_LABELS[INDIVIDUAL_TEAM])
        assert organisational < _baseline_of(ops, "No refresher training schedule") < task
        assert organisational < _baseline_of(ops, "Guard removal needs no permit") < task
        assert task < _baseline_of(ops, "Mill floor poorly lit") < individual

    def test_sub_causes_and_depth_words_reach_the_page(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())

        ops, _, _ = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))
        texts = _texts(ops)

        assert "No refresher training schedule (Budget withdrawn; No owner named)" in texts
        # Three legend keys plus one chip per classified factor; the unclassified
        # factor contributes no chip.
        assert texts.count("Underlying cause") == 2
        assert texts.count("Root cause") == 2
        assert texts.count("Immediate cause") == 3

    def test_a_factor_with_no_recorded_depth_is_drawn_without_a_depth_claim(self) -> None:
        factors = normalise_icam_factors([_factor(cause="Operator reached in", depth=None)])

        ops, _, _ = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))
        texts = _texts(ops)

        assert "Operator reached in" in texts
        # Only the three legend keys, so no chip was drawn against the row.
        assert [texts.count(ICAM_DEPTH_LABELS[depth]) for depth in ICAM_DEPTHS] == [1, 1, 1]

    def test_an_empty_category_says_so_rather_than_being_dropped(self) -> None:
        factors = normalise_icam_factors([_factor(id=1)])

        ops, _, _ = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))
        texts = _texts(ops)

        assert texts.count("None recorded.") == 3
        assert texts.count("0 factors") == 3
        assert texts.count("1 factor") == 2  # the populated band, plus the figure total

    def test_an_empty_set_reserves_nothing_and_draws_nothing(self) -> None:
        pdf = figure_pdf()
        start = pdf.get_y()

        ops, _, frame = record(lambda recorder: draw_icam_factors_figure(recorder, IcamFactorSet(), brand=BRAND))

        assert ops == []
        assert frame.h == 0.0
        assert icam_figure_height(IcamFactorSet()) == 0.0
        assert draw_icam_factors_figure(pdf, IcamFactorSet(), brand=BRAND).y == pytest.approx(start)
        assert pdf.get_y() == pytest.approx(start)

    def test_figure_stays_inside_its_frame_and_the_printable_page(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())
        pdf = figure_pdf()

        frame = draw_icam_factors_figure(pdf, factors, brand=BRAND)

        assert frame.bottom <= pdf.h - pdf.b_margin
        assert frame.right <= pdf.w - pdf.r_margin

    def test_figure_breaks_the_page_rather_than_drawing_over_the_footer(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())
        pdf = figure_pdf()
        pdf.set_y(pdf.h - pdf.b_margin - 12)

        frame = draw_icam_factors_figure(pdf, factors, brand=BRAND)

        assert pdf.page_no() == 2
        assert frame.bottom <= pdf.h - pdf.b_margin

    def test_a_hand_built_oversized_set_is_clipped_not_painted_over_the_footer(self) -> None:
        # Unreachable through normalise_icam_factors, which caps the rows. A
        # caller that builds a set directly must still not reach the footer.
        oversized = IcamFactorSet(
            factors=tuple(IcamFactor(id=i, category=ORGANISATIONAL, cause=f"Factor {i}") for i in range(400))
        )

        ops, pdf_bytes, frame = record(lambda pdf: draw_icam_factors_figure(pdf, oversized, brand=BRAND))

        assert pdf_bytes.startswith(b"%PDF-")
        for op in ops:
            if op["op"] in {"text", "rect"}:
                assert op["args"][1] <= frame.bottom + 0.05

    def test_colour_and_font_state_is_left_clean_for_the_next_section(self) -> None:
        factors = normalise_icam_factors(_fixture_factors())
        pdf = figure_pdf()
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_line_width(0.6)

        draw_icam_factors_figure(pdf, factors, brand=BRAND)

        assert (pdf.font_style, round(pdf.font_size_pt), pdf.line_width) == ("B", 11, 0.6)

    def test_figure_text_is_latin1_safe(self) -> None:
        factors = normalise_icam_factors(
            [_factor(cause="Ystrad \u2014 Mynach", sub_causes=["20\u00b0C"], depth="root")]
        )

        ops, _, _ = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))

        for text in _texts(ops):
            assert text.encode("latin-1").decode("latin-1") == text

    def test_long_cause_text_is_shortened_rather_than_painted_over_the_depth_chip(self) -> None:
        factors = normalise_icam_factors([_factor(cause="An extremely long contributing factor " * 20, depth="root")])

        ops, _, frame = record(lambda pdf: draw_icam_factors_figure(pdf, factors, brand=BRAND))
        row = next(op for op in ops if op["op"] == "text" and op["args"][2].startswith("An extremely long"))

        assert row["args"][2].endswith("...")
        assert row["args"][0] + 100 < frame.right

    def test_depth_colours_are_a_single_hue_not_a_rag_scale(self) -> None:
        # A root cause sits further back than an immediate one; it is not worse.
        shades = [draw._icam_depth_rgb(BRAND, depth) for depth in ICAM_DEPTHS]

        assert shades[0] > shades[1] > shades[2]
        assert draw._icam_depth_rgb(BRAND, None) == BRAND
        assert draw._icam_depth_rgb(BRAND, "catastrophic") == BRAND

    def test_committed_fixtures_are_json_a_reviewer_can_read(self) -> None:
        from tests.unit._pdf_golden import GOLDEN_DIR

        for name in ("investigation_icam_four_bands", "investigation_icam_partial_bands"):
            payload = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
            assert payload and all({"op", "args", "kwargs"} == set(entry) for entry in payload)
