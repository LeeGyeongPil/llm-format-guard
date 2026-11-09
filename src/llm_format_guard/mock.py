"""A practice (mock) model that misses format instructions the way real models do.

This is NOT a real model and its numbers are NOT measurements of any real model.
It reads the chat and reacts to it by a few fixed rules so that the guard's real
code (extract, re-inject, measure, repair) has something realistic to work on.
No randomness: the same messages always give the same answer.

Rules, from the literature on length-control failures (counts are off because
models write token by token; instructions fade over a long chat):

1. Instruction in the SAME user turn: the shape (table / list) is followed, counts
   overshoot (lines, sentences, items, paragraphs: target + 2; characters and
   words: target x 1.3).
2. Instruction given 1 or more turns EARLIER and no ``[활성 제약]`` block: ignored.
   The answer is the default long text (format drift).
3. ``[활성 제약]`` block present: shape followed, counts overshoot by 1
   (characters and words x 1.15). Lower bounds ("이상") are met.
4. A numeric feedback message (``[형식 점검 결과]`` ...): hits the targets exactly.
   Exception: for "table + row limit" it keeps the row limit but writes a bullet
   list instead of a table, so a careful guard has to reject that rewrite.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from .ledger import Ledger, message_text
from .repair import FEEDBACK_MARKERS
from .types import Constraint

__all__ = ["MockLLM", "MOCK_NOTICE"]

MOCK_NOTICE = ("연습용 목(mock) 모델입니다. 규칙으로 흉내 낸 답이며 실제 모델의 측정값이 아닙니다. "
               "(practice mock model - not a measurement of any real model)")

_BLOCK_MARKERS = ("[활성 제약]", "[Active constraints]")
_HANGUL = re.compile(r"[가-힣]")

_KO_LINES = [
    "핵심 내용을 먼저 짚어 보면 전체 흐름이 한눈에 들어옵니다.",
    "배경을 조금 더 풀어 말하면 이 주제가 나온 이유가 분명해집니다.",
    "중요한 조건은 상황마다 달라서 앞뒤 맥락을 함께 보는 편이 좋습니다.",
    "구체적인 예를 들자면 작은 사례부터 살펴보는 것이 이해에 도움이 됩니다.",
    "여기서 자주 놓치는 부분은 세부 설정이 결과에 영향을 준다는 점입니다.",
    "정리하면 단계별로 확인하면서 진행하는 방식이 가장 안정적입니다.",
    "추가로 참고할 만한 내용도 있지만 우선 위의 흐름을 따르시면 됩니다.",
    "마지막으로 궁금한 점이 남으면 언제든 더 자세히 설명해 드리겠습니다.",
]
_EN_LINES = [
    "To start with the core idea, the whole picture becomes clear at a glance.",
    "A little background explains why this topic came up in the first place.",
    "The important conditions differ by situation, so context matters a lot here.",
    "For a concrete example, it helps to look at one small case first.",
    "A detail that is often missed is that the settings shape the result.",
    "In short, checking step by step is the most reliable way to proceed.",
    "There is more that could be added, but the flow above is enough for now.",
    "If any question remains, I can explain it in more detail at any time.",
]
_KO_WORDS = ["핵심", "내용을", "먼저", "정리하면", "흐름이", "분명해집니다", "배경도", "함께", "살펴보면", "이해가", "쉬워집니다"]
_EN_WORDS = ["the", "core", "idea", "becomes", "clear", "when", "context", "is", "read", "together", "carefully"]
_KO_PREAMBLE = "요약해 드리겠습니다:"
_EN_PREAMBLE = "Here is the summary:"


def _line(i: int, lang: str) -> str:
    pool = _KO_LINES if lang == "ko" else _EN_LINES
    base = pool[i % len(pool)]
    if i >= len(pool):
        base = ("또한 " if lang == "ko" else "Also, ") + base
    return base


def _fill(k: int, lang: str, no_space: bool) -> str:
    """A filler sentence with exactly ``k`` countable characters (spaces count unless no_space)."""
    words = _KO_WORDS if lang == "ko" else _EN_WORDS
    pad = "다" if lang == "ko" else "a"
    out, n, i = [], 0, 0
    target = max(k - 1, 1)  # one character is kept for the final "."
    while n < target:
        w = words[i % len(words)]
        if out:
            if not no_space:
                out.append(" ")
                n += 1
                if n >= target:
                    out[-1] = pad  # never end on a space
                    break
        for ch in w:
            if n >= target:
                break
            out.append(ch)
            n += 1
        i += 1
    return "".join(out) + "."


def _words_sentence(count: int, lang: str) -> str:
    words = _KO_WORDS if lang == "ko" else _EN_WORDS
    toks = [words[i % len(words)] for i in range(max(count, 1))]
    return " ".join(toks) + "."


class MockLLM:
    """Callable ``(messages) -> str`` that behaves like a forgetful chat model.

    ``script`` is an optional list of replies returned first, in order, before the
    rules take over (handy in tests). ``calls`` counts how often it was called.
    """

    NOTICE = MOCK_NOTICE

    def __init__(self, script: Optional[Sequence[str]] = None) -> None:
        self._script: List[str] = list(script or [])
        self.calls = 0

    def __call__(self, messages: Sequence[Dict[str, Any]]) -> str:
        self.calls += 1
        if self._script:
            return self._script.pop(0)
        return self._respond(list(messages))

    # -- rules --------------------------------------------------------------------
    def _respond(self, messages: List[Dict[str, Any]]) -> str:
        users = [m for m in messages if m.get("role") == "user"]
        if not users:
            return _line(0, "ko")
        last_text = message_text(users[-1])
        feedback = any(last_text.startswith(mark) for mark in FEEDBACK_MARKERS.values())
        # On feedback, read the conversation as it was before the rewrite request.
        history = messages[:-2] if feedback else messages
        real_users = [m for m in history if m.get("role") == "user"]
        lang = "ko" if _HANGUL.search(message_text(real_users[-1]) if real_users else last_text) else "en"
        ledger = Ledger.from_messages(history)
        last_turn = len(real_users) - 1
        block = any(mark in message_text(m) for m in history for mark in _BLOCK_MARKERS)

        targets: Dict[str, Optional[int]] = {}
        shapes = set()
        for c in ledger.active:
            level = "exact" if feedback else "block" if block else "same" if c.turn == last_turn else None
            if level is None:
                continue  # format drift: the instruction faded
            if c.axis.startswith("shape_"):
                shapes.add(c.axis)
            else:
                targets[c.axis] = self._target(c, level)
        if not targets and not shapes:
            return self._default(lang)
        return self._build(targets, shapes, lang, feedback)

    @staticmethod
    def _target(c: Constraint, level: str) -> int:
        v = c.value
        if level == "exact":
            return {"le": v, "lt": v - 1, "ge": v, "gt": v + 1}.get(c.op, v)
        if c.op == "ge":
            return v
        if c.op == "gt":
            return v + 1
        if c.axis in ("chars", "chars_no_space", "words"):
            ratio = 1.15 if level == "block" else 1.3
            return max(v + 1, round(v * ratio))
        return v + (1 if level == "block" else 2)

    @staticmethod
    def _default(lang: str) -> str:
        pre = _KO_PREAMBLE if lang == "ko" else _EN_PREAMBLE
        return "\n".join([pre] + [_line(i, lang) for i in range(7)])

    def _build(self, t: Dict[str, Optional[int]], shapes: set, lang: str, feedback: bool) -> str:
        head, cell = ("| 항목 | 설명 |", "설명") if lang == "ko" else ("| Item | Note |", "Note")
        if "shape_table" in shapes or ("table_rows" in t and "shape_list" not in shapes and "items" not in t):
            rows = max(t.get("table_rows") or 5, 1)
            if feedback and "shape_table" in shapes and "table_rows" in t:
                # the rewrite keeps the row limit but drops the table shape
                return "\n".join(f"- {_row_text(i, lang)}" for i in range(rows))
            body = [f"| {i + 1} | {_row_text(i, lang)} |" for i in range(rows)]
            return "\n".join([head, "|---|---|"] + body)
        if "shape_list" in shapes or "items" in t:
            n = max(t.get("items") or 5, 1)
            return "\n".join(f"- {_row_text(i, lang)}" for i in range(n))
        return self._prose(t, lang)

    @staticmethod
    def _prose(t: Dict[str, Optional[int]], lang: str) -> str:
        paragraphs, lines = t.get("paragraphs"), t.get("lines")
        sentences = t.get("sentences")
        n_lines = paragraphs or lines or 1
        n_sent = sentences or n_lines
        if n_sent < n_lines:
            n_lines = n_sent
        per_line = [n_sent // n_lines + (1 if i < n_sent % n_lines else 0) for i in range(n_lines)]
        total = sum(per_line)
        chars, chars_ns, words = t.get("chars"), t.get("chars_no_space"), t.get("words")
        texts: List[str] = []
        if chars or chars_ns:
            seps = sum(p - 1 for p in per_line)
            budget = (chars_ns if chars_ns else chars - seps)
            if budget >= 3 * total:
                ks = [budget // total + (1 if i < budget % total else 0) for i in range(total)]
                texts = [_fill(k, lang, bool(chars_ns)) for k in ks]
        elif words and words >= total:
            ws = [words // total + (1 if i < words % total else 0) for i in range(total)]
            texts = [_words_sentence(w, lang) for w in ws]
        if not texts:
            texts = [_line(i, lang) for i in range(total)]
        out, pos = [], 0
        for p in per_line:
            out.append(" ".join(texts[pos:pos + p]))
            pos += p
        return ("\n\n" if paragraphs else "\n").join(out)


def _row_text(i: int, lang: str) -> str:
    return _line(i, lang).rstrip(".")
