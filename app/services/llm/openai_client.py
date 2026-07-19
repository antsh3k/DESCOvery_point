"""OpenAI (GPT) LLM client."""

from __future__ import annotations

from app.services.llm.base import LLMClient

_MAX_TOKENS = 4096


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        import openai  # imported lazily so the app boots without the key

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def _raw_complete(self, *, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""
