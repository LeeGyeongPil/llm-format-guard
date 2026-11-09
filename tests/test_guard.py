"""AC-6: the guard() path end to end, with the practice mock model."""

import copy
import unittest

from llm_format_guard import LLMCallError, Ledger, MockLLM, guard, measure


def chat(*users, system=True):
    msgs = [{"role": "system", "content": "You are helpful."}] if system else []
    for i, u in enumerate(users):
        msgs.append({"role": "user", "content": u})
        if i < len(users) - 1:
            msgs.append({"role": "assistant", "content": "ok"})
    return msgs


class TestGuard(unittest.TestCase):
    def test_no_constraint_one_call_messages_unchanged(self):
        msgs = chat("이 자료 좀 봐 줘")
        before = copy.deepcopy(msgs)
        seen = []

        def call_llm(m):
            seen.append(m)
            return "네."

        result = guard(msgs, call_llm)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0], before)
        self.assertEqual(msgs, before)
        self.assertFalse(result.injected)
        self.assertEqual((result.llm_calls, result.text, result.violations_before), (1, "네.", ()))

    def test_reminder_goes_right_before_last_user_message(self):
        llm = MockLLM()
        result = guard(chat("앞으로 세 줄로 요약해 줘", "점심 뭐 먹지?", "이것도 부탁해"), llm)
        sent = list(result.messages_sent)
        self.assertTrue(result.injected)
        self.assertEqual(sent[-2]["role"], "system")
        self.assertTrue(sent[-2]["content"].startswith("[활성 제약]"))
        self.assertEqual(sent[-1]["content"], "이것도 부탁해")

    def test_mock_model_ends_with_three_lines(self):
        llm = MockLLM()
        result = guard(chat("앞으로 세 줄로 요약해 줘", "점심 뭐 먹지?", "이것도 부탁해"), llm)
        self.assertEqual(measure(result.original).lines, 4)  # reminder helps, still one too long
        self.assertEqual(measure(result.text).lines, 3)
        self.assertEqual(result.violations_after, ())
        self.assertTrue(result.adopted)
        self.assertEqual((result.llm_calls, llm.calls), (2, 2))

    def test_without_reminder_the_mock_forgets(self):
        # same chat, but injection disabled by an empty ledger: the practice model drifts
        llm = MockLLM()
        ledger = Ledger.from_messages(chat("앞으로 세 줄로 요약해 줘", "점심?", "이것도"))
        text_plain = llm(chat("앞으로 세 줄로 요약해 줘", "점심?", "이것도"))
        self.assertGreater(measure(text_plain).lines, 5)
        self.assertEqual(len(ledger.active), 1)

    def test_repair_can_be_turned_off(self):
        llm = MockLLM()
        result = guard(chat("앞으로 세 줄로 요약해 줘", "점심?", "이것도"), llm, repair=False)
        self.assertEqual(result.llm_calls, 1)
        self.assertEqual(len(result.violations_after), 1)
        self.assertFalse(result.adopted)

    def test_rewrite_that_drops_the_table_is_rejected(self):
        llm = MockLLM()
        result = guard(chat("파이썬 자료형을 표로, 3행만 보여 줘"), llm)
        self.assertFalse(result.adopted)
        self.assertEqual(result.repair_reason, "not_improved")
        self.assertEqual(result.text, result.original)
        self.assertTrue(result.text.startswith("|"))

    def test_english_chat_gets_english_block(self):
        llm = MockLLM()
        result = guard(chat("Answer in at most 2 sentences.", "What is DNS?", "And DHCP?"), llm)
        self.assertIn("[Active constraints]", result.messages_sent[-2]["content"])
        self.assertEqual(measure(result.text).sentences, 2)

    def test_position_option(self):
        result = guard(chat("앞으로 세 줄로 요약해 줘", "이건?"), MockLLM(), position="system_end")
        self.assertIn("[활성 제약]", result.messages_sent[0]["content"])

    def test_disabled_ledger_means_no_injection(self):
        result = guard(chat("세 줄로 요약해 줘"), MockLLM(), ledger=Ledger(max_items=0))
        self.assertFalse(result.injected)
        self.assertEqual(result.llm_calls, 1)

    def test_first_call_error_propagates(self):
        def boom(messages):
            raise ConnectionError("down")

        with self.assertRaises(ConnectionError):
            guard(chat("세 줄로"), boom)

    def test_non_string_answer_is_explained(self):
        with self.assertRaises(LLMCallError) as ctx:
            guard(chat("세 줄로"), lambda m: {"text": "x"})
        self.assertIn("must return the answer as a str", str(ctx.exception))

    def test_call_llm_must_be_callable(self):
        with self.assertRaises(TypeError):
            guard(chat("세 줄로"), "not callable")  # type: ignore[arg-type]

    def test_messages_must_be_dicts(self):
        for bad in ("hello", ["hello"], 5):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError) as ctx:
                    guard(bad, lambda m: "x")  # type: ignore[arg-type]
                self.assertIn('"role", "content"', str(ctx.exception))

    def test_material_size_is_not_a_constraint(self):
        calls = []
        res = guard([{"role": "user", "content": "에러 로그 첫 3줄만 봐 줘: ..."}],
                    lambda m: calls.append(m) or "a\nb\nc\nd\ne")
        self.assertEqual(res.constraints, ())
        self.assertEqual(res.llm_calls, 1)

    def test_input_is_not_mutated(self):
        msgs = chat("앞으로 세 줄로 요약해 줘", "이건?")
        before = copy.deepcopy(msgs)
        guard(msgs, MockLLM())
        self.assertEqual(msgs, before)

    def test_mock_is_deterministic(self):
        msgs = chat("앞으로 세 줄로 요약해 줘", "이건?")
        a = guard(msgs, MockLLM())
        b = guard(msgs, MockLLM())
        self.assertEqual((a.original, a.text), (b.original, b.text))

    def test_mock_script_overrides_rules(self):
        llm = MockLLM(script=["첫 답"])
        self.assertEqual(llm([{"role": "user", "content": "아무거나"}]), "첫 답")
        self.assertEqual(llm.calls, 1)

    def test_mock_notice_is_honest(self):
        self.assertIn("연습용 목(mock)", MockLLM.NOTICE)
        self.assertIn("실제 모델의 측정값이 아닙니다", MockLLM.NOTICE)


if __name__ == "__main__":
    unittest.main()
