import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails_gateway.policy import Policy  # noqa: E402

POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "default.yaml"


@pytest.fixture
def policy():
    return Policy.from_yaml(POLICY_PATH)


@pytest.fixture
def good_json():
    return json.dumps({"answer": "Your billing account is under settings.",
                       "sources": ["https://docs.example.com/a"], "confidence": 0.9})
