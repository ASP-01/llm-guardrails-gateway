import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "evals" / "dataset.jsonl"


def test_dataset_is_well_formed():
    rows = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) >= 150
    assert {r["label"] for r in rows} == {"attack", "benign"}
    assert len({r["id"] for r in rows}) == len(rows)


def test_eval_runs_and_meets_floor(tmp_path):
    out = tmp_path / "results.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "run_eval.py"),
         "--min-recall", "0.9", "--max-fpr", "0.05", "--out", str(out)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    res = json.loads(out.read_text())
    assert res["attack_detection_excl_paraphrased"] >= 0.9
    assert res["false_positive_rate_plain"] <= 0.05
