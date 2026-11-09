"""AC-3: the constraint ledger."""

import copy
import unittest

from llm_format_guard import Ledger


def chat(*users):
    msgs = [{"role": "system", "content": "sys"}]
    for i, u in enumerate(users):
        msgs.append({"role": "user", "content": u})
        if i < len(users) - 1:
            msgs.append({"role": "assistant", "content": "ok"})
    return msgs


class TestLedger(unittest.TestCase):
    def test_range_in_one_message_keeps_both_bounds(self):
        led = Ledger.from_messages(chat("세 줄 이상 다섯 줄 이하로 써 줘"))
        self.assertEqual(sorted((c.op, c.value) for c in led.active), [("ge", 3), ("le", 5)])
        led = Ledger.from_messages(chat("세 줄 이상 다섯 줄 이하로 써 줘", "두 줄 이내로"))
        self.assertEqual([(c.op, c.value) for c in led.active], [("le", 2)])

    def test_same_axis_overwrites(self):
        led = Ledger.from_messages(chat("200자 이내로", "아니 100자 이내로"))
        self.assertEqual([(c.axis, c.value) for c in led.active], [("chars", 100)])

    def test_chars_and_chars_no_space_are_one_axis(self):
        led = Ledger.from_messages(chat("200자 이내로", "공백 제외 100자 이내로"))
        self.assertEqual([(c.axis, c.value) for c in led.active], [("chars_no_space", 100)])

    def test_shape_overwrites_shape(self):
        led = Ledger.from_messages(chat("표로 줘", "목록으로 줘"))
        self.assertEqual([c.axis for c in led.active], ["shape_list"])

    def test_max_five_keeps_newest(self):
        led = Ledger()
        for turn, text in enumerate(["세 줄로", "두 문장으로", "200자 이내로", "항목 4개로", "두 문단으로", "표로"]):
            led.update(text, turn)
        axes = [c.axis for c in led.active]
        self.assertEqual(len(axes), 5)
        self.assertNotIn("lines", axes)  # the oldest one was dropped
        self.assertIn("shape_table", axes)

    def test_release_expires_length_axes(self):
        led = Ledger.from_messages(chat("세 줄로 표로 써 줘", "이제 길게 써도 돼"))
        self.assertEqual([c.axis for c in led.active], ["shape_table"])

    def test_release_then_new_constraint_in_same_message(self):
        led = Ledger.from_messages(chat("세 줄로", "제한 없이, 두 문단으로"))
        self.assertEqual([(c.axis, c.value) for c in led.active], [("paragraphs", 2)])

    def test_window_expires_old_constraints(self):
        users = ["세 줄로"] + ["안녕"] * 6  # constraint is 6 turns behind the last user turn
        self.assertEqual(Ledger.from_messages(chat(*users)).active, [])
        users = ["세 줄로"] + ["안녕"] * 5
        self.assertEqual(len(Ledger.from_messages(chat(*users)).active), 1)
        self.assertEqual(len(Ledger.from_messages(chat(*(["세 줄로"] + ["안녕"] * 6)), window=7).active), 1)

    def test_render_is_positive_only(self):
        led = Ledger.from_messages(chat("세 줄로, 200자 이내로, 표로, 정확히 2문단으로, 100단어 이상"))
        for lang in ("ko", "en"):
            text = led.render(lang)
            self.assertTrue(text.startswith("[활성 제약]" if lang == "ko" else "[Active constraints]"))
            for banned in ("하지 마", "않", "don't", "do not", " not ", "never"):
                self.assertNotIn(banned, text.lower(), lang)
        self.assertIn("답은 3줄 이하로 쓴다.", led.render("ko"))

    def test_render_empty_when_nothing_active(self):
        self.assertEqual(Ledger().render(), "")

    def test_inject_positions_do_not_mutate_input(self):
        msgs = chat("세 줄로", "이건?")
        before = copy.deepcopy(msgs)
        led = Ledger.from_messages(msgs)

        out = led.inject(msgs, "before_last_user")
        self.assertEqual(out[-2]["role"], "system")
        self.assertTrue(out[-2]["content"].startswith("[활성 제약]"))
        self.assertEqual(out[-1], msgs[-1])

        out = led.inject(msgs, "system_end")
        self.assertTrue(out[0]["content"].startswith("sys"))
        self.assertIn("[활성 제약]", out[0]["content"])
        self.assertEqual(len(out), len(msgs))

        out = led.inject(msgs, "in_last_user")
        self.assertTrue(out[-1]["content"].startswith("이건?"))
        self.assertIn("[활성 제약]", out[-1]["content"])

        self.assertEqual(msgs, before)

    def test_system_end_without_system_message_adds_one(self):
        msgs = [{"role": "user", "content": "세 줄로"}]
        out = Ledger.from_messages(msgs).inject(msgs, "system_end")
        self.assertEqual(out[0]["role"], "system")

    def test_in_last_user_supports_content_parts(self):
        msgs = [{"role": "user", "content": [{"type": "text", "text": "세 줄로 요약"}]}]
        out = Ledger.from_messages(msgs).inject(msgs, "in_last_user")
        self.assertEqual(len(out[0]["content"]), 2)
        self.assertEqual(len(msgs[0]["content"]), 1)

    def test_inject_without_constraints_returns_equal_copy(self):
        msgs = chat("안녕")
        out = Ledger.from_messages(msgs).inject(msgs)
        self.assertEqual(out, msgs)
        self.assertIsNot(out, msgs)

    def test_english_block_for_english_chat_with_auto(self):
        msgs = chat("Answer in at most 3 sentences", "And now?")
        out = Ledger.from_messages(msgs).inject(msgs, lang="auto")
        self.assertIn("[Active constraints]", out[-2]["content"])

    def test_pasted_article_in_the_middle_is_not_scanned(self):
        article = "본문 " * 300 + " 세 줄로 나눈다고 쓰여 있는 기사 내용 " + "본문 " * 300
        led = Ledger.from_messages(chat("두 문장으로 요약해 줘: " + article))
        self.assertEqual([(c.axis, c.value) for c in led.active], [("sentences", 2)])

    def test_code_fences_are_ignored(self):
        led = Ledger.from_messages(chat("이 코드를 봐 줘\n```\nprint('세 줄로')\n```"))
        self.assertEqual(led.active, [])

    def test_max_items_zero_disables(self):
        self.assertEqual(Ledger.from_messages(chat("세 줄로"), max_items=0).active, [])

    def test_invalid_arguments_have_fix_hints(self):
        with self.assertRaises(ValueError) as ctx:
            Ledger(window=0)
        self.assertIn("window", str(ctx.exception))
        with self.assertRaises(ValueError):
            Ledger(max_items=-1)
        with self.assertRaises(TypeError):
            Ledger.from_messages("세 줄로")  # type: ignore[arg-type]
        with self.assertRaises(ValueError) as ctx:
            Ledger().inject([], position="middle")
        self.assertIn("before_last_user", str(ctx.exception))
        with self.assertRaises(ValueError):
            Ledger.from_messages(chat("세 줄로")).inject([{"role": "system", "content": "x"}])


if __name__ == "__main__":
    unittest.main()
