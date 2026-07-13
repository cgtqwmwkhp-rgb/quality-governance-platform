"""Unit tests for AI-first regulatory watch helpers."""

from src.domain.services.regulatory_watch_service import RegulatoryWatchService, WATCH_KEYWORDS


def test_watch_keywords_cover_hseq_domains():
    joined = " ".join(WATCH_KEYWORDS)
    assert "coshh" in joined
    assert "rams" in joined
    assert "iso 45001" in joined


def test_looks_relevant_filters_noise():
    svc = RegulatoryWatchService()
    assert svc._looks_relevant("HSE updates GB MCL list for hazardous chemicals") is True
    assert svc._looks_relevant("Office cafeteria menu changes next week") is False


def test_extract_tags_from_update_text():
    svc = RegulatoryWatchService()
    tags = svc._extract_tags("New COSHH and SDS guidance from HSE on CLP labelling")
    assert "coshh" in tags
    assert "sds" in tags or "clp" in tags


def test_parse_rss_extracts_relevant_items():
    svc = RegulatoryWatchService()
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>HSE COSHH assessment update</title>
        <description>Updated guidance for chemical safety</description>
        <link>https://www.hse.gov.uk/coshh/</link>
        <guid>coshh-1</guid>
      </item>
      <item>
        <title>Cafeteria specials</title>
        <description>Lunch options</description>
        <link>https://example.com</link>
        <guid>food-1</guid>
      </item>
    </channel></rss>"""
    feed = {
        "id": "test",
        "source": "hse_uk",
        "category": "health_safety",
        "url": "https://example.com/rss",
        "title_prefix": "HSE",
    }
    items = svc._parse_atom_or_rss(xml, feed)
    assert len(items) == 1
    assert "COSHH" in items[0].title
