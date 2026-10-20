"""Applies the YAML `rules:` list to a piece of text."""
from __future__ import annotations

import re

from .policy import Rule
from .topics import BUILTIN_TOPICS
from .types import Violation


def apply_rules(text: str, rules: list[Rule], stage: str) -> list[Violation]:
    out: list[Violation] = []
    for rule in rules:
        if rule.applies_to not in (stage, "both"):
            continue

        if rule.type == "forbidden_terms":
            for term in rule.terms:
                if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                    out.append(Violation(rule.id, "policy", stage, rule.message or rule.description))
                    break

        elif rule.type == "require_pattern":
            if not re.search(rule.pattern, text, re.IGNORECASE):  # type: ignore[arg-type]
                out.append(Violation(rule.id, "policy", stage, rule.message or rule.description))

        elif rule.type == "blocked_topic":
            if any(p.search(text) for p in BUILTIN_TOPICS[rule.topic]):  # type: ignore[index]
                out.append(Violation(rule.id, "policy", stage, rule.message or rule.description))
    return out
