"""Command line: ``llm-format-guard detect | measure | eval``."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import List, Optional, Sequence

from . import __version__
from ._i18n import ENV_VAR, SUPPORTED, display_width, resolve_cli_lang, t
from .detect import detect
from .errors import FormatGuardError
from .evaluate import evaluate, load_conversations
from .measure import measure
from .mock import MOCK_NOTICE


def _table(rows: Sequence[Sequence[str]]) -> str:
    widths = [max(display_width(str(r[i])) for r in rows) for i in range(len(rows[0]))]

    def cell(c: object, w: int) -> str:
        return str(c) + " " * (w - display_width(str(c)))  # pad by terminal width, not len()

    return "\n".join("  ".join(cell(c, w) for c, w in zip(r, widths)).rstrip() for r in rows)


def _cmd_detect(args: argparse.Namespace) -> int:
    lang = args.ui_lang
    found = detect(args.text)
    if args.json:
        print(json.dumps([dataclasses.asdict(c) for c in found], ensure_ascii=False, indent=2))
    elif not found:
        print(t(lang, "no_constraint"))
    else:
        header = tuple(t(lang, k) for k in ("col_axis", "col_op", "col_value", "col_text"))
        print(_table([header] + [(c.axis, c.op, str(c.value), c.unit_text) for c in found]))
    return 0


def _cmd_measure(args: argparse.Namespace) -> int:
    lang = args.ui_lang
    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    m = measure(text, splitter=args.splitter)
    if args.json:
        print(json.dumps(dataclasses.asdict(m), ensure_ascii=False, indent=2))
    else:
        # metric names (lines, chars ...) are JSON keys, so they stay untranslated
        print(_table([(t(lang, "col_metric"), t(lang, "col_value"))]
                     + [(k, str(v)) for k, v in dataclasses.asdict(m).items()]))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    lang = args.ui_lang
    report = evaluate(load_conversations(args.jsonl), mock=args.mock, mode=args.mode)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.mock:
        print(f"{t(lang, 'note_prefix')} {MOCK_NOTICE}")  # MOCK_NOTICE is already bilingual
    print(f"{t(lang, 'label_conversations')}={report['conversations']} "
          f"{t(lang, 'label_with_constraints')}={report['with_constraints']} "
          f"{t(lang, 'label_detection_rate')}={report['detection_rate']} "
          f"{t(lang, 'label_false_detections')}={report['false_detections']} "
          f"{t(lang, 'label_mode')}={report['mode']}")
    stages = list(report["stages"])
    print("\n" + t(lang, "title_compliance"))
    print(_table([(t(lang, "col_stage"), t(lang, "col_rate"))] + [(s, f"{report['stages'][s]:.2f}") for s in stages]))
    print("\n" + t(lang, "title_by_axis"))
    print(_table([(t(lang, "col_axis"), *stages)] + [(a, *(f"{v[s]:.2f}" for s in stages))
                                                     for a, v in report["compliance_by_axis"].items()]))
    print("\n" + t(lang, "title_by_kind"))
    for s in stages:
        print(f"  {s}: {report['violations_by_kind'][s] or '{}'}")
    return 0


def build_parser(lang: Optional[str] = None) -> argparse.ArgumentParser:
    """Build the parser; ``lang`` (en|ko) picks the help language, default from the environment."""
    ui = resolve_cli_lang(lang)
    p = argparse.ArgumentParser(prog="llm-format-guard", description=t(ui, "description"), add_help=False)
    p.add_argument("-h", "--help", action="help", help=t(ui, "help_help"))
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}", help=t(ui, "help_version"))
    p.add_argument("--lang", choices=list(SUPPORTED), default=None, help=t(ui, "help_lang", env=ENV_VAR))
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("detect", help=t(ui, "help_detect"))
    d.add_argument("text", help=t(ui, "help_text"))
    d.add_argument("--json", action="store_true", help=t(ui, "help_json"))
    d.set_defaults(func=_cmd_detect)
    m = sub.add_parser("measure", help=t(ui, "help_measure"))
    m.add_argument("file", help=t(ui, "help_file"))
    m.add_argument("--splitter", choices=["builtin", "kss"], default="builtin", help=t(ui, "help_splitter"))
    m.add_argument("--json", action="store_true", help=t(ui, "help_json"))
    m.set_defaults(func=_cmd_measure)
    e = sub.add_parser("eval", help=t(ui, "help_eval"))
    e.add_argument("jsonl", help=t(ui, "help_jsonl"))
    e.add_argument("--mock", action="store_true", help=t(ui, "help_mock"))
    e.add_argument("--mode", choices=["loose", "strict"], default="loose", help=t(ui, "help_mode"))
    e.add_argument("--json", action="store_true", help=t(ui, "help_json"))
    e.set_defaults(func=_cmd_eval)
    return p


def _early_lang(argv: Sequence[str]) -> Optional[str]:
    """Read ``--lang`` first so that --help already comes out in the chosen language."""
    pre = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    def _silent(message: str) -> None:
        raise SystemExit(2)  # the real parser prints the one error

    pre.error = _silent  # type: ignore[method-assign]
    pre.add_argument("--lang", default=None)  # no choices: the real parser reports a bad value once
    try:
        value = pre.parse_known_args(list(argv))[0].lang
    except SystemExit:
        return None  # e.g. "--lang" with no value; the real parser reports it
    return value if value in SUPPORTED else None


def _error_text(exc: Exception, lang: str) -> str:
    """Localized sentence for errors that carry a code, else the library's own text."""
    code = getattr(exc, "code", None)
    if code:
        try:
            return t(lang, f"err_{code}", **getattr(exc, "params", {}))
        except KeyError:
            pass
    return str(exc)


def main(argv: Optional[List[str]] = None) -> int:
    args_in = sys.argv[1:] if argv is None else list(argv)
    lang = resolve_cli_lang(_early_lang(args_in))
    args = build_parser(lang).parse_args(args_in)
    args.ui_lang = lang
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        text = t(lang, "err_file_not_found", filename=exc.filename) if exc.filename else str(exc)
        print(f"{t(lang, 'error_prefix')} {text}", file=sys.stderr)
        return 2
    except (FormatGuardError, OSError, ValueError) as exc:
        print(f"{t(lang, 'error_prefix')} {_error_text(exc, lang)}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
