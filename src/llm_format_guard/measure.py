"""Deterministic, markdown-aware measurements of one answer (standard library only)."""

from __future__ import annotations

import re
from typing import List, Set

from .splitters import count_sentences
from .types import Metrics

__all__ = ["measure", "strip_noise"]

_FENCE = re.compile(r"^(```|~~~)")
_INNER_TAG = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)
_OPEN_ONLY = re.compile(r"<(?:think|thinking|reasoning)>.*\Z", re.S | re.I)
_CLOSE_ONLY = re.compile(r"\A.*?</(?:think|thinking|reasoning)>", re.S | re.I)
_LIST_ITEM = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+\S")
_LEAD_MARK = re.compile(r"^\s*(?:[-*+•]|\d+[.)]|#{1,6}|>)\s+")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")


def strip_noise(text: str) -> List[str]:
    """Return the lines of ``text`` without ``<think>`` blocks and fenced code."""
    text = _INNER_TAG.sub("", text)
    text = _OPEN_ONLY.sub("", text)
    if "<" in text:  # a model that streams only the closing tag: drop what came before it
        text = _CLOSE_ONLY.sub("", text, count=1)
    out: List[str] = []
    in_code = False
    for line in text.split("\n"):
        if _FENCE.match(line.strip()):
            in_code = not in_code
            continue
        if not in_code:
            out.append(line)
    return out


def _table_lines(lines: List[str]) -> "tuple[Set[int], Set[int], int]":
    """Find markdown tables. Returns (all table line indexes, separator indexes, data rows)."""
    table: Set[int] = set()
    seps: Set[int] = set()
    rows = 0
    for i, line in enumerate(lines):
        if i == 0 or i in table:
            continue
        if "|" in line and _TABLE_SEP.match(line) and "|" in lines[i - 1] and lines[i - 1].strip():
            seps.add(i)
            block = [i - 1, i]
            j = i + 1
            while j < len(lines) and lines[j].strip() and "|" in lines[j]:
                block.append(j)
                rows += 1
                j += 1
            table.update(block)
    return table, seps, rows


def measure(text: str, *, splitter: str = "builtin") -> Metrics:
    """Measure ``text``: lines, sentences, characters, words, list items, paragraphs, table.

    Fenced code blocks and ``<think>`` style tags are ignored. Characters count the
    visible prose (list markers, ``*_` ` and line breaks removed); table rows are
    counted separately. The visible text of table cells (header and data rows, without
    separator lines and pipes) also counts toward characters and words, but not toward
    sentences.
    """
    if not isinstance(text, str):
        raise TypeError(f"measure() expects a str, got {type(text).__name__}")
    lines = strip_noise(text)
    table, seps, table_rows = _table_lines(lines)
    body = [(i, l) for i, l in enumerate(lines) if l.strip() and i not in seps]
    prose = [l.strip() for i, l in body if i not in table]
    plain = "\n".join(re.sub(r"[*_`]", "", _LEAD_MARK.sub("", l)) for l in prose)

    # table cell text: counted in chars / words, not in sentences
    cells = [
        re.sub(r"[*_`]", "", c.strip())
        for i, l in body
        if i in table
        for c in l.strip().strip("|").split("|")
        if c.strip()
    ]
    counted = plain + ("\n" if plain and cells else "") + "\n".join(cells)

    count = len(body)
    preamble = bool(body) and count > 1 and body[0][1].rstrip().endswith((":", "："))
    items = sum(1 for i, l in body if i not in table and _LIST_ITEM.match(l))
    paragraphs = [p for p in re.split(r"\n\s*\n", "\n".join(lines)) if p.strip()]
    return Metrics(
        lines=count,
        lines_wo_preamble=count - 1 if preamble else count,
        sentences=count_sentences(plain, splitter),
        chars=len(counted.replace("\n", "")),
        chars_no_space=len(re.sub(r"\s", "", counted)),
        words=len(counted.split()),
        items=items,
        paragraphs=len(paragraphs),
        has_table=bool(seps),
        table_rows=table_rows,
        has_list=items > 0,
    )
