# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-12

### Added
- Command line output language: English or Korean for help (including `-h` and `--version`), table headers (aligned by display width), the `eval` text report, `NOTE:`/`error:` prefixes and the CLI error sentences (missing or invalid conversations file, missing `messages` or `answer`, missing file, missing kss). Chosen by `--lang en|ko`, then `LLM_FORMAT_GUARD_LANG`, then `LC_ALL`, `LC_MESSAGES`, `LANG` (a value starting with `ko` is Korean, everything else English).
- `FormatGuardError` accepts optional keyword-only `code` and `params`; `str(exc)` is unchanged.

### Changed
- Text output now follows the shell language when `LANG` is Korean. Scripts that parse the text output should pass `--lang en` or set `LLM_FORMAT_GUARD_LANG=en`.

### Unchanged
- `--json` output, rule ids, exit codes, the library API and exception messages.

## [0.1.2] - 2026-11-10

### Fixed
- `measure()` counts the visible text of table cells (header and data rows, without separator lines and pipes) in `chars`, `chars_no_space` and `words`. Before, a table-only answer measured 0 characters, so a length limit combined with a table instruction ("200자 이내로 … 표로 줘") never reported a violation. Sentences, items, lines and table rows are unchanged.

## [0.1.1] - 2026-11-10

### Changed
- README: replace the comparison table with a short when-to-use section.

## [0.1.0] - 2026-11-09

### Added
- `detect()`: regex first filter for Korean and English format and length instructions
  (lines, sentences, characters, words, items, paragraphs, table rows, table and list shape),
  with Arabic, native Korean, Sino-Korean and English number words.
- `Ledger`: remembers constraints across user turns (6-turn window, newest wins per axis,
  release phrases, at most 5) and re-injects them as a positive-sentence block in three positions.
- `measure()`: deterministic, markdown-aware counting (code fences and `<think>` tags excluded).
- `check()`: `loose` and `strict` judging with numeric messages.
- `repair()`: one rewrite attempt, adopted only when it strictly reduces violations.
- `guard()`: all steps in one call.
- `MockLLM`: practice (mock) model that forgets instructions by fixed rules; not a real model.
- Optional `kss` extra (`kss==6.0.6`) for Korean sentence splitting.
- Command line: `llm-format-guard detect | measure | eval`.
- `examples/quickstart.py`, `examples/with_ollama.py`, hand-written conversations fixture.
- `examples/check_only.py`, `examples/ledger_demo.py`, `examples/data/my-chats.jsonl` (a two-line eval input), `docs/how-it-works.md`.
- Fixes before first release: `detect()` ignores the size of the material ("첫 3줄만 봐 줘"), overlap removal is O(n log n) with oversized numbers ignored, `guard()` raises a clear `TypeError` for bad `messages`, ranges in one message keep both bounds, the `SplitterUnavailable` message names a route that works before the PyPI release.
- README: field table for the eval JSONL input, `position` guide, limits and roadmap.

[0.1.2]: https://github.com/LeeGyeongPil/llm-format-guard/releases/tag/v0.1.2
[0.1.1]: https://github.com/LeeGyeongPil/llm-format-guard/releases/tag/v0.1.1
[0.1.0]: https://github.com/LeeGyeongPil/llm-format-guard/releases/tag/v0.1.0
