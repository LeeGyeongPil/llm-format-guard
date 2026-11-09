"""Command line: ``llm-format-guard detect | measure | eval``."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import List, Optional, Sequence

from . import __version__
from .detect import detect
from .errors import FormatGuardError
from .evaluate import evaluate, load_conversations
from .measure import measure
from .mock import MOCK_NOTICE


def _table(rows: Sequence[Sequence[str]]) -> str:
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows)


def _cmd_detect(args: argparse.Namespace) -> int:
    found = detect(args.text)
    if args.json:
        print(json.dumps([dataclasses.asdict(c) for c in found], ensure_ascii=False, indent=2))
    elif not found:
        print("(no format or length constraint found)")
    else:
        print(_table([("axis", "op", "value", "text")] + [(c.axis, c.op, str(c.value), c.unit_text) for c in found]))
    return 0


def _cmd_measure(args: argparse.Namespace) -> int:
    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    m = measure(text, splitter=args.splitter)
    if args.json:
        print(json.dumps(dataclasses.asdict(m), ensure_ascii=False, indent=2))
    else:
        print(_table([("metric", "value")] + [(k, str(v)) for k, v in dataclasses.asdict(m).items()]))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    report = evaluate(load_conversations(args.jsonl), mock=args.mock, mode=args.mode)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.mock:
        print(f"NOTE: {MOCK_NOTICE}")
    print(f"conversations={report['conversations']} with_constraints={report['with_constraints']} "
          f"detection_rate={report['detection_rate']} false_detections={report['false_detections']} "
          f"mode={report['mode']}")
    stages = list(report["stages"])
    print("\ncompliance (share of conversations with no violation)")
    print(_table([("stage", "rate")] + [(s, f"{report['stages'][s]:.2f}") for s in stages]))
    print("\ncompliance by axis")
    print(_table([("axis", *stages)] + [(a, *(f"{v[s]:.2f}" for s in stages))
                                         for a, v in report["compliance_by_axis"].items()]))
    print("\nviolations by kind")
    for s in stages:
        print(f"  {s}: {report['violations_by_kind'][s] or '{}'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llm-format-guard",
                                description="Detect, measure and evaluate format/length instructions for LLM answers.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("detect", help="show the constraints found in one message")
    d.add_argument("text")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_detect)
    m = sub.add_parser("measure", help="count lines, sentences, characters ... of an answer file ('-' = stdin)")
    m.add_argument("file")
    m.add_argument("--splitter", choices=["builtin", "kss"], default="builtin")
    m.add_argument("--json", action="store_true")
    m.set_defaults(func=_cmd_measure)
    e = sub.add_parser("eval", help="score a conversations JSONL file")
    e.add_argument("jsonl")
    e.add_argument("--mock", action="store_true", help="run the practice mock model in three stages")
    e.add_argument("--mode", choices=["loose", "strict"], default="loose")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=_cmd_eval)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FormatGuardError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
