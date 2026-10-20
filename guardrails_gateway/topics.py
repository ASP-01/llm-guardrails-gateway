"""Built-in topic detectors a policy author can reference by name (blocked_topic rules)."""
import re

_F = re.IGNORECASE

BUILTIN_TOPICS: dict[str, list[re.Pattern]] = {
    "medical_advice": [
        re.compile(r"\byou\s+should\s+(?:take|stop\s+taking|start\s+taking|increase|reduce)\b", _F),
        re.compile(r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|ml)\b", _F),
        re.compile(r"\b(?:dosage|dose)\s+(?:of|for)\b", _F),
        re.compile(r"\bdiagnos(?:e|es|ed|is)\b", _F),
        re.compile(r"\b(?:prescri(?:be|bed|ption)|antibiotics?|ibuprofen|acetaminophen|painkillers?)\b", _F),
        re.compile(r"\b(?:treatment\s+for|symptoms?\s+of)\b", _F),
    ],
    "legal_advice": [
        re.compile(r"\byou\s+(?:should|must)\s+(?:sue|file\s+a\s+(?:lawsuit|claim))\b", _F),
        re.compile(r"\b(?:legally\s+(?:entitled|liable)|statute\s+of\s+limitations)\b", _F),
        re.compile(r"\bthis\s+constitutes\s+(?:fraud|negligence|breach)\b", _F),
    ],
    "financial_advice": [
        re.compile(r"\byou\s+should\s+(?:buy|sell|invest\s+in|short)\b", _F),
        re.compile(r"\bguaranteed\s+returns?\b", _F),
        re.compile(r"\b(?:price\s+target|can't\s+lose)\b", _F),
    ],
}
