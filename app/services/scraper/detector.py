"""Heuristics deciding whether Tier-1 output is too thin and needs Tier-2."""

from __future__ import annotations

# Below this many characters of visible text, a page is effectively empty.
MIN_TEXT_CHARS = 600

# Markers that a page is a client-rendered JS shell with little server HTML.
_JS_SHELL_MARKERS = ("__NEXT_DATA__", "ng-app", "data-reactroot", "id=\"root\"", "id=\"app\"")


def needs_tier2(*, html: str, text: str) -> bool:
    """Return True when Tier-1 content looks insufficient for extraction."""
    if len(text.strip()) < MIN_TEXT_CHARS:
        return True
    # A JS shell that rendered almost no real text is a strong escalation signal.
    if len(text.strip()) < 1500 and any(m in html for m in _JS_SHELL_MARKERS):
        return True
    return False
