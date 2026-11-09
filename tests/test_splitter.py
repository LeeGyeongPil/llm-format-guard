"""AC-9: sentence splitting and the optional kss extra."""

import importlib.util
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

from llm_format_guard import SplitterUnavailable, measure

ROOT = Path(__file__).resolve().parents[1]
HAS_KSS = importlib.util.find_spec("kss") is not None


class TestSplitter(unittest.TestCase):
    def test_pyproject_declares_pinned_kss_extra(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(text, r'kss\s*=\s*\[\s*"kss==6\.0\.6"\s*\]')
        self.assertRegex(text, r"dependencies\s*=\s*\[\s*\]")

    def test_kss_missing_raises_with_install_command(self):
        with mock.patch.dict(sys.modules, {"kss": None}):  # makes `import kss` fail
            with self.assertRaises(SplitterUnavailable) as ctx:
                measure("하나. 둘.", splitter="kss")
        self.assertIn('pip install "llm-format-guard[kss]"', str(ctx.exception))
        # QA Q-2: also name an install route that works before the PyPI release
        self.assertIn("git+https://github.com/LeeGyeongPil/llm-format-guard", str(ctx.exception))
        self.assertIn("uv sync --extra kss", str(ctx.exception))

    def test_unknown_splitter_is_rejected(self):
        with self.assertRaises(ValueError):
            measure("하나.", splitter="nltk")

    def test_builtin_default(self):
        self.assertEqual(measure("하나. 둘.").sentences, 2)

    @unittest.skipUnless(HAS_KSS, "kss is not installed (optional extra)")
    def test_kss_splits_sentences_without_periods(self):
        text = "회의는 3시에 시작합니다 자료는 미리 읽어 오세요 질문은 끝나고 받겠습니다"
        self.assertEqual(measure(text, splitter="kss").sentences, 3)
        self.assertEqual(measure(text).sentences, 1)  # built-in: no punctuation, one line, one sentence


if __name__ == "__main__":
    unittest.main()
