"""Plain data types shared by the public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

#: Every axis a constraint can talk about.
AXES = (
    "lines",
    "sentences",
    "chars",
    "chars_no_space",
    "words",
    "items",
    "paragraphs",
    "table_rows",
    "shape_table",
    "shape_list",
)
#: Comparison operators: <=, <, >=, >, ==, "about" (within a tolerance).
OPS = ("le", "lt", "ge", "gt", "eq", "approx")


@dataclass(frozen=True)
class Constraint:
    """One format or length instruction pulled out of a user message."""

    axis: str
    op: str
    value: int
    unit_text: str = ""
    span: Tuple[int, int] = (0, 0)
    turn: int = 0


@dataclass(frozen=True)
class Metrics:
    """Deterministic measurements of one answer (code blocks and think tags removed)."""

    lines: int
    lines_wo_preamble: int
    sentences: int
    chars: int
    chars_no_space: int
    words: int
    items: int
    paragraphs: int
    has_table: bool
    table_rows: int
    has_list: bool


@dataclass(frozen=True)
class Violation:
    """A constraint that an answer did not satisfy."""

    constraint: Constraint
    actual: int
    kind: str  # "over" | "under" | "shape_mismatch"
    message: str


@dataclass(frozen=True)
class RepairResult:
    """Outcome of the single rewrite attempt."""

    text: str
    adopted: bool
    reason: str  # "improved" | "not_improved" | "empty_repair" | "repair_call_failed" | "no_violations"
    before: Tuple[int, float]
    after: Tuple[int, float]
    extra_calls: int
    error: Optional[str] = None


@dataclass(frozen=True)
class GuardResult:
    """Everything ``guard()`` did for one call."""

    text: str
    original: str
    constraints: Tuple[Constraint, ...]
    violations_before: Tuple[Violation, ...]
    violations_after: Tuple[Violation, ...]
    adopted: bool
    llm_calls: int
    injected: bool
    repair_reason: str = ""
    messages_sent: Tuple[dict, ...] = field(default=(), repr=False)
