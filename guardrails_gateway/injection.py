"""Heuristic prompt-injection / jailbreak scoring.

Each matched pattern carries a weight; the final score is 1 - prod(1 - w), so one strong
signal trips the threshold alone while several weak signals can add up.
This is a baseline. See README for how to layer a classifier model on top.
"""
from __future__ import annotations

import re
import unicodedata

_F = re.IGNORECASE

_PATTERNS: list[tuple[str, re.Pattern, float]] = [
    ("ignore-previous", re.compile(r"ignore\s+(?:all\s+|any\s+|the\s+|your\s+)?(?:previous|prior|above|earlier|preceding)\s+(?:instructions|prompts?|rules|directions)", _F), 0.9),
    ("disregard-rules", re.compile(r"disregard\s+(?:all\s+|any\s+|the\s+|your\s+)?(?:previous\s+|prior\s+|system\s+|earlier\s+)?(?:instructions|prompt|rules|guidelines)", _F), 0.85),
    ("reveal-system-prompt", re.compile(r"(?:reveal|show|print|repeat|output|leak)\s+(?:me\s+)?(?:your|the)\s+(?:system|hidden|initial|original)\s+(?:prompt|instructions|message)", _F), 0.8),
    ("persona-switch", re.compile(r"you\s+are\s+now\s+(?:in\s+)?(?:dan|developer\s+mode|jailbroken|unrestricted|an?\s+unfiltered)", _F), 0.85),
    ("dan", re.compile(r"\bdo\s+anything\s+now\b", _F), 0.8),
    ("privileged-mode", re.compile(r"\b(?:developer|god|sudo|admin)\s+mode\b", _F), 0.5),
    ("no-restrictions", re.compile(r"pretend\s+(?:that\s+)?you\s+(?:have\s+no|are\s+not\s+bound\s+by)\s+(?:any\s+)?(?:restrictions|rules|limits|filters|guidelines)", _F), 0.8),
    ("bypass-safety", re.compile(r"(?:without|bypass|circumvent|disable)\s+(?:any\s+|all\s+|your\s+)?(?:safety|content|ethical)\s+(?:filters?|guidelines|restrictions|policies|checks)", _F), 0.7),
    ("role-delimiter", re.compile(r"</?\s*(?:system|assistant|im_start|im_end)\s*>|\[/?INST\]|<\|im_(?:start|end)\|>", _F), 0.7),
    ("new-instructions", re.compile(r"new\s+instructions?\s*:", _F), 0.5),
    ("from-now-on", re.compile(r"from\s+now\s+on,?\s+(?:you|ignore|act)", _F), 0.4),
    ("jailbreak-word", re.compile(r"\bjailbreak(?:ing|s)?\b", _F), 0.4),
]

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)


def normalize(text: str) -> str:
    """Defeat trivial obfuscation: fullwidth chars, zero-width joiners, odd whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    return re.sub(r"\s+", " ", text)


def injection_score(text: str) -> tuple[float, list[str]]:
    norm = normalize(text)
    hits: list[str] = []
    keep = 1.0
    for name, pattern, weight in _PATTERNS:
        if pattern.search(norm):
            hits.append(name)
            keep *= 1 - weight
    return round(1 - keep, 3), hits
