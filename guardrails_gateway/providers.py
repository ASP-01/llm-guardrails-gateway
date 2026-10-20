"""LLM provider adapters. The gateway only needs one method: complete(system, messages)."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod

CORRECTION_MARKER = "[GATEWAY CORRECTION]"


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, messages: list[dict[str, str]]) -> str: ...


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None, max_tokens: int = 1024):
        import anthropic  # lazy: only needed when a real key is used

        self.client = anthropic.Anthropic()
        self.model = model or os.getenv("GATEWAY_MODEL", "claude-sonnet-5-5")
        self.max_tokens = max_tokens

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        resp = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system, messages=messages)
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


class ScriptedProvider(LLMProvider):
    """Returns canned responses in order. Used in tests."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        self.calls.append((system, messages))
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


class DemoProvider(LLMProvider):
    """Offline stand-in so the project runs with no API key.

    It deliberately misbehaves on the first try for certain trigger words, then behaves once
    the gateway sends a correction. That makes the retry loop visible in the demo.
    """

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        corrected = messages[-1]["content"].startswith(CORRECTION_MARKER)
        original = next((m["content"] for m in messages
                         if m["role"] == "user" and not m["content"].startswith(CORRECTION_MARKER)), "")
        q = original.lower()

        def reply(answer: str, sources=("https://docs.example.com/help",)) -> str:
            return json.dumps({"answer": answer, "sources": list(sources), "confidence": 0.8})

        good = reply("For billing questions, check the Billing tab under your account settings.")
        if corrected:
            return good
        if "competitor" in q:
            return reply("Our billing is cheaper than Globex, and your account setup is simpler too.")
        if "headache" in q or "medical" in q:
            return reply("For billing stress headaches you should take 400 mg of ibuprofen.")
        if "plain text" in q:
            return "Sure! Billing is handled in your account settings."
        if "unsourced" in q:
            return reply("Your billing account can be updated in settings.", sources=())
        return good
