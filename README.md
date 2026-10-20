# LLM Guardrails Gateway

![tests](https://github.com/ASP-01/llm-guardrails-gateway/actions/workflows/tests.yml/badge.svg)

Middleware that sits between your users and any LLM. It checks what goes in, checks what
comes out, retries with a correction when the model misbehaves, and returns a safe fallback
when it can't be fixed. The rules live in a YAML file that non-engineers can edit.

```
user ──► input guards ──► LLM ──► output guards ──► user
         │ injection       ▲        │ JSON schema
         │ jailbreak       │        │ toxicity
         │ PII             │        │ on-topic
         │ business rules  │        │ PII leak, business rules
         ▼                 │        ▼
      blocked          retry with correction (max N) ──► safe fallback
```

## Quick start

```bash
pip install -r requirements.txt
python examples/demo.py                     # no API key needed (uses an offline demo model)
pytest -q                                   # 48 tests
uvicorn guardrails_gateway.app:app --reload # API on :8000
```

To use a real model, set `ANTHROPIC_API_KEY` (optionally `GATEWAY_MODEL`). Without a key the
API runs against the offline `DemoProvider`.

```bash
curl -s localhost:8000/v1/chat -H 'content-type: application/json' \
  -d '{"message": "Is your competitor cheaper?"}' | python -m json.tool
```

## How it behaves

| Situation | What happens |
|---|---|
| Prompt injection / jailbreak in the user message | Blocked before the LLM is called |
| Credit card, SSN, email, phone or API key in the user message | Blocked, or redacted before sending (`pii.action`) |
| Model output fails schema, tone, topic or a business rule | Retried up to `max_retries` times with a correction message listing what was wrong |
| Still failing after retries | `fallback_message` returned, `status: "fallback"` |
| Provider/network error | `fallback_message` returned, `status: "provider_error"` |

Every response includes `status`, per-attempt `violations` and `redactions`, so you get an audit
trail without logging raw user data. The rejected model answer is never fed back into the retry
prompt, since it might contain toxic text or leaked data.

## The policy file

`policies/default.yaml` is commented for non-engineers. The three business rules from the brief:

```yaml
rules:
  - id: no-competitors
    description: Never discuss competitors.
    type: forbidden_terms
    terms: [Globex, Initech]

  - id: cite-sources
    description: Always cite sources with a link.
    type: require_pattern
    pattern: "https?://"

  - id: no-medical-advice
    description: Never give medical advice.
    type: blocked_topic
    topic: medical_advice      # also: legal_advice, financial_advice
```

Rule `description`s are also injected into the system prompt, so the model is told the rules up
front and the guards only have to catch the misses. Policies are validated on load (bad regex,
unknown topic, duplicate ids), and the API hot-reloads the file when it changes. If someone saves
a broken edit, the last good policy keeps running.

## Layout

```
guardrails_gateway/
  policy.py         YAML schema + validation (pydantic)
  input_guards.py   injection, PII, length, input rules
  injection.py      weighted pattern scoring + unicode normalization
  pii.py            regex + Luhn checksum detectors, redaction
  output_guards.py  JSON/schema, toxicity, PII leak, on-topic, output rules
  rules.py          applies YAML rules
  topics.py         built-in blocked-topic detectors
  gateway.py        orchestration: validate -> call -> validate -> retry -> fallback
  providers.py      Anthropic, Demo (offline), Scripted (tests)
  app.py            FastAPI service with policy hot-reload
tests/              48 tests
```

## Known limitations (read before using in production)

This is a solid, tested baseline, not a complete safety system.

- **Injection and jailbreak detection is heuristic.** It catches common phrasings and basic
  obfuscation (zero-width characters, fullwidth text) but not paraphrased or multilingual attacks.
  Put a classifier model in front for real traffic.
- **Toxicity and topic checks are keyword-based.** The topic check is crude (keyword overlap) and
  the toxicity list is small. Use `Gateway.extra_output_checks()` to plug in a moderation model or
  embedding similarity.
- **PII coverage is US-centric** (SSN, US phone format). Add detectors in `pii.py` or swap in
  Microsoft Presidio.
- **No streaming support**: output has to be complete before it can be validated.
- Retries cost extra latency and tokens. Keep `max_retries` low.

## Ideas for extending it

- Measure it: build a labeled set of attack and benign prompts and report detection rate and
  false-positive rate. Those are the numbers worth putting on a resume.
- Add per-request latency and retry-rate metrics (Prometheus) to show guardrail overhead.
- Per-tenant policies selected by API key.

## Example responses

These are real responses from `POST /v1/chat` using the offline demo model and the default policy.

**Model breaks a rule, gateway retries.** The first answer mentioned a competitor, so it was rejected and the model was asked again. Attempt 2 passed.

```bash
curl -s localhost:8000/v1/chat -H 'content-type: application/json' \
  -d '{"message": "Is your competitor cheaper?"}'
```

```json
{
  "status": "ok",
  "attempts": [
    {
      "number": 1,
      "violations": [
        {
          "rule_id": "no-competitors",
          "category": "policy",
          "stage": "output",
          "message": "Do not mention or compare against competitors."
        }
      ]
    },
    { "number": 2, "violations": [] }
  ],
  "input_violations": [],
  "redactions": []
}
```

**Prompt injection is blocked before the model is called.** `attempts` is empty because the LLM was never reached.

```json
{
  "status": "blocked_input",
  "content": "I can't process that message. Please rephrase it without sensitive details and try again.",
  "attempts": [],
  "input_violations": [
    {
      "rule_id": "prompt-injection",
      "category": "injection",
      "stage": "input",
      "message": "Possible prompt injection or jailbreak (score 0.98, signals: ignore-previous, reveal-system-prompt)"
    }
  ]
}
```

**A pasted credit card number is blocked.**

```json
{
  "status": "blocked_input",
  "content": "I can't process that message. Please rephrase it without sensitive details and try again.",
  "attempts": [],
  "input_violations": [
    {
      "rule_id": "pii-in-input",
      "category": "pii",
      "stage": "input",
      "message": "Message contains sensitive data (credit_card)"
    }
  ]
}
```
