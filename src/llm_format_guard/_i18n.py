"""Message table and language choice for the command line (internal).

Only text meant for people lives here. JSON output, rule ids, metric names and stage
names are identifiers and are never translated.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Dict, Mapping, Optional

SUPPORTED = ("en", "ko")
ENV_VAR = "LLM_FORMAT_GUARD_LANG"

MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "description": "Detect, measure and evaluate format/length instructions for LLM answers.",
        "help_lang": "language of human-readable output (default: {env}, then LC_ALL, LC_MESSAGES, LANG, else en)",
        "help_detect": "show the constraints found in one message",
        "help_measure": "count lines, sentences, characters ... of an answer file ('-' = stdin)",
        "help_eval": "score a conversations JSONL file",
        "help_text": "the user message to inspect",
        "help_file": "answer file to measure ('-' = stdin)",
        "help_jsonl": "conversations JSONL file",
        "help_json": "print machine-readable JSON (identical in every language)",
        "help_splitter": "sentence splitter (default: builtin)",
        "help_mock": "run the practice mock model in three stages",
        "help_mode": "judging mode (default: loose)",
        "no_constraint": "(no format or length constraint found)",
        "col_axis": "axis",
        "col_op": "op",
        "col_value": "value",
        "col_text": "text",
        "col_metric": "metric",
        "col_stage": "stage",
        "col_rate": "rate",
        "note_prefix": "NOTE:",
        "error_prefix": "error:",
        "label_conversations": "conversations",
        "label_with_constraints": "with_constraints",
        "label_detection_rate": "detection_rate",
        "label_false_detections": "false_detections",
        "label_mode": "mode",
        "title_compliance": "compliance (share of conversations with no violation)",
        "title_by_axis": "compliance by axis",
        "title_by_kind": "violations by kind",
        "err_invalid_json": "{path}:{line}: invalid JSON ({detail}). One JSON object per line.",
        "err_no_conversations": "{path}: no conversations found",
        "err_bad_messages": '{path}:{line}: needs "messages": a non-empty list of {{"role": ..., "content": ...}}',
        "err_no_answer": 'conversation {conv_id} has no "answer"; add the recorded reply or use --mock',
        "err_kss_missing": 'splitter="kss" needs the optional kss package. Install it with: pip install "llm-format-guard[kss]" (in a clone: uv sync --extra kss).',
        "err_file_not_found": "no such file: {filename}",
        "help_help": "show this help message and exit",
        "help_version": "show the version and exit",
    },
    "ko": {
        "description": "LLM 답변에 대한 형식·길이 지시를 찾아내고, 측정하고, 평가합니다.",
        "help_lang": "사람이 읽는 출력의 언어입니다 (기본값: {env}, LC_ALL, LC_MESSAGES, LANG 순, 없으면 en)",
        "help_detect": "메시지 하나에서 찾은 제약을 보여 줍니다",
        "help_measure": "답변 파일의 줄·문장·글자 수 등을 셉니다 ('-' 는 표준 입력)",
        "help_eval": "대화 JSONL 파일을 채점합니다",
        "help_text": "검사할 사용자 메시지입니다",
        "help_file": "측정할 답변 파일입니다 ('-' 는 표준 입력)",
        "help_jsonl": "대화 JSONL 파일입니다",
        "help_json": "기계가 읽는 JSON 을 출력합니다 (어느 언어에서도 같습니다)",
        "help_splitter": "문장 분리기입니다 (기본값: builtin)",
        "help_mock": "연습용 목(mock) 모델을 세 단계로 돌립니다",
        "help_mode": "판정 모드입니다 (기본값: loose)",
        "no_constraint": "(찾은 형식·길이 제약이 없습니다)",
        "col_axis": "축",
        "col_op": "연산",
        "col_value": "값",
        "col_text": "원문",
        "col_metric": "지표",
        "col_stage": "단계",
        "col_rate": "비율",
        "note_prefix": "참고:",
        "error_prefix": "오류:",
        "label_conversations": "대화 수",
        "label_with_constraints": "제약 있는 대화",
        "label_detection_rate": "탐지율",
        "label_false_detections": "오탐",
        "label_mode": "모드",
        "title_compliance": "준수율 (위반이 없는 대화의 비율)",
        "title_by_axis": "축별 준수율",
        "title_by_kind": "종류별 위반",
        "err_invalid_json": "{path}:{line}: JSON 형식이 올바르지 않습니다 ({detail}). 한 줄에 JSON 객체 하나씩 써야 합니다.",
        "err_no_conversations": "{path}: 대화가 없습니다",
        "err_bad_messages": '{path}:{line}: "messages" 가 필요합니다. {{"role": ..., "content": ...}} 항목이 하나 이상 든 목록이어야 합니다.',
        "err_no_answer": '대화 {conv_id} 에 "answer" 가 없습니다. 기록된 답변을 넣거나 --mock 을 사용하십시오.',
        "err_kss_missing": 'splitter="kss" 에는 선택 패키지 kss 가 필요합니다. pip install "llm-format-guard[kss]" 로 설치하십시오 (클론에서는 uv sync --extra kss).',
        "err_file_not_found": "파일을 찾을 수 없습니다: {filename}",
        "help_help": "이 도움말을 보여 주고 종료합니다",
        "help_version": "버전을 보여 주고 종료합니다",
    },
}


def _from_value(value: Optional[str]) -> Optional[str]:
    """Map one setting to a language, or None when the value is empty."""
    if not value or not value.strip():
        return None
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_cli_lang(arg: Optional[str] = None, environ: Optional[Mapping[str, str]] = None) -> str:
    """Pick the output language: --lang > LLM_FORMAT_GUARD_LANG > LC_ALL > LC_MESSAGES > LANG > en.

    The first non-empty setting wins; ``ko*`` means Korean and anything else means English.
    """
    env = os.environ if environ is None else environ
    if arg in SUPPORTED:
        return str(arg)
    for name in (ENV_VAR, "LC_ALL", "LC_MESSAGES", "LANG"):
        lang = _from_value(env.get(name))
        if lang:
            return lang
    return "en"


def display_width(text: str) -> int:
    """Columns the text takes in a terminal (wide Hangul/CJK characters count as 2)."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def t(lang: str, key: str, **params: object) -> str:
    """Look up a message; falls back to English for an unknown language."""
    table = MESSAGES.get(lang, MESSAGES["en"])
    return table[key].format(**params) if params else table[key]
