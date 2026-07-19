"""Four-stage matching engine: filters → numeric → thesis judge → re-rank."""

from app.services.matching.engine import MatchResult, run_match
from app.services.matching.score import DEFAULT_WEIGHTS, compose

__all__ = ["DEFAULT_WEIGHTS", "MatchResult", "compose", "run_match"]
