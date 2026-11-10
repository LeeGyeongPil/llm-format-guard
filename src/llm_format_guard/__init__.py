"""llm-format-guard: catch LLM answers that miss the user's format and length instructions.

Typical use::

    from llm_format_guard import guard
    result = guard(messages, call_llm)   # call_llm(list[dict]) -> str
    print(result.text)
"""

from __future__ import annotations

from .check import check
from .detect import detect
from .errors import FormatGuardError, LLMCallError, SplitterUnavailable
from .guard import guard
from .ledger import Ledger
from .measure import measure
from .mock import MockLLM
from .repair import repair
from .types import Constraint, GuardResult, Metrics, RepairResult, Violation

__version__ = "0.1.1"

__all__ = [
    "Constraint",
    "FormatGuardError",
    "GuardResult",
    "LLMCallError",
    "Ledger",
    "Metrics",
    "MockLLM",
    "RepairResult",
    "SplitterUnavailable",
    "Violation",
    "__version__",
    "check",
    "detect",
    "guard",
    "measure",
    "repair",
]
