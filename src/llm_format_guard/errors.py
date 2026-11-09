"""Exceptions raised by llm_format_guard."""

from __future__ import annotations


class FormatGuardError(Exception):
    """Base class for every error raised on purpose by this package."""


class SplitterUnavailable(FormatGuardError):
    """The optional Korean sentence splitter (kss) is not installed."""


class LLMCallError(FormatGuardError):
    """The ``call_llm`` callback misbehaved (for example, it returned a non-string)."""
