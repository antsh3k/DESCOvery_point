"""Anthropic (Claude) LLM client."""

from __future__ import annotations

import logging

from app.services.llm.base import LLMClient

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic  # imported lazily so the app boots without the key

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _raw_complete(self, *, system: str, user: str) -> str:
        messages = [{"role": "user", "content": user}]
        # Prefer adaptive thinking; fall back if the model rejects the param.
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system,
                thinking={"type": "adaptive"},
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001 - defensive across model versions
            logger.debug("adaptive thinking rejected (%s); retrying without it", exc)
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system,
                messages=messages,
            )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
