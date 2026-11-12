"""CLI output language: en/ko tables, priority, JSON invariance, exit codes."""

import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _lang  # noqa: F401
from llm_format_guard._i18n import MESSAGES, resolve_cli_lang
from llm_format_guard.cli import main

ROOT = Path(__file__).resolve().parents[1]
CONVERSATIONS = ROOT / "examples" / "data" / "conversations.jsonl"
ANSWER = ROOT / "examples" / "data" / "answer.md"
HANGUL = re.compile("[가-힣]")
LANG_VARS = ("LLM_FORMAT_GUARD_LANG", "LC_ALL", "LC_MESSAGES", "LANG")
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def run(*argv, env=None):
    """Run main() with only the given language variables set."""
    clean = {k: v for k, v in os.environ.items() if k not in LANG_VARS}
    clean.update(env or {})
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, clean, clear=True), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TestTable(unittest.TestCase):
    def test_keys_match(self):
        self.assertEqual(set(MESSAGES["en"]), set(MESSAGES["ko"]))

    def test_placeholders_match(self):
        for key, en in MESSAGES["en"].items():
            self.assertEqual(set(PLACEHOLDER.findall(en)), set(PLACEHOLDER.findall(MESSAGES["ko"][key])), key)

    def test_no_particle_placeholders(self):
        for text in MESSAGES["ko"].values():
            self.assertNotIn("(가)", text)
            self.assertNotIn("(를)", text)


class TestPriority(unittest.TestCase):
    def test_default_is_english(self):
        self.assertEqual(resolve_cli_lang(None, {}), "en")
        self.assertEqual(resolve_cli_lang(None, {"LANG": "C"}), "en")
        self.assertEqual(resolve_cli_lang(None, {"LANG": "fr_FR.UTF-8"}), "en")
        self.assertEqual(resolve_cli_lang(None, {"LANG": ""}), "en")

    def test_korean_values(self):
        for v in ("ko", "ko_KR.UTF-8", "KO_kr"):
            self.assertEqual(resolve_cli_lang(None, {"LANG": v}), "ko")

    def test_order(self):
        env = {"LLM_FORMAT_GUARD_LANG": "en", "LC_ALL": "ko", "LC_MESSAGES": "ko", "LANG": "ko"}
        self.assertEqual(resolve_cli_lang(None, env), "en")
        self.assertEqual(resolve_cli_lang("ko", env), "ko")
        self.assertEqual(resolve_cli_lang(None, {"LC_ALL": "C", "LC_MESSAGES": "ko", "LANG": "ko"}), "en")
        self.assertEqual(resolve_cli_lang(None, {"LC_MESSAGES": "ko", "LANG": "C"}), "ko")
        self.assertEqual(resolve_cli_lang(None, {"LANG": "ko_KR.UTF-8"}), "ko")
        self.assertEqual(resolve_cli_lang(None, {"LLM_FORMAT_GUARD_LANG": "weird", "LANG": "ko"}), "en")

    def test_cli_follows_priority(self):
        _, out, _ = run("detect", "이 자료 좀 봐 줘", env={"LANG": "ko_KR.UTF-8"})
        self.assertRegex(out, HANGUL)
        _, out, _ = run("detect", "이 자료 좀 봐 줘", env={"LANG": "ko_KR.UTF-8", "LLM_FORMAT_GUARD_LANG": "en"})
        self.assertIn("no format or length", out)
        _, out, _ = run("--lang", "en", "detect", "이 자료 좀 봐 줘", env={"LLM_FORMAT_GUARD_LANG": "ko"})
        self.assertIn("no format or length", out)
        _, out, _ = run("detect", "이 자료 좀 봐 줘", env={"LANG": "C"})
        self.assertIn("no format or length", out)


