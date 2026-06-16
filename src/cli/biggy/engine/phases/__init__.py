"""Investigation phases — the abductive loop, one class per stage (hypothesize -> test -> adjudicate).

Each satisfies the ``Phase`` protocol (``name`` + ``run(inv)``) and mutates the shared
``Investigation``. The orchestrator composes them into a pipeline.
"""

from biggy.engine.phases.adjudicate import Adjudicate
from biggy.engine.phases.base import Phase, load_prompt
from biggy.engine.phases.hypothesize import Hypothesize
from biggy.engine.phases.investigate import Investigate

__all__ = ["Adjudicate", "Hypothesize", "Investigate", "Phase", "load_prompt"]
