"""Exceptions raised by llm_format_guard."""

from __future__ import annotations

from typing import Any, Dict, Optional


class FormatGuardError(Exception):
    """Base class for every error raised on purpose by this package.

    ``str(exc)`` is always the English sentence. Some errors also carry a machine
    readable ``code`` and ``params`` so the command line can show the same error in
    another language; library callers can ignore both.
    """

    def __init__(self, *args: Any, code: Optional[str] = None, **params: Any) -> None:
        super().__init__(*args)
        self.code: Optional[str] = code
        self.params: Dict[str, Any] = params


class SplitterUnavailable(FormatGuardError):
    """The optional Korean sentence splitter (kss) is not installed."""


class LLMCallError(FormatGuardError):
    """The ``call_llm`` callback misbehaved (for example, it returned a non-string)."""
