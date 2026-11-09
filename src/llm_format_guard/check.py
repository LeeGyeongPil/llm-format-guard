"""Judge an answer against constraints (loose or strict) and describe violations."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Union

from .measure import measure
from .types import Constraint, Metrics, Violation

__all__ = ["check", "describe_target", "violation_distance", "MODES"]

MODES = ("loose", "strict")

_UNIT = {
    "ko": {"lines": "줄", "sentences": "문장", "chars": "자", "chars_no_space": "자", "words": "단어",
           "items": "개 항목", "paragraphs": "문단", "table_rows": "행"},
    "en": {"lines": "lines", "sentences": "sentences", "chars": "characters",
           "chars_no_space": "characters", "words": "words", "items": "items",
           "paragraphs": "paragraphs", "table_rows": "table rows"},
}
_NOTE = {
    "ko": {"chars": "공백 포함", "chars_no_space": "공백 제외", "table_rows": "표의 데이터 행"},
    "en": {"chars": "spaces included", "chars_no_space": "spaces excluded", "table_rows": "table data rows"},
}
_OP = {
    "ko": {"le": "이하", "lt": "미만", "ge": "이상", "gt": "초과", "eq": "", "approx": "내외"},
    "en": {"le": "at most", "lt": "fewer than", "ge": "at least", "gt": "more than", "eq": "exactly",
           "approx": "about"},
}
_ATTR = {"lines": "lines", "sentences": "sentences", "chars": "chars", "chars_no_space": "chars_no_space",
         "words": "words", "items": "items", "paragraphs": "paragraphs", "table_rows": "table_rows"}


def unit_of(axis: str, lang: str) -> str:
    return _UNIT[lang].get(axis, "")


def note_of(axis: str, lang: str) -> str:
    return _NOTE[lang].get(axis, "")


def describe_target(c: Constraint, lang: str = "ko") -> str:
    """Human wording of a numeric target, e.g. "3줄 이하" or "at most 3 lines"."""
    unit = unit_of(c.axis, lang)
    if lang == "ko":
        if c.op == "eq":
            return f"정확히 {c.value}{unit}"
        return f"{c.value}{unit} {_OP['ko'][c.op]}"
    return f"{_OP['en'][c.op]} {c.value} {unit}"


def _ok(op: str, actual: float, value: int, tolerance: float) -> bool:
    if op == "le":
        return actual <= value
    if op == "lt":
        return actual < value
    if op == "ge":
        return actual >= value
    if op == "gt":
        return actual > value
    if op == "eq":
        return actual == value
    return abs(actual - value) <= tolerance * value + 1e-9  # approx


def _candidates(c: Constraint, m: Metrics, mode: str) -> List[int]:
    if c.axis == "lines" and mode == "loose":
        return [m.lines, m.lines_wo_preamble]  # a one-line lead-in ("다음은 요약입니다:") is forgiven
    return [getattr(m, _ATTR[c.axis])]


def _message(c: Constraint, actual: int, lang: str) -> str:
    unit = unit_of(c.axis, lang)
    note = note_of(c.axis, lang)
    if lang == "ko":
        text = f"현재 {actual}{unit}, 목표 {describe_target(c, 'ko')}"
        return f"{text} ({note})" if note else text
    text = f"currently {actual} {unit}, target {describe_target(c, 'en')}"
    return f"{text} ({note})" if note else text


def check(
    text_or_metrics: Union[str, Metrics],
    constraints: Iterable[Constraint],
    *,
    mode: str = "loose",
    approx_tolerance: float = 0.1,
    lang: str = "ko",
) -> List[Violation]:
    """Return the constraints the answer breaks (empty list = all satisfied).

    ``mode="loose"`` (default) gives the answer the benefit of the doubt: an upper
    bound uses the smaller of the plausible counts, a lower bound the larger one.
    ``mode="strict"`` uses the raw count. ``approx`` constraints ("200자 내외")
    allow ``approx_tolerance`` (10% by default).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if lang not in _UNIT:
        raise ValueError(f"lang must be 'ko' or 'en', got {lang!r}")
    if not 0 <= approx_tolerance < 1:
        raise ValueError("approx_tolerance must be between 0 and 1 (for example 0.1 for 10%)")
    m = text_or_metrics if isinstance(text_or_metrics, Metrics) else measure(text_or_metrics)
    out: List[Violation] = []
    for c in constraints:
        if c.axis == "shape_table":
            if not m.has_table:
                msg = "표 형식이 아님, 목표: 마크다운 표" if lang == "ko" else "no table found, target: a markdown table"
                out.append(Violation(c, 0, "shape_mismatch", msg))
            continue
        if c.axis == "shape_list":
            if not m.has_list:
                msg = "목록 형식이 아님, 목표: 글머리 목록" if lang == "ko" else "no list found, target: a bulleted list"
                out.append(Violation(c, 0, "shape_mismatch", msg))
            continue
        values = _candidates(c, m, mode)
        if c.op in ("le", "lt"):
            actual = min(values)
        elif c.op in ("ge", "gt"):
            actual = max(values)
        else:
            actual = values[0]
        passed = (any(_ok(c.op, v, c.value, approx_tolerance) for v in values)
                  if c.op in ("eq", "approx") else _ok(c.op, actual, c.value, approx_tolerance))
        if passed:
            continue
        over = actual > c.value if c.op in ("eq", "approx") else c.op in ("le", "lt")
        out.append(Violation(c, actual, "over" if over else "under", _message(c, actual, lang)))
    return out


def violation_distance(v: Violation) -> float:
    """How far an answer is from the target, scaled by the target (shape mismatch = 1.0)."""
    c = v.constraint
    if v.kind == "shape_mismatch":
        return 1.0
    target = {"le": c.value, "lt": c.value - 1, "ge": c.value, "gt": c.value + 1}.get(c.op, c.value)
    return abs(v.actual - target) / max(c.value, 1)
