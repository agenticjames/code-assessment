"""The Biggy investigation engine — importable and surface-agnostic.

Nothing here imports a surface (``biggy.cli`` / ``biggy.eval``); dependencies point inward. The CLI
today, and a FastAPI surface later, both drive the engine through this package. ``investigate`` is
exposed lazily so importing lightweight pieces (e.g. ``RunConfig``) doesn't pull in the LLM stack.
"""

from biggy.engine.config import RunConfig

__all__ = ["RunConfig", "investigate"]


def __getattr__(name: str):
    if name == "investigate":
        from biggy.engine.orchestrator import investigate

        return investigate
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
