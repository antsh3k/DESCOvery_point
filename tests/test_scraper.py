"""Tier-1 HTTP scraper: parsing and internal-link selection (network mocked)."""

import httpx
import respx

from app.enums import FetchMethod
from app.services.scraper.tier1_http import fetch_site

_HOME = """
<html><head><title>Acme</title></head><body>
  <h1>Acme Software</h1><p>We build B2B SaaS for logistics.</p>
  <script>var x = 1;</script>
  <a href="/about">About us</a>
  <a href="/contact">Contact</a>
  <a href="https://twitter.com/acme">Twitter</a>
</body></html>
"""

_ABOUT = """
<html><head><title>About Acme</title></head><body>
  <p>Founded 2010 in the UK. 80 employees.</p>
</body></html>
"""


@respx.mock
async def test_fetch_site_parses_and_follows_internal_links():
    respx.get("https://acme.com/").mock(
        return_value=httpx.Response(200, html=_HOME)
    )
    respx.get("https://acme.com/about").mock(
        return_value=httpx.Response(200, html=_ABOUT)
    )
    respx.get("https://acme.com/contact").mock(
        return_value=httpx.Response(200, html="<html><body>Reach us</body></html>")
    )

    pages = await fetch_site("https://acme.com/", max_pages=3)

    urls = {p.url for p in pages}
    assert "https://acme.com/" in urls
    assert "https://acme.com/about" in urls  # prioritised keyword page

    home = next(p for p in pages if p.url == "https://acme.com/")
    assert home.title == "Acme"
    assert home.method is FetchMethod.http
    assert "B2B SaaS" in home.text
    assert "var x" not in home.text  # <script> stripped

    # External links are never followed.
    assert not any("twitter.com" in u for u in urls)
