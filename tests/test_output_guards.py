import json

from guardrails_gateway.output_guards import check_output


def ids(v):
    return {x.rule_id for x in v}


def test_valid_output_passes(policy, good_json):
    viol, parsed = check_output(good_json, policy)
    assert viol == [] and parsed["confidence"] == 0.9


def test_fenced_json_accepted(policy, good_json):
    viol, _ = check_output(f"```json\n{good_json}\n```", policy)
    assert viol == []


def test_not_json(policy):
    viol, _ = check_output("Sure, billing is in settings.", policy)
    assert "invalid-json" in ids(viol)


def test_missing_required_and_extra_field(policy):
    bad = json.dumps({"answer": "billing account", "sources": ["https://x.io"], "extra": 1})
    viol, _ = check_output(bad, policy)
    assert "schema-mismatch" in ids(viol)
    assert len([v for v in viol if v.rule_id == "schema-mismatch"]) >= 2


def test_empty_sources_fails(policy):
    bad = json.dumps({"answer": "billing account", "sources": [], "confidence": 0.5})
    assert "schema-mismatch" in ids(check_output(bad, policy)[0])


def test_competitor_blocked(policy):
    out = json.dumps({"answer": "Better billing than Globex", "sources": ["https://x.io"], "confidence": 1})
    assert "no-competitors" in ids(check_output(out, policy)[0])


def test_competitor_word_boundary(policy):
    out = json.dumps({"answer": "Your billing account is fine", "sources": ["https://x.io"], "confidence": 1})
    assert "no-competitors" not in ids(check_output(out, policy)[0])


def test_medical_advice_blocked(policy):
    out = json.dumps({"answer": "For your billing headache take 400 mg of ibuprofen",
                      "sources": ["https://x.io"], "confidence": 1})
    assert "no-medical-advice" in ids(check_output(out, policy)[0])


def test_citation_rule_is_independent_of_schema(policy):
    policy.output.json_schema = None
    out = json.dumps({"answer": "billing is in your account"})
    assert "cite-sources" in ids(check_output(out, policy)[0])


def test_toxic(policy):
    out = json.dumps({"answer": "billing account? You are an idiot", "sources": ["https://x.io"], "confidence": 1})
    assert "toxic-output" in ids(check_output(out, policy)[0])


def test_off_topic(policy):
    out = json.dumps({"answer": "The capital of France is Paris", "sources": ["https://x.io"], "confidence": 1})
    assert "off-topic" in ids(check_output(out, policy)[0])


def test_pii_leak_in_output(policy):
    out = json.dumps({"answer": "billing: card 4111 1111 1111 1111", "sources": ["https://x.io"], "confidence": 1})
    assert "pii-in-output" in ids(check_output(out, policy)[0])
