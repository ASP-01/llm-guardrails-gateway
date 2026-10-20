from __future__ import annotations

import json
import logging

from .input_guards import check_input
from .output_guards import check_output
from .policy import Policy
from .providers import CORRECTION_MARKER, LLMProvider
from .types import Attempt, GatewayResult, Violation

log = logging.getLogger("guardrails_gateway")


class Gateway:
    """validate input -> call LLM -> validate output -> retry with correction -> safe fallback"""

    def __init__(self, policy: Policy, provider: LLMProvider):
        self.policy = policy
        self.provider = provider

    # Override in a subclass to plug in a real toxicity / topic classifier.
    def extra_output_checks(self, text: str) -> list[Violation]:
        return []

    def build_system_prompt(self) -> str:
        p = self.policy
        parts = [p.system_prompt.strip()]
        if p.rules:
            parts.append("You must follow these rules:\n" + "\n".join(f"- {r.description}" for r in p.rules))
        if p.output.format == "json":
            parts.append("Respond with ONLY a JSON object, no prose and no markdown.")
            if p.output.json_schema:
                parts.append("It must match this JSON schema:\n" + json.dumps(p.output.json_schema))
        return "\n\n".join(parts)

    @staticmethod
    def build_correction(violations: list[Violation]) -> str:
        reasons = "\n".join(f"- {v.message}" for v in violations)
        return (f"{CORRECTION_MARKER} Your previous response was rejected:\n{reasons}\n"
                "Answer my original request again and fix every issue above. "
                "Do not mention this notice.")

    def run(self, user_message: str, history: list[dict[str, str]] | None = None) -> GatewayResult:
        pol = self.policy
        clean, in_viol, redactions = check_input(user_message, pol)

        if in_viol:
            log.info("input blocked: %s", [v.rule_id for v in in_viol])
            return GatewayResult("blocked_input", pol.on_fail.blocked_input_message,
                                 input_violations=in_viol)

        system = self.build_system_prompt()
        base = list(history or []) + [{"role": "user", "content": clean}]
        messages = base
        attempts: list[Attempt] = []

        for n in range(1, pol.on_fail.max_retries + 2):
            try:
                raw = self.provider.complete(system, messages)
            except Exception:  # noqa: BLE001 - provider/network failures must not leak to callers
                log.exception("provider call failed")
                return GatewayResult("provider_error", pol.on_fail.fallback_message,
                                     attempts=attempts, redactions=redactions)

            violations, parsed = check_output(raw, pol)
            violations += self.extra_output_checks(raw)
            attempts.append(Attempt(n, violations))

            if not violations:
                return GatewayResult("ok", raw, parsed, attempts, redactions=redactions)

            log.info("attempt %d failed: %s", n, [v.rule_id for v in violations])
            # Don't echo the rejected answer back: it may be toxic or contain leaked data.
            messages = base + [
                {"role": "assistant", "content": "[previous response withheld]"},
                {"role": "user", "content": self.build_correction(violations)},
            ]

        return GatewayResult("fallback", pol.on_fail.fallback_message,
                             attempts=attempts, redactions=redactions)
