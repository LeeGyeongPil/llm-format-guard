"""``guard()``: extract, re-inject, measure, repair once."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from .check import check
from .errors import LLMCallError
from .ledger import Ledger, resolve_lang
from .repair import repair as _repair
from .types import GuardResult

__all__ = ["guard"]


def _call(call_llm: Callable[[List[Dict[str, Any]]], str], messages: List[Dict[str, Any]]) -> str:
    text = call_llm(messages)
    if not isinstance(text, str):
        raise LLMCallError(
            f"call_llm must return the answer as a str, got {type(text).__name__}. "
            "Return response text (for example completion.choices[0].message.content).")
    return text


def guard(
    messages: Sequence[Dict[str, Any]],
    call_llm: Callable[[List[Dict[str, Any]]], str],
    *,
    ledger: Optional[Ledger] = None,
    repair: bool = True,
    mode: str = "loose",
    position: str = "before_last_user",
    lang: str = "auto",
) -> GuardResult:
    """Run one LLM call with format-instruction support.

    Steps: build the ledger from the chat (or use ``ledger`` as given), add the
    ``[활성 제약]`` block, call the model, measure the answer, and if rules are
    broken ask for one rewrite that is adopted only when it is better.

    With no active constraint this makes exactly one call and sends the messages
    unchanged. Exceptions raised by ``call_llm`` on the first call propagate as-is.
    """
    if not callable(call_llm):
        raise TypeError("call_llm must be a function taking a message list and returning str")
    if (isinstance(messages, (str, bytes)) or not hasattr(messages, "__iter__")
            or not all(isinstance(m, dict) for m in messages)):
        raise TypeError('messages must be a list of {"role", "content"} dicts, '
                        'e.g. [{"role": "user", "content": "세 줄로 요약해 줘"}]')
    msgs = [dict(m) for m in messages]
    led = ledger if ledger is not None else Ledger.from_messages(msgs)
    active = tuple(led.active)
    resolved = resolve_lang(lang, msgs)
    if not active:
        text = _call(call_llm, msgs)
        return GuardResult(text, text, (), (), (), False, 1, False, "", tuple(msgs))
    sent = led.inject(msgs, position=position, lang=resolved)
    original = _call(call_llm, sent)
    before = tuple(check(original, active, mode=mode, lang=resolved))
    if not before or not repair:
        return GuardResult(original, original, active, before, before, False, 1, True, "", tuple(sent))
    result = _repair(sent, original, before, call_llm, constraints=active, mode=mode, lang=resolved)
    after = tuple(check(result.text, active, mode=mode, lang=resolved))
    return GuardResult(result.text, original, active, before, after, result.adopted,
                       1 + result.extra_calls, True, result.reason, tuple(sent))