class TestKorean(unittest.TestCase):
    def test_help_in_korean(self):
        for argv in (("--lang", "ko", "--help"), ("--help",)):
            code, out, _ = run(*argv, env={"LANG": "ko_KR.UTF-8"})
            self.assertEqual(code, 0)
            self.assertIn("형식·길이", out)
        code, out, _ = run("--lang", "ko", "eval", "--help")
        self.assertIn("대화 JSONL", out)

    def test_help_in_english(self):
        code, out, _ = run("--lang", "en", "--help", env={"LANG": "ko_KR.UTF-8"})
        self.assertIn("Detect, measure and evaluate", out)
        self.assertNotRegex(out, HANGUL)

    def test_detect_empty_and_table(self):
        _, out, _ = run("--lang", "ko", "detect", "안녕")
        self.assertIn("찾은 형식·길이 제약이 없습니다", out)
        _, out, _ = run("--lang", "ko", "detect", "세 줄로 알려 줘")
        self.assertIn("축", out)
        self.assertIn("lines", out)  # rule ids are not translated

    def test_measure_headers(self):
        _, out, _ = run("--lang", "ko", "measure", str(ANSWER))
        self.assertIn("지표", out)
        self.assertIn("chars", out)

    def test_eval_report(self):
        code, out, _ = run("eval", str(CONVERSATIONS), "--mock", env={"LANG": "ko_KR.UTF-8"})
        self.assertEqual(code, 0)
        for word in ("준수율", "축별 준수율", "종류별 위반", "참고:", "repaired"):
            self.assertIn(word, out)
        code, out, _ = run("eval", str(CONVERSATIONS), "--mock", env={"LANG": "C"})
        self.assertIn("compliance by axis", out)
        self.assertIn("NOTE:", out)

    def test_error_prefix_and_localized_errors(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.jsonl"
            bad.write_text("not json\n", encoding="utf-8")
            code, _, err = run("--lang", "ko", "eval", str(bad))
            self.assertEqual(code, 2)
            self.assertTrue(err.startswith("오류:"))
            self.assertIn("올바르지 않습니다", err)
            code, _, err = run("--lang", "en", "eval", str(bad))
            self.assertEqual(code, 2)
            self.assertIn("invalid JSON", err)
            empty = Path(d) / "empty.jsonl"
            empty.write_text("", encoding="utf-8")
            code, _, err = run("--lang", "ko", "eval", str(empty))
            self.assertEqual(code, 2)
            self.assertIn("대화가 없습니다", err)
            # every CLI error is fully Korean (no English sentence mixed in)
            nomsg = Path(d) / "nomsg.jsonl"
            nomsg.write_text('{"x":1}\n', encoding="utf-8")
            code, _, err = run("--lang", "ko", "eval", str(nomsg))
            self.assertEqual(code, 2)
            self.assertIn("가 필요합니다", err)
            self.assertNotIn("needs", err)
            code, _, err = run("--lang", "en", "eval", str(nomsg))
            self.assertIn('needs "messages"', err)
            na = Path(d) / "na.jsonl"
            na.write_text(json.dumps({"messages": [{"role": "user", "content": "세 줄로"}]}) + "\n",
                          encoding="utf-8")
            code, _, err = run("--lang", "ko", "eval", str(na))
            self.assertEqual(code, 2)
            self.assertIn("answer", err)
            self.assertIn("기록된 답변", err)
            self.assertNotIn("add the recorded", err)
        code, _, err = run("--lang", "ko", "measure", "/nonexistent/answer.md")
        self.assertEqual(code, 2)
        self.assertIn("파일을 찾을 수 없습니다: /nonexistent/answer.md", err)
        self.assertNotIn("Errno", err)
        code, _, err = run("--lang", "en", "measure", "/nonexistent/answer.md")
        self.assertIn("no such file: /nonexistent/answer.md", err)

    def test_kss_missing_localized(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.md"
            f.write_text("hello.\n", encoding="utf-8")
            with mock.patch.dict("sys.modules", {"kss": None}):
                code, _, err = run("--lang", "ko", "measure", str(f), "--splitter", "kss")
                self.assertEqual(code, 2)
                self.assertIn("선택 패키지 kss", err)
                code, _, err = run("--lang", "en", "measure", str(f), "--splitter", "kss")
                self.assertIn("optional kss package", err)

    def test_library_error_text_unchanged(self):
        from llm_format_guard.errors import FormatGuardError
        from llm_format_guard.evaluate import load_conversations
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.jsonl"
            f.write_text('{"x":1}\n', encoding="utf-8")
            with self.assertRaises(FormatGuardError) as cm:
                load_conversations(str(f))
            self.assertTrue(str(cm.exception).endswith('{"role": ..., "content": ...}'))
            self.assertEqual(cm.exception.code, "bad_messages")

    def test_error_accepts_several_positional_args(self):
        from llm_format_guard.errors import FormatGuardError
        exc = FormatGuardError("a", "b")
        self.assertEqual(exc.args, ("a", "b"))
        self.assertIsNone(exc.code)

    def test_table_aligns_by_display_width(self):
        code, out, _ = run("--lang", "ko", "detect", "세 줄로 써 주세요")
        lines = out.splitlines()
        from llm_format_guard._i18n import display_width
        head = lines[0]
        starts = [head.index("값"), head.index("원문")]
        for line in lines[1:]:
            # the value and text columns start at the same display column as the header
            self.assertEqual(display_width(line[:line.index(line.split()[2])]), display_width(head[:starts[0]]))

    def test_help_strings_localized(self):
        code, out, _ = run("--lang", "ko", "--help")
        self.assertIn("이 도움말을 보여 주고 종료합니다", out)
        self.assertNotIn("show this help", out)
        self.assertNotIn("재고", out)

    def test_argparse_errors_keep_exit_code_2(self):
        code, _, err = run("--lang", "xx", "detect", "a")
        self.assertEqual(code, 2)
        self.assertRegex(err, r"invalid choice: '?xx'?")
        self.assertEqual(len(re.findall(r"invalid choice", err)), 1)
        self.assertEqual(len(re.findall(r"^usage:", err, re.M)), 1)
        code, _, err = run("--lang", "ko", "eval", "x", "--mode", "zz")
        self.assertEqual(code, 2)
        self.assertRegex(err, r"invalid choice: '?zz'?")


class TestJsonInvariant(unittest.TestCase):
    def test_json_identical_across_languages(self):
        cases = (
            ("detect", "항목 5개로, 200자 이내로 정리하고 표로 줘", "--json"),
            ("detect", "이 자료 좀 봐 줘", "--json"),
            ("measure", str(ANSWER), "--json"),
            ("eval", str(CONVERSATIONS), "--json"),
            ("eval", str(CONVERSATIONS), "--mock", "--json"),
        )
        for argv in cases:
            c_en, en, _ = run("--lang", "en", *argv)
            c_ko, ko, _ = run("--lang", "ko", *argv)
            c_env, env, _ = run(*argv, env={"LANG": "ko_KR.UTF-8"})
            self.assertEqual((c_en, c_ko, c_env), (0, 0, 0))
            self.assertEqual(en.encode("utf-8"), ko.encode("utf-8"), argv)
            self.assertEqual(en.encode("utf-8"), env.encode("utf-8"), argv)
            json.loads(en)


class TestLibraryUnchanged(unittest.TestCase):
    def test_exception_text_and_attributes(self):
        from llm_format_guard import FormatGuardError
        from llm_format_guard.evaluate import load_conversations

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.jsonl"
            p.write_text("", encoding="utf-8")
            with self.assertRaises(FormatGuardError) as cm:
                load_conversations(str(p))
            self.assertEqual(str(cm.exception), f"{p}: no conversations found")
        self.assertEqual(str(FormatGuardError("plain")), "plain")
        self.assertIsNone(FormatGuardError("plain").code)


if __name__ == "__main__":
    unittest.main()
