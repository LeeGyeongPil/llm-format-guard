"""Regression: table cell text counts toward chars and words (v0.1.2)."""

import unittest

from llm_format_guard import check, detect, measure

ROW = "| 신제품 출시 일정과 가격 정책에 대한 자세한 설명입니다 | 다음 달부터 전국 매장에서 판매를 시작할 예정입니다 |"
LONG_TABLE = "| 항목 | 설명 |\n|---|---|\n" + "\n".join([ROW] * 5)


class TableCellTests(unittest.TestCase):
    def test_cells_counted_in_chars_and_words(self):
        m = measure(LONG_TABLE)
        self.assertGreater(m.chars, 200)
        self.assertGreater(m.words, 0)
        self.assertEqual(m.table_rows, 5)
        self.assertTrue(m.has_table)
        self.assertEqual(m.sentences, 0)  # sentences stay prose-only

    def test_short_table_values(self):
        m = measure("| a |\n|---|\n| 1 |")
        self.assertEqual((m.chars, m.chars_no_space, m.words), (2, 2, 2))

    def test_length_limit_with_table_is_enforced(self):
        constraints = detect("항목 5개로, 200자 이내로 정리하고 표로 줘")
        violations = check(LONG_TABLE, constraints)
        over = [v for v in violations if v.constraint.axis == "chars"]
        self.assertEqual(len(violations), 1)
        self.assertEqual(len(over), 1)
        self.assertIn("목표 200자 이하", over[0].message)

    def test_short_table_still_passes_table_instruction(self):
        self.assertEqual(check("| a |\n|---|\n| 1 |", detect("표로 줘")), [])


if __name__ == "__main__":
    unittest.main()
