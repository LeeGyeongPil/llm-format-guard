"""The ledger remembers an instruction across turns and shows what would be re-injected."""

from llm_format_guard import Ledger

ledger = Ledger()
ledger.update("세 줄로 요약해 줘", turn=0)
ledger.update("점심 뭐 먹을까?", turn=1)
print(ledger.render())
print("--- after a release phrase ---")
ledger.update("이제 길게 써도 돼", turn=2)
print(repr(ledger.render()), len(ledger.active))
