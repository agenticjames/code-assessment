"""Provider-abstracted chat client (LangChain ``init_chat_model``).

The engine talks to this wrapper, never to a provider SDK — so swapping providers is a
``--provider/--model`` change. Two methods mirror the two LLM uses in the engine:
``bind_tools`` (the tool loop) and ``structured`` (the final typed verdict). Every run makes
real LLM calls; there is no offline stub.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model


def ensure_google_key() -> bool:
    """``google_genai`` expects ``GOOGLE_API_KEY``; the repo's ``.env`` uses ``GEMINI_API_KEY``.

    Map one to the other if needed. Returns True if a usable key is present.
    """
    if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    return bool(os.environ.get("GOOGLE_API_KEY"))


class LLMClient:
    """Wraps one chat model. Low temperature for stable, repeatable investigations."""

    def __init__(self, provider: str, model: str, temperature: float = 0.0):
        self._model = init_chat_model(f"{provider}:{model}", temperature=temperature)

    def bind_tools(self, tools):
        return self._model.bind_tools(tools)

    def structured(self, schema):
        return self._model.with_structured_output(schema)


def get_client(provider: str, model: str) -> LLMClient:
    """Build the chat client for a real provider (e.g. ``google_genai``)."""
    ensure_google_key()
    return LLMClient(provider, model)
