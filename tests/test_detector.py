"""Tier-2 escalation detector."""

from app.services.scraper.detector import needs_tier2


def test_thin_text_escalates():
    assert needs_tier2(html="<html></html>", text="too short") is True


def test_rich_text_does_not_escalate():
    text = "word " * 300  # ~1500 chars of real content
    assert needs_tier2(html="<html>...</html>", text=text) is False


def test_js_shell_with_little_text_escalates():
    text = "word " * 200  # ~1000 chars, under the JS-shell ceiling
    html = '<div id="root"></div><script id="__NEXT_DATA__"></script>'
    assert needs_tier2(html=html, text=text) is True
