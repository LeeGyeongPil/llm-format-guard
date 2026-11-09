"""No model at all: pull constraints from a message, then measure and judge an answer."""

from llm_format_guard import check, detect, measure

constraints = detect("항목 5개로, 200자 이내로 정리하고 표로 줘")
answer = "- 하나\n- 둘\n- 셋\n- 넷\n- 다섯\n- 여섯"

print(measure(answer))
for v in check(answer, constraints):
    print(v.kind, "|", v.message)
