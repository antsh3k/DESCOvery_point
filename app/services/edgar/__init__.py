"""SEC EDGAR ingestion: discover real PE fund entities from Form ADV and Form D
bulk data, then reuse the existing scrape+extract pipeline to infer each one's
investment mandate. See ``ingest.py`` for the orchestrator and ``fetch.py`` for
the bulk-data downloader.
"""
