"""Quickstart: a user said "세 줄로" three turns ago; the model forgets it; the guard catches it.

Runs with no key and no network. The model here is `MockLLM`, a practice (mock)
model that forgets instructions by fixed rules, not a real model.

    python examples/quickstart.py
"""

from llm_format_guard import MockLLM, guard, measure

print(MockLLM.NOTICE)
print()

# 1턴에 "세 줄로" 지시, 두 턴 동안 다른 얘기, 마지막 턴에는 "이것도"라고만 한다.
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "앞으로 세 줄로 요약해 줘"},
    {"role": "assistant", "content": "네, 세 줄로 요약하겠습니다."},
    {"role": "user", "content": "점심 뭐 먹을까?"},
    {"role": "assistant", "content": "비빔밥은 어때요?"},
    {"role": "user", "content": "이것도 부탁해: 회사가 신제품을 공개했다. 가격은 낮아졌다. 출시는 다음 달이다."},
]

llm = MockLLM()
result = guard(messages, llm)  # 이 한 줄이 전부다: 제약 추출 -> 재주입 -> 측정 -> 필요하면 1회 수선

print("[1] 대화에서 뽑은 제약:")
for c in result.constraints:
    print(f"    {c.axis} {c.op} {c.value}  (말한 곳: 사용자 {c.turn + 1}번째 메시지, \"{c.unit_text}\")")

print("[2] 마지막 사용자 메시지 바로 앞에 다시 넣은 블록:")
for line in result.messages_sent[-2]["content"].splitlines():
    print("    " + line)

print(f"[3] 모델의 첫 답: {measure(result.original).lines}줄")
for v in result.violations_before:
    print(f"    위반: {v.message}")

print(f"[4] 수치 피드백으로 1회 수선 -> 채택 여부 adopted={result.adopted} ({result.repair_reason})")
print("[5] 최종 답:")
for line in result.text.splitlines():
    print("    " + line)

print()
print(f"모델 호출 {result.llm_calls}회 ({MockLLM.__name__} 호출 카운터 {llm.calls})")
print(f"RESULT before_lines={measure(result.original).lines} after_lines={measure(result.text).lines} "
      f"violations_after={len(result.violations_after)} adopted={result.adopted}")
