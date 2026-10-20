"""Measures how well the input guardrails separate attacks from normal messages.

    python evals/run_eval.py                       # default dataset + default policy
    python evals/run_eval.py --dataset my.jsonl    # your own labeled prompts
    python evals/run_eval.py --min-recall 0.9 --max-fpr 0.1   # exit 1 if below/above (for CI)

No LLM is called. This evaluates the guardrail layer only.
Dataset format (JSONL): {"id": "...", "bucket": "...", "label": "attack" | "benign", "text": "..."}
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from guardrails_gateway import Gateway, Policy, ScriptedProvider  # noqa: E402
from guardrails_gateway.input_guards import check_input  # noqa: E402

GOOD_REPLY = json.dumps({"answer": "Check the billing tab in your account settings.",
                         "sources": ["https://docs.example.com/help"], "confidence": 0.9})


def pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def percentile(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(ROOT / "evals" / "dataset.jsonl"))
    ap.add_argument("--policy", default=str(ROOT / "policies" / "default.yaml"))
    ap.add_argument("--out", default=str(ROOT / "evals" / "results.json"))
    ap.add_argument("--min-recall", type=float, default=None,
                    help="fail if attack detection on the non-hard buckets is below this")
    ap.add_argument("--max-fpr", type=float, default=None,
                    help="fail if false-positive rate on plain benign prompts exceeds this")
    args = ap.parse_args()

    policy = Policy.from_yaml(args.policy)
    rows = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]

    # --- classification ---------------------------------------------------------------
    per_bucket: dict[str, dict] = defaultdict(lambda: {"n": 0, "blocked": 0, "label": "", "missed": [], "flagged": []})
    for r in rows:
        _, violations, _ = check_input(r["text"], policy)
        blocked = bool(violations)
        b = per_bucket[r["bucket"]]
        b["label"] = r["label"]
        b["n"] += 1
        b["blocked"] += blocked
        if r["label"] == "attack" and not blocked:
            b["missed"].append(r["text"])
        if r["label"] == "benign" and blocked:
            b["flagged"].append({"text": r["text"], "why": [v.rule_id for v in violations]})

    attack_b = {k: v for k, v in per_bucket.items() if v["label"] == "attack"}
    benign_b = {k: v for k, v in per_bucket.items() if v["label"] == "benign"}
    hard = {"paraphrased_hard"}

    def rate(buckets, key):
        n = sum(b["n"] for b in buckets.values())
        return (sum(b[key] for b in buckets.values()) / n) if n else float("nan"), n

    core_attacks = {k: v for k, v in attack_b.items() if k not in hard}
    recall_all, n_attack = rate(attack_b, "blocked")
    recall_core, n_core = rate(core_attacks, "blocked")
    fpr_all, n_benign = rate(benign_b, "blocked")
    fpr_plain, n_plain = rate({"benign": benign_b.get("benign", {"n": 0, "blocked": 0})}, "blocked")
    fpr_hard, n_hardb = rate({"benign_hard": benign_b.get("benign_hard", {"n": 0, "blocked": 0})}, "blocked")

    tp = sum(b["blocked"] for b in attack_b.values())
    fp = sum(b["blocked"] for b in benign_b.values())
    precision = tp / (tp + fp) if (tp + fp) else float("nan")

    # --- latency ----------------------------------------------------------------------
    texts = [r["text"] for r in rows]
    guard_ms = []
    for t in texts:
        runs = []
        for _ in range(30):
            t0 = time.perf_counter()
            check_input(t, policy)
            runs.append((time.perf_counter() - t0) * 1000)
        guard_ms.append(statistics.median(runs))

    # Full gateway round trip with an instant fake model: everything left over is overhead.
    gw = Gateway(policy, ScriptedProvider([GOOD_REPLY]))
    benign_texts = [r["text"] for r in rows if r["label"] == "benign"]
    e2e_ms = []
    for t in benign_texts:
        for _ in range(10):
            t0 = time.perf_counter()
            gw.run(t)
            e2e_ms.append((time.perf_counter() - t0) * 1000)

    # --- report -----------------------------------------------------------------------
    print(f"\nDataset: {len(rows)} prompts  ({n_attack} attack, {n_benign} benign)   Policy: {policy.name}\n")
    print(f"{'bucket':20s} {'label':7s} {'n':>3s} {'blocked':>8s}  rate")
    for name, b in per_bucket.items():
        print(f"{name:20s} {b['label']:7s} {b['n']:3d} {b['blocked']:8d}  {pct(b['blocked'] / b['n'])}")

    print("\nSummary")
    print(f"  Attack detection, all attack buckets      {pct(recall_all)}  ({n_attack} prompts)")
    print(f"  Attack detection, excluding paraphrased   {pct(recall_core)}  ({n_core} prompts)")
    print(f"  False-positive rate, plain benign         {pct(fpr_plain)}  ({n_plain} prompts)")
    print(f"  False-positive rate, near-miss benign     {pct(fpr_hard)}  ({n_hardb} prompts)")
    print(f"  False-positive rate, all benign           {pct(fpr_all)}  ({n_benign} prompts)")
    print(f"  Precision                                 {pct(precision)}")
    print("\nLatency (no model call)")
    print(f"  Input guards only      p50 {percentile(guard_ms, .5):.3f} ms   p95 {percentile(guard_ms, .95):.3f} ms")
    print(f"  Full gateway overhead  p50 {percentile(e2e_ms, .5):.3f} ms   p95 {percentile(e2e_ms, .95):.3f} ms"
          "  (input + output validation, instant fake model)")

    print("\nMissed attacks")
    for name, b in attack_b.items():
        for t in b["missed"]:
            print(f"  [{name}] {t[:100]!r}")
    print("\nFalse positives")
    for name, b in benign_b.items():
        for f in b["flagged"]:
            print(f"  [{name}] {f['text'][:100]!r}  -> {f['why']}")

    result = {
        "n_prompts": len(rows), "n_attack": n_attack, "n_benign": n_benign,
        "attack_detection_all": recall_all, "attack_detection_excl_paraphrased": recall_core,
        "false_positive_rate_plain": fpr_plain, "false_positive_rate_near_miss": fpr_hard,
        "false_positive_rate_all": fpr_all, "precision": precision,
        "latency_ms": {"guards_p50": percentile(guard_ms, .5), "guards_p95": percentile(guard_ms, .95),
                       "gateway_p50": percentile(e2e_ms, .5), "gateway_p95": percentile(e2e_ms, .95)},
        "buckets": {k: {"label": v["label"], "n": v["n"], "blocked": v["blocked"],
                        "missed": v["missed"], "false_positives": v["flagged"]} for k, v in per_bucket.items()},
    }
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {args.out}")

    failed = False
    if args.min_recall is not None and recall_core < args.min_recall:
        print(f"FAIL: attack detection {pct(recall_core)} < {pct(args.min_recall)}")
        failed = True
    if args.max_fpr is not None and fpr_plain > args.max_fpr:
        print(f"FAIL: false-positive rate {pct(fpr_plain)} > {pct(args.max_fpr)}")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
