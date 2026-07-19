"""Scraper data types shared across tiers."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.enums import FetchMethod


@dataclass(slots=True)
class ScrapedPage:
    url: str
    title: str | None
    text: str
    method: FetchMethod


@dataclass(slots=True)
class ScrapeResult:
    pages: list[ScrapedPage] = field(default_factory=list)

    @property
    def text(self) -> str:
        """All page text concatenated, page-delimited for the extractor."""
        return "\n\n".join(
            f"[source: {p.url}]\n{p.text}" for p in self.pages if p.text
        )

    @property
    def source_urls(self) -> list[str]:
        return [p.url for p in self.pages]
