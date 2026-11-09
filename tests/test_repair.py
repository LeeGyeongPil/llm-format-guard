"""AC-5: the single repair attempt and the adoption rule."""

import unittest

from llm_format_guard import check, detect, repair

MESSAGES = [{"role": "user", "content": "세 줄로 요약해 줘"}]
FOUR = "가나다.\n라마바.\n사아자.\n차카타."
THREE = "가나다.\n라마바.\n사아자."
SEVEN = "\n".join(["문장입니다."] * 7)
CONSTRAINTS = detect("세 줄로")


def run(answer, reply, constraints=CONSTRAINTS):
    calls = []

    def call_llm(messages):
        calls.append(messages)
        if isinstance(reply, Exception):
            raise reply
        return reply

    violations = check(answer, constraints)
    result = repair(MESSAGES, answer, violations, call_llm, constraints=constraints)
    return result, calls


class TestRepair(unittest.TestCase):
    def test_improvement_is_adopted(self):
        result, calls = run(FOUR, THREE)
        self.assertTrue(result.adopted)
        self.assertEqual(result.text, THREE)
        self.assertEqual(result.reason, "improved")
        self.assertEqual(result.extra_calls, 1)
        self.assertEqual(len(calls), 1)

    def test_feedback_carries_numbers_and_answer(self):
        _, calls = run(FOUR, THREE)
        sent = calls[0]
        self.assertEqual(sent[-2], {"role": "assistant", "content": FOUR})
        self.assertIn("현재 4줄", sent[-1]["content"])
        self.assertIn("목표 3줄 이하", sent[-1]["content"])

    def test_same_result_keeps_original(self):
        result, calls = run(FOUR, FOUR)
        self.assertFalse(result.adopted)
        self.assertEqual(result.text, FOUR)
        self.assertEqual(result.reason, "not_improved")
        self.assertEqual(len(calls), 1)

    def test_worse_result_keeps_original(self):
        result, _ = run(FOUR, SEVEN)
        self.assertFalse(result.adopted)
        self.assertEqual(result.text, FOUR)
        self.assertGreater(result.after, result.before)

    def test_closer_but_still_violating_is_adopted(self):
        # same violation count, smaller distance: lexicographic comparison prefers it
        result, _ = run(SEVEN, FOUR)
        self.assertTrue(result.adopted)

    def test_fixing_length_but_breaking_shape_is_rejected(self):
        constraints = detect("표로, 3행만")
        table5 = "| a |\n|---|\n" + "\n".join(f"| {i} |" for i in range(5))
        bullets3 = "- 1\n- 2\n- 3"
        result, _ = run(table5, bullets3, constraints)
        self.assertFalse(result.adopted)
        self.assertEqual(result.text, table5)
        self.assertEqual(result.reason, "not_improved")

    def test_callback_error_keeps_original(self):
        result, calls = run(FOUR, RuntimeError("timeout"))
        self.assertFalse(result.adopted)
        self.assertEqual(result.text, FOUR)
        self.assertEqual(result.reason, "repair_call_failed")
        self.assertIn("timeout", result.error)
        self.assertEqual(len(calls), 1)

    def test_empty_reply_keeps_original(self):
        result, _ = run(FOUR, "   ")
        self.assertEqual((result.adopted, result.reason), (False, "empty_repair"))

    def test_no_violations_makes_no_call(self):
        result, calls = run(THREE, "x")
        self.assertEqual((result.adopted, result.reason, result.extra_calls), (False, "no_violations", 0))
        self.assertEqual(calls, [])

    def test_input_messages_are_not_mutated(self):
        run(FOUR, THREE)
        self.assertEqual(MESSAGES, [{"role": "user", "content": "세 줄로 요약해 줘"}])


if __name__ == "__main__":
    unittest.main()
