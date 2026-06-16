"""Grading against the per-scenario HIDDEN_TRUTH answer key.

Inc 0 ships a single-run grader used by ``investigate --check`` (a verification aid). The full
multi-scenario eval harness + scorecard is Inc 4.
"""

from biggy.eval.grade import Scorecard, grade, scorecard_panel

__all__ = ["Scorecard", "grade", "scorecard_panel"]
