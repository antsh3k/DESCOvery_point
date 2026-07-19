"""Shared HTML → (title, clean text) parsing, used by every scraper tier."""

from __future__ import annotations

from bs4 import BeautifulSoup

_STRIP_TAGS = ("script", "style", "noscript", "template", "svg")


def clean_html(html: str) -> tuple[str | None, str]:
    """Return the page title and collapsed visible text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    text = " ".join(soup.get_text(" ").split())
    return title, text
