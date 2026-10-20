from __future__ import annotations

from .injection import injection_score
from .pii import find_pii, redact
from .policy import Policy
from .rules import apply_rules
from .types import Violation


def check_input(text: str, policy: Policy) -> tuple[str, list[Violation], list[str]]:
    """Returns (text_to_send_to_llm, violations, redacted_pii_types)."""
    cfg = policy.input
    violations: list[Violation] = []
    redactions: list[str] = []
    clean = text

    if len(text) > cfg.max_chars:
        violations.append(Violation("input-too-long", "length", "input",
                                    f"Message exceeds {cfg.max_chars} characters"))

    if cfg.injection.enabled:
        score, hits = injection_score(text)
        if score >= cfg.injection.threshold:
            violations.append(Violation(
                "prompt-injection", "injection", "input",
                f"Possible prompt injection or jailbreak (score {score}, signals: {', '.join(hits)})"))

    if cfg.pii.enabled:
        findings = find_pii(text, cfg.pii.detect)
        if findings:
            kinds = sorted({f.type for f in findings})
            if cfg.pii.action == "block":
                violations.append(Violation("pii-in-input", "pii", "input",
                                            f"Message contains sensitive data ({', '.join(kinds)})"))
            else:
                clean = redact(text, findings)
                redactions = kinds

    violations += apply_rules(text, policy.rules, "input")
    return clean, violations, redactions
