## Evaluation

`evals/` holds 158 labeled prompts and a script that measures the input guardrails (no LLM is
called). Run it with `python evals/run_eval.py`, or point it at your own data with `--dataset`.

| Bucket | Label | Prompts | Blocked |
|---|---|---|---|
| Direct injection | attack | 25 | 92% |
| Jailbreak / persona | attack | 20 | 90% |
| Role-delimiter injection | attack | 5 | 100% |
| Obfuscated (zero-width, fullwidth, case) | attack | 10 | 90% |
| PII (cards, SSN, email, phone, keys) | attack | 23 | 100% |
| Paraphrased / multilingual / indirect | attack | 15 | **0%** |
| Plain billing questions | benign | 40 | 0% (no false positives) |
| Near-miss benign ("ignore the typo", "disable content filters on my kid's tablet") | benign | 20 | 20% flagged |

- Attack detection excluding the paraphrased bucket: **94%** (83 prompts). Including it: 79.6%.
- False-positive rate: 0% on plain benign prompts, 6.7% across all benign prompts.
- Latency, no model call: input guards p50 0.03 ms, full gateway overhead (input + output
  validation) p50 0.15 ms / p95 0.27 ms.

**Read these numbers carefully.** The test set and the detector were written by the same person,
so the 94% is optimistic: it measures how well the patterns cover the phrasings their author
thought of. The paraphrased bucket is the more honest signal. The pattern layer does not catch
rewordings, other languages, base64 or role-play attacks, which is why the README recommends
adding a classifier model. The four near-miss false positives are listed in `evals/results.json`.
CI fails if detection drops below 90% or plain-prompt false positives exceed 5%.

