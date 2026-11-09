"""Number words (Arabic digits, native Korean, Sino-Korean, English) to integers."""

from __future__ import annotations

from typing import Optional

#: Native Korean numerals that can stand in front of a counter ("세 줄", "열두 문장").
_NATIVE_UNITS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "석": 3, 
                 "네": 4, "넷": 4, "넉": 4, "다섯": 5, "여섯": 6, "일곱": 7,
                 "여덟": 8, "아홉": 9}
_NATIVE_TENS = {"열": 10, "스물": 20, "스무": 20, "서른": 30, "마흔": 40, "쉰": 50}
SINO_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_SINO_MULT = {"십": 10, "백": 100}
EN_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
              "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
              "twenty": 20, "thirty": 30, "fifty": 50}


def _native(token: str) -> Optional[int]:
    if token in _NATIVE_TENS:
        return _NATIVE_TENS[token]
    if token in _NATIVE_UNITS:
        return _NATIVE_UNITS[token]
    for tens, base in sorted(_NATIVE_TENS.items(), key=lambda kv: -len(kv[0])):
        if token.startswith(tens) and token[len(tens):] in _NATIVE_UNITS:
            return base + _NATIVE_UNITS[token[len(tens):]]
    return None


def _sino(token: str) -> Optional[int]:
    total, current = 0, 0
    for ch in token:
        if ch in SINO_DIGITS:
            current = SINO_DIGITS[ch]
        elif ch in _SINO_MULT:
            total += (current or 1) * _SINO_MULT[ch]
            current = 0
        else:
            return None
    return total + current


def to_int(token: str) -> Optional[int]:
    """Convert one number token to an int, or return None if it is not a number word."""
    token = token.strip()
    digits = token.replace(",", "")
    if digits.isdigit():
        # Absurdly long digit strings are not instructions (and would hit int()'s size limit).
        return int(digits) if len(digits) <= 12 else None
    low = token.lower()
    if low in EN_NUMBERS:
        return EN_NUMBERS[low]
    value = _native(token)
    if value is not None:
        return value
    return _sino(token)


def is_sino_single(token: str) -> bool:
    """True for a one-character Sino-Korean numeral such as "이" (too ambiguous alone)."""
    return len(token) == 1 and token in SINO_DIGITS


def number_pattern() -> str:
    """Regex source (no groups) that matches any number token this module understands."""
    tens = "|".join(sorted(_NATIVE_TENS, key=len, reverse=True))
    units = "|".join(sorted(_NATIVE_UNITS, key=len, reverse=True))
    english = "|".join(sorted(EN_NUMBERS, key=len, reverse=True))
    sino = "[일이삼사오육칠팔구십백]+"
    return rf"(?:\d{{1,3}}(?:,\d{{3}})+|\d+|(?:{tens})(?:{units})?|(?:{units})|{sino}|(?i:{english}))"
