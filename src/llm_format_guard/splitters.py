"""Sentence counting: a built-in rule-based splitter and an optional kss backend."""

from __future__ import annotations

import re
from typing import List

from .errors import SplitterUnavailable

_MASK = "\x00"
# Dots that do not end a sentence: URLs, decimals, common abbreviations.
_PROTECT = re.compile(
    r"https?://\S+|www\.\S+|\d+(?:[.,]\d+)+|\b(?:e\.g|i\.e|etc|vs|Mr|Mrs|Ms|Dr|Prof|No|Fig|U\.S|a\.m|p\.m)\.",
    re.I)
# ASCII/full-width terminators followed by space or the end; CJK full-width marks split anywhere.
_SPLIT = re.compile(r"(?:[.?!…]+(?=[\s\"'”’)\]」』]|$)|[。？！]+)")


def _mask_dots(match: "re.Match[str]") -> str:
    return match.group(0).replace(".", _MASK)


def split_builtin(text: str) -> List[str]:
    """Split ``text`` into sentences. Every line is at least one sentence.

    A line that ends in a Korean ending with no punctuation ("...합니다") therefore
    still counts, which is how chat answers are usually written.
    """
    sentences: List[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        masked = _PROTECT.sub(_mask_dots, line)
        for part in _SPLIT.split(masked):
            part = part.replace(_MASK, ".").strip()
            if re.search(r"\w", part):
                sentences.append(part)
    return sentences


def split_kss(text: str) -> List[str]:
    """Split with kss (pecab backend). Needs ``pip install "llm-format-guard[kss]"``."""
    try:
        import kss  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SplitterUnavailable(
            'splitter="kss" needs the optional kss package. '
            'Install it with: pip install "llm-format-guard[kss] @ '
            'git+https://github.com/LeeGyeongPil/llm-format-guard" '
            "(or, in a clone: uv sync --extra kss). "
            'Once the package is published to PyPI: pip install "llm-format-guard[kss]"'
        ) from exc
    result = kss.split_sentences(text, backend="pecab")
    return [s for s in result if s.strip()]


def count_sentences(text: str, splitter: str = "builtin") -> int:
    """Count sentences with the chosen splitter ("builtin" or "kss")."""
    if splitter == "builtin":
        return len(split_builtin(text))
    if splitter == "kss":
        return len(split_kss(text))
    raise ValueError(f'unknown splitter {splitter!r}; use "builtin" or "kss"')
