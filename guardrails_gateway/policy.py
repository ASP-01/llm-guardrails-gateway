"""Policy model + YAML loader. This is the file non-engineers edit."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .topics import BUILTIN_TOPICS

DEFAULT_PII = ["credit_card", "ssn", "email", "phone", "api_key"]


class InjectionConfig(BaseModel):
    enabled: bool = True
    threshold: float = Field(0.6, ge=0, le=1)


class PIIConfig(BaseModel):
    enabled: bool = True
    action: Literal["block", "redact"] = "block"
    detect: list[str] = Field(default_factory=lambda: list(DEFAULT_PII))


class InputConfig(BaseModel):
    max_chars: int = 8000
    injection: InjectionConfig = InjectionConfig()
    pii: PIIConfig = PIIConfig()


class ToxicityConfig(BaseModel):
    enabled: bool = True
    extra_patterns: list[str] = Field(default_factory=list)


class OnTopicConfig(BaseModel):
    enabled: bool = False
    min_matches: int = 1
    topics: dict[str, list[str]] = Field(default_factory=dict)


class OutputConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    format: Literal["text", "json"] = "text"
    json_schema: dict[str, Any] | None = Field(None, alias="schema")
    max_chars: int = 8000
    toxicity: ToxicityConfig = ToxicityConfig()
    on_topic: OnTopicConfig = OnTopicConfig()
    block_pii_leak: bool = True


class Rule(BaseModel):
    id: str
    description: str
    type: Literal["forbidden_terms", "require_pattern", "blocked_topic"]
    applies_to: Literal["input", "output", "both"] = "output"
    terms: list[str] = Field(default_factory=list)
    pattern: str | None = None
    topic: str | None = None
    message: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "Rule":
        if self.type == "forbidden_terms" and not self.terms:
            raise ValueError(f"rule '{self.id}': forbidden_terms needs a non-empty 'terms' list")
        if self.type == "require_pattern":
            if not self.pattern:
                raise ValueError(f"rule '{self.id}': require_pattern needs 'pattern'")
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"rule '{self.id}': bad regex: {e}") from e
        if self.type == "blocked_topic" and self.topic not in BUILTIN_TOPICS:
            raise ValueError(
                f"rule '{self.id}': unknown topic '{self.topic}'. Available: {sorted(BUILTIN_TOPICS)}"
            )
        return self


class FailureConfig(BaseModel):
    max_retries: int = Field(2, ge=0, le=5)
    fallback_message: str = "Sorry, I can't help with that request."
    blocked_input_message: str = "Your message was blocked by our safety policy."


class Policy(BaseModel):
    version: int = 1
    name: str = "default"
    system_prompt: str = "You are a helpful assistant."
    input: InputConfig = InputConfig()
    output: OutputConfig = OutputConfig()
    rules: list[Rule] = Field(default_factory=list)
    on_fail: FailureConfig = FailureConfig()

    @model_validator(mode="after")
    def _unique_ids(self) -> "Policy":
        ids = [r.id for r in self.rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate rule ids: {sorted(dupes)}")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Policy":
        data = yaml.safe_load(Path(path).read_text()) or {}
        return cls.model_validate(data)
