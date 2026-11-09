"""AC-2: deterministic measurement regression corpus."""

import dataclasses
import json
import unittest
from pathlib import Path

from llm_format_guard import measure

DATA = Path(__file__).parent / "data" / "measure_cases.jsonl"


class TestMeasure(unittest.TestCase):
    def test_corpus(self):
        cases = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(cases), 20)
        for case in cases:
            with self.subTest(name=case["name"]):
                got = dataclasses.asdict(measure(case["text"]))
                for key, want in case["expect"].items():
                    self.assertEqual(got[key], want, key)

    def test_same_input_same_output(self):
        text = "첫 문장입니다. 둘째 문장입니다.\n- 항목"
        self.assertEqual(measure(text), measure(text))

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            measure(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
