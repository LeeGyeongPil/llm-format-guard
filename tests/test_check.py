"""AC-4: judging answers."""

import unittest

from llm_format_guard import check, detect, measure
from llm_format_guard.check import violation_distance

SEVEN_LINES = "\n".join(f"줄 {i}입니다." for i in range(7))


class TestCheck(unittest.TestCase):
    def test_over_has_numeric_message(self):
        (v,) = check(SEVEN_LINES, detect("세 줄로"))
        self.assertEqual(v.kind, "over")
        self.assertEqual(v.actual, 7)
        self.assertIn("현재 7줄", v.message)
        self.assertIn("목표 3줄 이하", v.message)

    def test_english_message(self):
        (v,) = check(SEVEN_LINES, detect("in 3 lines"), lang="en")
        self.assertIn("currently 7 lines", v.message)
        self.assertIn("at most 3 lines", v.message)

    def test_under(self):
        (v,) = check("한 문장입니다.", detect("5문장 이상"))
        self.assertEqual((v.kind, v.actual), ("under", 1))
        self.assertIn("목표 5문장 이상", v.message)

    def test_shape_mismatch(self):
        table = check("그냥 문장입니다.", detect("표로 줘"))
        self.assertEqual(table[0].kind, "shape_mismatch")
        self.assertEqual(check("| a |\n|---|\n| 1 |", detect("표로 줘")), [])
        self.assertEqual(check("- 하나\n- 둘", detect("목록으로 줘")), [])

    def test_preamble_loose_passes_strict_fails(self):
        text = "다음은 요약입니다:\n- 하나\n- 둘\n- 셋"
        cs = detect("세 줄로")
        self.assertEqual(check(text, cs, mode="loose"), [])
        (v,) = check(text, cs, mode="strict")
        self.assertEqual(v.actual, 4)

    def test_loose_lower_bound_uses_larger_count(self):
        text = "다음은 요약입니다:\n- 하나\n- 둘\n- 셋"
        self.assertEqual(check(text, detect("4줄 이상"), mode="loose"), [])

    def test_approx_boundaries(self):
        cs = detect("100자 내외")
        self.assertEqual(check("가" * 110, cs), [])
        self.assertEqual(check("가" * 90, cs), [])
        self.assertEqual(len(check("가" * 111, cs)), 1)
        self.assertEqual(len(check("가" * 89, cs)), 1)
        self.assertEqual(len(check("가" * 111, cs, approx_tolerance=0.2)), 0)

    def test_each_operator(self):
        text = "가" * 10
        cases = {"10자 이하": 0, "9자 이하": 1, "10자 미만": 1, "11자 미만": 0, "10자 이상": 0, "11자 이상": 1,
                 "10자 초과": 1, "9자 초과": 0, "정확히 10자": 0, "정확히 9자": 1}
        for msg, n_violations in cases.items():
            with self.subTest(msg=msg):
                self.assertEqual(len(check(text, detect(msg))), n_violations)

    def test_accepts_metrics(self):
        m = measure(SEVEN_LINES)
        self.assertEqual(len(check(m, detect("세 줄로"))), 1)

    def test_table_rows_counts_data_rows(self):
        table = "| a |\n|---|\n| 1 |\n| 2 |\n| 3 |\n| 4 |"
        self.assertEqual(len(check(table, detect("표로, 3행만"))), 1)
        self.assertEqual(check(table, detect("표로, 4행만")), [])

    def test_distance_grows_with_gap(self):
        near = check("가" * 12, detect("10자 이내"))[0]
        far = check("가" * 30, detect("10자 이내"))[0]
        self.assertLess(violation_distance(near), violation_distance(far))

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError) as ctx:
            check("x", detect("세 줄로"), mode="fuzzy")
        self.assertIn("loose", str(ctx.exception))
        with self.assertRaises(ValueError):
            check("x", [], approx_tolerance=5)
        with self.assertRaises(ValueError):
            check("x", [], lang="fr")


if __name__ == "__main__":
    unittest.main()
