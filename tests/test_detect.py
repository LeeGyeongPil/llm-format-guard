"""AC-1: constraint detection regression corpus."""

import json
import unittest
from pathlib import Path

from llm_format_guard import detect
from llm_format_guard.detect import detect_release

DATA = Path(__file__).parent / "data" / "detect_cases.jsonl"


def triples(text):
    return sorted([c.axis, c.op, c.value] for c in detect(text))


class TestDetect(unittest.TestCase):
    def test_corpus(self):
        cases = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(cases), 40)
        self.assertGreaterEqual(sum(1 for c in cases if not c["expect"]), 10, "need >= 10 negative cases")
        for case in cases:
            with self.subTest(text=case["text"]):
                self.assertEqual(triples(case["text"]), sorted(case["expect"]))

    def test_probe_regressions(self):
        self.assertEqual(triples("항목 5개로 정리"), [["items", "le", 5]])
        self.assertEqual(triples("2개 문단으로"), [["paragraphs", "le", 2]])
        self.assertEqual(len(detect("Answer in no more than 3 sentences")), 1)
        self.assertEqual(triples("Answer in no more than 3 sentences"), [["sentences", "le", 3]])
        self.assertEqual(triples("한 줄로 답해"), [["lines", "le", 1]])
        self.assertEqual(detect("이 자료 좀 봐 줘"), [])
        self.assertEqual(detect("사과 5개로 나눠"), [])

    def test_odd_input_is_bounded(self):
        # QA Q-7: huge numbers are dropped, long repeated input stays fast.
        import time
        self.assertEqual(detect("1" * 5000 + "줄로 써"), [])
        self.assertEqual(detect("99999999줄로"), [])
        start = time.monotonic()
        self.assertEqual(len(detect("세 줄 " * 4000)), 4000)
        self.assertLess(time.monotonic() - start, 2.0)

    def test_turn_and_span_are_recorded(self):
        text = "앞에서 세 줄로 요약"
        (c,) = detect(text, turn=4)
        self.assertEqual(c.turn, 4)
        self.assertEqual(text[c.span[0]:c.span[1]], "세 줄")

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError) as ctx:
            detect({"role": "user", "content": "세 줄로"})  # type: ignore[arg-type]
        self.assertIn("message text", str(ctx.exception))

    def test_release_phrases(self):
        self.assertIn("lines", detect_release("이제 길게 써도 돼"))
        self.assertNotIn("shape_table", detect_release("이제 길게 써도 돼"))
        self.assertIn("shape_table", detect_release("형식 상관없이 써 줘"))
        self.assertIn("lines", detect_release("No limit on length"))
        self.assertIn("shape_list", detect_release("any format is fine"))
        self.assertEqual(detect_release("세 줄로 써 줘"), frozenset())


if __name__ == "__main__":
    unittest.main()
