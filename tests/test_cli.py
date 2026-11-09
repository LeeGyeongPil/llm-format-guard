"""AC-7, AC-8: command line and the mock evaluation."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from llm_format_guard.cli import main

ROOT = Path(__file__).resolve().parents[1]
CONVERSATIONS = ROOT / "examples" / "data" / "conversations.jsonl"
ANSWER = ROOT / "examples" / "data" / "answer.md"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:  # argparse errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):
    def test_eval_mock_improves(self):
        code, out, _ = run("eval", str(CONVERSATIONS), "--mock", "--json")
        self.assertEqual(code, 0)
        report = json.loads(out)
        for key in ("detection_rate", "compliance_by_axis", "violations_by_kind", "stages"):
            self.assertIn(key, report)
        s = report["stages"]
        self.assertLess(s["raw"], s["injected"])
        self.assertLess(s["injected"], s["repaired"])
        self.assertTrue(report["mock"])
        self.assertIn("연습용 목(mock)", report["notice"])
        self.assertEqual(report["false_detections"], 0)
        self.assertEqual(report["detection_rate"], 1.0)

    def test_eval_mock_text_output_is_labelled(self):
        code, out, _ = run("eval", str(CONVERSATIONS), "--mock")
        self.assertEqual(code, 0)
        self.assertIn("연습용 목(mock)", out)
        self.assertIn("repaired", out)

    def test_eval_recorded_answers(self):
        code, out, _ = run("eval", str(CONVERSATIONS), "--json")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(list(report["stages"]), ["recorded"])
        self.assertFalse(report["mock"])
        self.assertGreater(report["stages"]["recorded"], 0)
        self.assertLess(report["stages"]["recorded"], 1)

    def test_fixture_composition(self):
        rows = [json.loads(l) for l in CONVERSATIONS.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(r["source"] == "handwritten" for r in rows))
        self.assertGreaterEqual(sum(1 for r in rows if not r["expect"]), 5)

    def test_eval_errors_are_readable(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.jsonl"
            bad.write_text('{"messages": []}\n', encoding="utf-8")
            code, _, err = run("eval", str(bad), "--mock")
            self.assertEqual(code, 2)
            self.assertIn("messages", err)
            bad.write_text("not json\n", encoding="utf-8")
            code, _, err = run("eval", str(bad))
            self.assertEqual(code, 2)
            self.assertIn("invalid JSON", err)
            noanswer = Path(d) / "na.jsonl"
            noanswer.write_text(json.dumps({"messages": [{"role": "user", "content": "세 줄로"}]}) + "\n",
                                encoding="utf-8")
            code, _, err = run("eval", str(noanswer))
            self.assertEqual(code, 2)
            self.assertIn("--mock", err)
        code, _, err = run("eval", "/nonexistent/file.jsonl")
        self.assertEqual(code, 2)

    def test_detect_command(self):
        code, out, _ = run("detect", "항목 5개로, 200자 이내로 정리하고 표로 줘")
        self.assertEqual(code, 0)
        for word in ("items", "chars", "shape_table"):
            self.assertIn(word, out)
        code, out, _ = run("detect", "이 자료 좀 봐 줘", "--json")
        self.assertEqual(json.loads(out), [])

    def test_measure_command(self):
        code, out, _ = run("measure", str(ANSWER), "--json")
        self.assertEqual(code, 0)
        m = json.loads(out)
        self.assertEqual((m["table_rows"], m["items"], m["has_table"]), (3, 2, True))
        self.assertEqual(m["lines"], 8)  # code block and <think> are excluded

    def test_measure_missing_file(self):
        code, _, err = run("measure", "/nonexistent/answer.md")
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_quickstart_runs_and_prints_result_line(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        done = subprocess.run([sys.executable, str(ROOT / "examples" / "quickstart.py")],
                              capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("연습용 목(mock)", done.stdout)
        last = done.stdout.strip().splitlines()[-1]
        self.assertEqual(last, "RESULT before_lines=4 after_lines=3 violations_after=0 adopted=True")

    def test_module_entry_point(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        done = subprocess.run([sys.executable, "-m", "llm_format_guard", "detect", "세 줄로"],
                              capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("lines", done.stdout)


if __name__ == "__main__":
    unittest.main()
