"""Regex first filter: pull format and length instructions out of one message.

The detector is deliberately precision-first. A bare "5개" ("사과 5개로 나눠") or a
one-syllable Sino-Korean number without a relation word ("이 자료") is ignored,
because a wrong constraint is worse than a missed one.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from typing import Dict, FrozenSet, List, Optional, Tuple

from .numerals import is_sino_single, number_pattern, to_int
from .types import Constraint

__all__ = ["detect", "detect_release", "LENGTH_AXES", "SHAPE_AXES"]

LENGTH_AXES: Tuple[str, ...] = ("lines", "sentences", "chars", "chars_no_space", "words",
                                "items", "paragraphs", "table_rows")
SHAPE_AXES: Tuple[str, ...] = ("shape_table", "shape_list")

_NUM = number_pattern()

_REL_KO: Dict[str, str] = {"이내": "le", "이하": "le", "미만": "lt", "이상": "ge", "초과": "gt",
                           "내외": "approx", "정도": "approx", "안팎": "approx"}
_PRE_KO: Dict[str, str] = {"정확히": "eq", "딱": "eq", "최대": "le", "최소": "ge"}
_UNIT_KO: Dict[str, str] = {"줄": "lines", "문장": "sentences", "글자": "chars", "자": "chars",
                            "단어": "words", "항목": "items", "포인트": "items", "불릿": "items",
                            "글머리": "items", "가지": "items", "문단": "paragraphs",
                            "단락": "paragraphs", "행": "table_rows"}
_NOUNS_KO = "항목|포인트|불릿|글머리|문단|단락|문장|줄|단어"
_REL_KO_RE = "이내|이하|미만|이상|초과|내외|정도|안팎"
_PRE_KO_RE = "정확히|딱|최대|최소"
# A counter may be followed by a particle ("줄로"), but not by more Hangul ("자료", "자리").
_KO_END = r"(?=[^가-힣]|$|[로으짜만씩에의도는은이가을를])"
_KO_START = r"(?<![0-9A-Za-z.])"

_KO_A = re.compile(
    rf"{_KO_START}(?:(?P<pre>{_PRE_KO_RE})\s*)?(?P<num>{_NUM})\s*"
    rf"(?P<unit>글자|문장|단어|항목|포인트|불릿|글머리|문단|단락|가지|줄|자|행)"
    rf"(?:\s*(?P<rel>{_REL_KO_RE}))?{_KO_END}")
# "항목 5개로" -> the noun in front of "N개" decides the unit.
_KO_B = re.compile(
    rf"(?P<noun>{_NOUNS_KO})\s*(?:(?P<pre>{_PRE_KO_RE})\s*)?(?P<num>{_NUM})\s*개"
    rf"(?:\s*(?P<rel>{_REL_KO_RE}))?{_KO_END}")
# "2개 문단으로" / "5개의 항목" -> the noun after "N개" decides the unit.
_KO_C = re.compile(
    rf"{_KO_START}(?:(?P<pre>{_PRE_KO_RE})\s*)?(?P<num>{_NUM})\s*개(?:의)?\s*(?P<noun>{_NOUNS_KO})"
    rf"(?:\s*(?P<rel>{_REL_KO_RE}))?{_KO_END}")
# "첫 3줄만 봐 줘", "50줄 넘는데": the number describes the material (code, log), not the
# answer the user wants. Drop those; "3줄로", "3줄 이내", "3줄만 써" stay.
_KO_OBJECT_AFTER = re.compile(r"\s*(?:(?:만|을|를)\s*)?(?:봐|보[고세아]|읽)|\s*(?:넘|짜리|에서|째)")
_KO_OBJECT_BEFORE = re.compile(r"(?:첫|마지막|처음|맨\s*앞|위|아래|앞|뒤)\s*$")
#: Largest value accepted as an instruction; bigger numbers are noise.
MAX_VALUE = 100_000
_KO_TABLE = re.compile(r"(?<![가-힣])(?:표|테이블)(?:로|\s*형식|\s*형태|\s*포맷|\s*모양)")
_KO_LIST = re.compile(r"(?:목록|리스트|글머리\s*기호|불릿|불렛)(?:으로|로|\s*형식|\s*형태)")

_EN_NUMS = r"\d{1,3}(?:,\d{3})+|\d+|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|fifty)"
_EN_PRE = {"no more than": "le", "at most": "le", "within": "le", "up to": "le",
           "maximum of": "le", "max of": "le", "a maximum of": "le",
           "under": "lt", "less than": "lt", "fewer than": "lt",
           "at least": "ge", "minimum of": "ge", "a minimum of": "ge", "more than": "gt",
           "exactly": "eq", "about": "approx", "around": "approx",
           "approximately": "approx", "roughly": "approx"}
_EN_UNIT = {"bullet point": "items", "bullet": "items", "sentence": "sentences", "character": "chars",
            "char": "chars", "word": "words", "line": "lines", "paragraph": "paragraphs",
            "item": "items", "point": "items", "row": "table_rows"}
_EN_A = re.compile(
    r"(?<![\w.-])(?:(?P<pre>" + "|".join(sorted(_EN_PRE, key=len, reverse=True)) + r")\s+)?"
    rf"(?P<num>{_EN_NUMS})[\s-]*"
    r"(?P<unit>bullet points?|bullets?|sentences?|characters?|chars?|words?|lines?|paragraphs?|items?|points?|rows?)"
    r"(?P<tail>\s+or\s+(?:fewer|less|more))?\b", re.I)
_EN_SINGLE = re.compile(r"\b(?:a\s+)?single\s+(?P<unit>sentence|line|paragraph|word)\b", re.I)
_EN_TABLE = re.compile(r"\b(?:(?:in|as|into)\s+(?:a\s+)?(?:markdown\s+)?table\b|table\s+format\b|tabular\b)", re.I)
_EN_LIST = re.compile(
    r"\bas\s+(?:a\s+)?(?:(?:bulleted|numbered|bullet)\s+)?list\b|\bbullet\s+points?\b|\b(?:in|as)\s+bullets?\b"
    r"|\bbulleted\s+list\b|\bnumbered\s+list\b", re.I)

_NO_SPACE = re.compile(r"공백\s*(?:을\s*)?(?:제외|빼고|없이)|띄어쓰기\s*(?:를\s*)?(?:제외|없이)|"
                       r"(?:excluding|without)\s+(?:white\s*)?spaces?|no\s+spaces|spaces?\s+excluded", re.I)
# Per-item instructions ("각 줄 30자") are out of scope for 0.1: drop them.
_PER_ITEM_BEFORE = re.compile(
    r"(?:각\s*(?:줄|문장|항목|문단|단락)\s*[은는이가]?|(?:줄|문장|항목|문단|단락)\s*(?:마다|당|별)|"
    r"(?:each|every|per)\s+[\w-]+)\s*$", re.I)

_RELEASE_LENGTH = re.compile(
    r"길게\s*(?:써|작성|답)|길이\s*(?:는\s*)?(?:상관\s*없|제한\s*없)|제한\s*없이|분량\s*(?:은\s*)?(?:상관\s*없|자유)|"
    r"no\s+(?:length\s+)?limits?|any\s+length|as\s+long\s+as\s+you\s+(?:like|want)|"
    r"without\s+(?:a\s+)?(?:length\s+)?limit|length\s+(?:doesn.t|does\s+not)\s+matter", re.I)
_RELEASE_FORMAT = re.compile(
    r"형식\s*(?:은\s*)?(?:상관\s*없|자유)|아무\s*형식|자유\s*형식|any\s+format|free\s*-?\s*form|"
    r"format\s+(?:doesn.t|does\s+not)\s+matter", re.I)
_RELEASE_ALL = re.compile(
    r"(?:모든\s*)?(?:제약|형식\s*지시|지시)\s*(?:을\s*|는\s*)?(?:모두\s*)?(?:해제|무시|취소)|"
    r"(?:forget|ignore)\s+(?:the\s+)?(?:previous\s+)?(?:format|constraints?)", re.I)


def _op_from(pre: Optional[str], rel: Optional[str], table: Dict[str, str]) -> str:
    if rel:
        return _REL_KO[rel]
    if pre:
        return table[pre.lower()]
    return "le"  # "세 줄로" is read as an upper bound: most complaints are about overshooting


def detect_release(text: str) -> FrozenSet[str]:
    """Return the axes the user released ("길게 써도 돼", "no limit", "any format")."""
    axes: set = set()
    if _RELEASE_ALL.search(text):
        axes.update(LENGTH_AXES + SHAPE_AXES)
    if _RELEASE_FORMAT.search(text):
        axes.update(SHAPE_AXES)
    stripped = _RELEASE_FORMAT.sub(" ", text)
    if _RELEASE_LENGTH.search(stripped):
        axes.update(LENGTH_AXES)
    return frozenset(axes)


def detect(text: str, *, turn: int = 0) -> List[Constraint]:
    """Pull format and length constraints out of one message (regex only, deterministic)."""
    if not isinstance(text, str):
        raise TypeError(f"detect() expects a str, got {type(text).__name__}; "
                        "pass the message text, not the message dict")
    # (start, end, axis, op, value, unit_text)
    found: List[Tuple[int, int, str, str, int, str]] = []

    def add_num(m: "re.Match[str]", axis: str, op: str, token: str) -> None:
        value = to_int(token)
        if value is None or value <= 0 or value > MAX_VALUE:
            return
        if _PER_ITEM_BEFORE.search(text[max(0, m.start() - 14):m.start()]):
            return
        found.append((m.start(), m.end(), axis, op, value, m.group(0).strip()))

    for m in _KO_A.finditer(text):
        token = m.group("num")
        if not m.group("rel") and (_KO_OBJECT_AFTER.match(text, m.end())
                                   or _KO_OBJECT_BEFORE.search(text[max(0, m.start() - 6):m.start()])):
            continue  # describes the material, not the answer
        if is_sino_single(token) and not (m.group("rel") or m.group("pre")):
            continue  # "이 자료": a lone Sino-Korean syllable is only a number when a relation follows
        add_num(m, _UNIT_KO[m.group("unit")], _op_from(m.group("pre"), m.group("rel"), _PRE_KO), token)
    for pattern in (_KO_B, _KO_C):
        for m in pattern.finditer(text):
            token = m.group("num")
            if is_sino_single(token) and not (m.group("rel") or m.group("pre")):
                continue
            add_num(m, _UNIT_KO[m.group("noun")], _op_from(m.group("pre"), m.group("rel"), _PRE_KO), token)
    for m in _KO_TABLE.finditer(text):
        found.append((m.start(), m.end(), "shape_table", "eq", 1, m.group(0)))
    for m in _KO_LIST.finditer(text):
        found.append((m.start(), m.end(), "shape_list", "eq", 1, m.group(0)))

    for m in _EN_A.finditer(text):
        unit = m.group("unit").lower()
        unit = unit[:-1] if unit.endswith("s") and unit != "bullet points" else unit
        unit = "bullet point" if unit.startswith("bullet point") else unit
        axis = _EN_UNIT[unit]
        tail = (m.group("tail") or "").strip().lower()
        if m.group("pre"):
            op = _EN_PRE[m.group("pre").lower()]
        elif tail.endswith("more"):
            op = "ge"
        else:
            op = "le"
        add_num(m, axis, op, m.group("num"))
    for m in _EN_SINGLE.finditer(text):
        found.append((m.start(), m.end(), _EN_UNIT[m.group("unit").lower()], "le", 1, m.group(0)))
    for m in _EN_TABLE.finditer(text):
        found.append((m.start(), m.end(), "shape_table", "eq", 1, m.group(0)))
    for m in _EN_LIST.finditer(text):
        found.append((m.start(), m.end(), "shape_list", "eq", 1, m.group(0)))

    # Overlapping matches describe the same words: keep the longest one only.
    # `kept` stays sorted by start and non-overlapping, so only the two neighbours of a
    # candidate can collide with it (O(n log n) instead of O(n^2)).
    found.sort(key=lambda f: (-(f[1] - f[0]), f[0]))
    kept: List[Tuple[int, int, str, str, int, str]] = []
    starts: List[int] = []
    for cand in found:
        i = bisect_left(starts, cand[0])
        if i > 0 and kept[i - 1][1] > cand[0]:
            continue
        if i < len(kept) and kept[i][0] < cand[1]:
            continue
        kept.insert(i, cand)
        starts.insert(i, cand[0])

    no_space = bool(_NO_SPACE.search(text))
    out: List[Constraint] = []
    for start, end, axis, op, value, unit_text in kept:
        if axis in ("chars", "chars_no_space"):
            axis = "chars_no_space" if no_space else "chars"
        out.append(Constraint(axis=axis, op=op, value=value, unit_text=unit_text,
                              span=(start, end), turn=turn))
    return out
