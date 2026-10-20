from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import Draft202012Validator

from .pii import find_pii
from .policy import Policy
from .rules import apply_rules
from .types import Violation

_F = re.IGNORECASE

# Small built-in baseline. Extend via policy `toxicity.extra_patterns`, or swap in a real
# classifier by subclassing Gateway and overriding `extra_output_checks`.
_TOXIC = [
    re.compile(r"\b(?:kill|hurt)\s+yourself\b", _F),
    re.compile(r"\byou(?:'re|\s+are)\s+(?:an?\s+)?(?:idiot|moron|stupid|worthless|pathetic)\b", _F),
    re.compile(r"\b(?:shut\s+up|go\s+to\s+hell|i\s+hate\s+you)\b", _F),
    re.compile(r"\bi(?:'ll|\s+will)\s+(?:kill|hurt|destroy)\s+you\b", _F),
]

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_json(text: str) -> Any:
    m = _FENCE.match(text)
    return json.loads(m.group(1) if m else text)


def check_output(text: str, policy: Policy) -> tuple[list[Violation], Any]:
    cfg = policy.output
    violations: list[Violation] = []
    parsed: Any = None

    if len(text) > cfg.max_chars:
        violations.append(Violation("output-too-long", "length", "output",
                                    f"Response exceeds {cfg.max_chars} characters"))

    if cfg.format == "json":
        try:
            parsed = parse_json(text)
        except (json.JSONDecodeError, ValueError) as e:
            violations.append(Violation("invalid-json", "schema", "output",
                                        f"Response is not valid JSON ({e}). Return only a JSON object."))
        else:
            if cfg.json_schema:
                errors = sorted(Draft202012Validator(cfg.json_schema).iter_errors(parsed),
                                key=lambda e: list(e.path))
                for err in errors[:5]:
                    where = "/".join(str(p) for p in err.path) or "(root)"
                    violations.append(Violation("schema-mismatch", "schema", "output",
                                                f"JSON schema error at {where}: {err.message}"))

    if cfg.toxicity.enabled:
        patterns = _TOXIC + [re.compile(p, _F) for p in cfg.toxicity.extra_patterns]
        if any(p.search(text) for p in patterns):
            violations.append(Violation("toxic-output", "toxicity", "output",
                                        "Response contains toxic or abusive language"))

    if cfg.block_pii_leak and find_pii(text, ["credit_card", "ssn", "api_key"]):
        violations.append(Violation("pii-in-output", "pii", "output",
                                    "Response contains sensitive data (card, SSN or API key)"))

    if cfg.on_topic.enabled and cfg.on_topic.topics:
        lowered = text.lower()
        matched = {kw for kws in cfg.on_topic.topics.values() for kw in kws if kw.lower() in lowered}
        if len(matched) < cfg.on_topic.min_matches:
            allowed = ", ".join(cfg.on_topic.topics)
            violations.append(Violation("off-topic", "topic", "output",
                                        f"Response is off-topic. Stay within: {allowed}"))

    violations += apply_rules(text, policy.rules, "output")
    return violations, parsed
