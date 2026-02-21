"""Input sanitization utilities for user-generated content."""

import nh3


def sanitize_html(text: str | None) -> str | None:
    """Strip all HTML tags from user input, keeping only plain text."""
    if text is None:
        return None
    return nh3.clean(text, tags=set())


def sanitize_rich_text(text: str | None) -> str | None:
    """Allow safe HTML subset for rich text fields (bold, italic, links, lists)."""
    if text is None:
        return None
    return nh3.clean(
        text,
        tags={"b", "i", "em", "strong", "a", "ul", "ol", "li", "p", "br", "h1", "h2", "h3"},
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https", "mailto"},
    )
