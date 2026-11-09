"""Evaluate a JSONL file of conversations: how often are format instructions kept?

Each line is ``{"id": ..., "messages": [...], "answer": "...", "expect": ["lines"]}``.
``answer`` is the model's recorded reply (needed unless ``mock=True``); ``expect``
optionally lists the axes a human sees in the user's instructions (used for the
detection rate).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from .check import check
from .errors import FormatGuardError
from .guard import guard
from .ledger import Ledger
from .mock import MOCK_NOTICE, MockLLM
from .types import Constraint

__all__ = ["load_conversations", "evaluate"]


def load_conversations(path: str) -> List[Dict[str, Any]]:
    """Read and validate a conversations JSONL file."""
    rows: List[Dict[str, Any]] = []
    with open(Path(path), encoding="utf-8") as fh:
        for no, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FormatGuardError(f"{path}:{no}: invalid JSON ({exc.msg}). One JSON object per line.") from exc
            msgs = row.get("messages") if isinstance(row, dict) else None
            if not (isinstance(msgs, list) and msgs and all(isinstance(m, dict) and "role" in m for m in msgs)):
                raise FormatGuardError(
                    f'{path}:{no}: needs "messages": a non-empty list of {{"role": ..., "content": ...}}')
            rows.append(row)
    if not rows:
        raise FormatGuardError(f"{path}: no conversations found")
    return rows


def _axis_key(axis: str) -> str:
    return "chars" if axis.startswith("chars") else "shape" if axis.startswith("shape_") else axis


def _rate(ok: int, total: int) -> float:
    return round(ok / total, 4) if total else 0.0


def evaluate(conversations: Sequence[Dict[str, Any]], *, mock: bool = False, mode: str = "loose") -> Dict[str, Any]:
    """Score every conversation; returns a JSON-friendly dict."""
    stage_names = ("raw", "injected", "repaired") if mock else ("recorded",)
    stage_ok: Counter = Counter()
    axis_ok: Dict[Tuple[str, str], int] = Counter()
    axis_total: Counter = Counter()
    kinds: Dict[str, Counter] = {s: Counter() for s in stage_names}
    with_constraints = 0
    expected_total = expected_hit = false_detect = 0
    labelled_any = any("expect" in c for c in conversations)

    for i, conv in enumerate(conversations):
        msgs = conv["messages"]
        ledger = Ledger.from_messages(msgs)
        active: List[Constraint] = ledger.active
        detected = {_axis_key(c.axis) for c in active}
        if "expect" in conv:
            expected = {_axis_key(a) for a in conv["expect"]}
            expected_total += len(expected)
            expected_hit += len(expected & detected)
            false_detect += len(detected - expected)
        if not active:
            continue
        with_constraints += 1
        answers: Dict[str, str] = {}
        if mock:
            answers["raw"] = MockLLM()(msgs)
            answers["injected"] = MockLLM()(ledger.inject(msgs, lang="auto"))
            answers["repaired"] = guard(msgs, MockLLM(), mode=mode).text
        else:
            if not isinstance(conv.get("answer"), str):
                raise FormatGuardError(
                    f'conversation {conv.get("id", i + 1)!r} has no "answer"; add the recorded reply or use --mock')
            answers["recorded"] = conv["answer"]
        for stage, text in answers.items():
            violations = check(text, active, mode=mode)
            bad = {id(v.constraint) for v in violations}
            stage_ok[stage] += 0 if violations else 1
            for c in active:
                axis_total[(c.axis, stage)] += 1
                axis_ok[(c.axis, stage)] += 0 if id(c) in bad else 1
            for v in violations:
                kinds[stage][v.kind] += 1

    detection = (_rate(expected_hit, expected_total) if labelled_any and expected_total
                 else _rate(with_constraints, len(conversations)))
    axes = sorted({a for a, _ in axis_total})
    report: Dict[str, Any] = {
        "mock": mock,
        "mode": mode,
        "conversations": len(conversations),
        "with_constraints": with_constraints,
        "detection_rate": detection,
        "false_detections": false_detect,
        "stages": {s: _rate(stage_ok[s], with_constraints) for s in stage_names},
        "compliance_by_axis": {a: {s: _rate(axis_ok[(a, s)], axis_total[(a, s)]) for s in stage_names} for a in axes},
        "violations_by_kind": {s: dict(sorted(kinds[s].items())) for s in stage_names},
    }
    if mock:
        report["notice"] = MOCK_NOTICE
    return report
