"""The constraint ledger: remember instructions across turns and say them again."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from .check import describe_target, note_of
from .detect import detect, detect_release
from .types import Constraint

__all__ = ["Ledger", "POSITIONS", "message_text", "resolve_lang"]

POSITIONS = ("before_last_user", "system_end", "in_last_user")
_FENCED = re.compile(r"```.*?(?:```|\Z)", re.S)
_HANGUL = re.compile(r"[가-힣]")
_HEADERS = {"ko": "[활성 제약]", "en": "[Active constraints]"}


def message_text(message: Dict[str, Any]) -> str:
    """Text of one chat message; supports plain strings and OpenAI-style content parts."""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
    return ""


def resolve_lang(lang: str, messages: Sequence[Dict[str, Any]]) -> str:
    """Turn ``"auto"`` into ``"ko"`` or ``"en"`` using the last user message."""
    if lang in ("ko", "en"):
        return lang
    if lang != "auto":
        raise ValueError(f"lang must be 'ko', 'en' or 'auto', got {lang!r}")
    for m in reversed(messages):
        if m.get("role") == "user":
            return "ko" if _HANGUL.search(message_text(m)) else "en"
    return "ko"


def _group(axis: str) -> str:
    """Axes that contradict each other share a group; the newest one wins."""
    if axis.startswith("chars"):
        return "chars"
    if axis.startswith("shape_"):
        return "shape"
    return axis


def _render_line(c: Constraint, lang: str) -> str:
    if c.axis == "shape_table":
        return "답은 마크다운 표로 쓴다." if lang == "ko" else "Format the answer as a markdown table."
    if c.axis == "shape_list":
        return "답은 글머리 목록으로 쓴다." if lang == "ko" else "Format the answer as a bulleted list."
    target = describe_target(c, lang)
    note = note_of(c.axis, lang)
    if lang == "ko":
        if c.op == "eq":
            line = f"답은 {target}이다"
        else:
            josa = "으로" if c.op in ("ge", "lt") else "로"
            line = f"답은 {target}{josa} 쓴다"
        return f"{line} ({note})." if note else f"{line}."
    line = f"Keep the answer to {target}"
    return f"{line} ({note})." if note else f"{line}."


class Ledger:
    """Tracks active constraints across user turns.

    * Only constraints from the last ``window`` user turns are active.
    * A newer constraint on the same axis replaces the older one.
    * Release phrases ("길게 써도 돼", "no limit", "any format") expire matching axes.
    * At most ``max_items`` constraints are kept (oldest dropped first).
      ``Ledger(max_items=0)`` records nothing, which turns the guard's injection off.
    * Very long user messages (a pasted article) are scanned at their head and
      tail only, so numbers inside the pasted text are not mistaken for instructions.
    """

    def __init__(self, max_items: int = 5, window: int = 6, scan_edge: int = 300) -> None:
        if not isinstance(max_items, int) or max_items < 0:
            raise ValueError("max_items must be an integer >= 0 (0 disables the ledger)")
        if not isinstance(window, int) or window < 1:
            raise ValueError("window must be an integer >= 1 (number of user turns to remember)")
        if scan_edge < 50:
            raise ValueError("scan_edge must be >= 50 characters")
        self.max_items = max_items
        self.window = window
        self.scan_edge = scan_edge
        self._items: List[Constraint] = []
        self._last_turn = -1

    # -- building -----------------------------------------------------------------
    def update(self, user_text: str, turn: int) -> List[Constraint]:
        """Read one user message; return the constraints it added."""
        if not isinstance(user_text, str):
            raise TypeError("update() expects the user message text (str)")
        self._last_turn = max(self._last_turn, turn)
        text = _FENCED.sub(" ", user_text)
        if len(text) > 4 * self.scan_edge:
            text = text[: self.scan_edge] + "\n" + text[-self.scan_edge:]
        released = detect_release(text)
        if released:
            self._items = [c for c in self._items if c.axis not in released]
        added: List[Constraint] = []
        if self.max_items:
            for c in detect(text, turn=turn):
                # A newer constraint replaces older ones on the same axis, except the other
                # half of a range given in this very message ("세 줄 이상 다섯 줄 이하").
                self._items = [x for x in self._items
                               if _group(x.axis) != _group(c.axis)
                               or (x in added and {x.op, c.op} == {"ge", "le"})]
                self._items.append(c)
                added.append(c)
            del self._items[: max(0, len(self._items) - self.max_items)]
        return [c for c in added if c in self._items]

    @classmethod
    def from_messages(cls, messages: Sequence[Dict[str, Any]], **kwargs: Any) -> "Ledger":
        """Replay a whole chat history (user messages only) into a new ledger."""
        if not isinstance(messages, (list, tuple)) or not all(isinstance(m, dict) for m in messages):
            raise TypeError("messages must be a list of dicts like {'role': 'user', 'content': '...'}")
        ledger = cls(**kwargs)
        turn = 0
        for m in messages:
            if m.get("role") == "user":
                ledger.update(message_text(m), turn)
                turn += 1
        return ledger

    # -- reading ------------------------------------------------------------------
    @property
    def active(self) -> List[Constraint]:
        """Constraints still inside the turn window, oldest first."""
        return [c for c in self._items if c.turn > self._last_turn - self.window]

    def render(self, lang: str = "ko") -> str:
        """The block that is shown to the model again (positive sentences only)."""
        if lang == "auto":
            lang = "ko"
        if lang not in _HEADERS:
            raise ValueError(f"lang must be 'ko', 'en' or 'auto', got {lang!r}")
        active = self.active
        if not active:
            return ""
        lines = [_HEADERS[lang]] + [f"- {_render_line(c, lang)}" for c in active]
        return "\n".join(lines)

    def inject(self, messages: Sequence[Dict[str, Any]], position: str = "before_last_user",
               lang: str = "ko") -> List[Dict[str, Any]]:
        """Return a NEW message list with the block added. The input is never changed."""
        if position not in POSITIONS:
            raise ValueError(f"position must be one of {POSITIONS}, got {position!r}")
        out = [dict(m) for m in messages]
        block = self.render(resolve_lang(lang, messages))
        if not block:
            return out
        last_user = max((i for i, m in enumerate(out) if m.get("role") == "user"), default=None)
        if position == "system_end":
            first_sys = next((i for i, m in enumerate(out) if m.get("role") == "system"), None)
            if first_sys is None:
                out.insert(0, {"role": "system", "content": block})
            else:
                out[first_sys]["content"] = (message_text(out[first_sys]) + "\n\n" + block).strip()
            return out
        if last_user is None:
            raise ValueError(f"position={position!r} needs at least one user message in `messages`")
        if position == "before_last_user":
            out.insert(last_user, {"role": "system", "content": block})
        else:  # in_last_user
            content = out[last_user].get("content", "")
            if isinstance(content, list):
                out[last_user]["content"] = list(content) + [{"type": "text", "text": block}]
            else:
                out[last_user]["content"] = f"{content}\n\n{block}"
        return out
