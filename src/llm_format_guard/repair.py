"""One rewrite attempt, adopted only when it is strictly better."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence, Tuple

from .check import check, violation_distance
from .types import Constraint, RepairResult, Violation

__all__ = ["repair", "build_feedback", "FEEDBACK_MARKERS", "score"]

FEEDBACK_MARKERS = {"ko": "[형식 점검 결과]", "en": "[Format check]"}
LLMCallable = Callable[[List[Dict[str, Any]]], str]


def score(violations: Sequence[Violation]) -> Tuple[int, float]:
    """(number of violations, summed normalised distance). Smaller is better."""
    return (len(violations), round(sum(violation_distance(v) for v in violations), 6))


def build_feedback(violations: Sequence[Violation], lang: str = "ko") -> str:
    """The numeric feedback sentence sent with the rewrite request."""
    lines = "\n".join(f"- {v.message}" for v in violations)
    if lang == "ko":
        return (f"{FEEDBACK_MARKERS['ko']} 방금 답이 형식 지시와 달랐습니다.\n{lines}\n"
                "같은 내용을 위 목표에 맞춰 다시 써 주세요. 답변 본문만 출력합니다.")
    return (f"{FEEDBACK_MARKERS['en']} The last answer missed the format instructions.\n{lines}\n"
            "Rewrite the same content to meet the targets above. Output the answer text only.")


def repair(
    messages: Sequence[Dict[str, Any]],
    answer: str,
    violations: Sequence[Violation],
    call_llm: LLMCallable,
    *,
    constraints: Sequence[Constraint],
    mode: str = "loose",
    lang: str = "ko",
) -> RepairResult:
    """Ask for ONE rewrite and keep it only if it breaks strictly fewer rules.

    "Strictly better" means the pair (number of violations, summed distance) gets
    smaller. A rewrite that fixes the length but drops the table is therefore
    rejected. If ``call_llm`` raises, the original answer is kept with
    ``reason="repair_call_failed"``.
    """
    before = score(violations)
    if not violations:
        return RepairResult(answer, False, "no_violations", before, before, 0)
    request = list(messages) + [
        {"role": "assistant", "content": answer},
        {"role": "user", "content": build_feedback(violations, lang)},
    ]
    try:
        new_text = call_llm(request)
    except Exception as exc:  # the callback is user code: any failure keeps the original answer
        return RepairResult(answer, False, "repair_call_failed", before, before, 1,
                            error=f"{type(exc).__name__}: {exc}")
    if not isinstance(new_text, str) or not new_text.strip():
        return RepairResult(answer, False, "empty_repair", before, before, 1)
    after = score(check(new_text, constraints, mode=mode, lang=lang))
    if after < before:
        return RepairResult(new_text, True, "improved", before, after, 1)
    return RepairResult(answer, False, "not_improved", before, after, 1)
