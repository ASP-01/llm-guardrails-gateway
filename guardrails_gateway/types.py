from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class Violation:
    rule_id: str
    category: str   # injection | pii | toxicity | schema | topic | policy | length
    stage: str      # input | output
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class Attempt:
    number: int
    violations: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"number": self.number, "violations": [v.to_dict() for v in self.violations]}


@dataclass
class GatewayResult:
    status: str                      # ok | blocked_input | fallback | provider_error
    content: str                     # what the caller should show the user
    parsed: Any = None               # parsed JSON when output.format == "json"
    attempts: list[Attempt] = field(default_factory=list)
    input_violations: list[Violation] = field(default_factory=list)
    redactions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "content": self.content,
            "parsed": self.parsed,
            "attempts": [a.to_dict() for a in self.attempts],
            "input_violations": [v.to_dict() for v in self.input_violations],
            "redactions": self.redactions,
        }
