"""PII detection. Regex + checksum based: fast, deterministic, no model needed."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Finding:
    type: str
    start: int
    end: int


def luhn_ok(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# Order matters: earlier detectors win when spans overlap (a card number is not a phone number).
_DETECTORS: list[tuple[str, re.Pattern, bool]] = [
    ("credit_card", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"), True),   # True = needs Luhn
    ("ssn", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"), False),
    ("api_key", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36})\b"), False),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), False),
    ("phone", re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"), False),
]


def find_pii(text: str, enabled: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for name, pattern, needs_luhn in _DETECTORS:
        if name not in enabled:
            continue
        for m in pattern.finditer(text):
            if needs_luhn and not luhn_ok(m.group()):
                continue
            if any(m.start() < f.end and f.start < m.end() for f in findings):
                continue
            findings.append(Finding(name, m.start(), m.end()))
    return sorted(findings, key=lambda f: f.start)


def redact(text: str, findings: list[Finding]) -> str:
    for f in sorted(findings, key=lambda f: f.start, reverse=True):
        text = text[: f.start] + f"[REDACTED_{f.type.upper()}]" + text[f.end :]
    return text
