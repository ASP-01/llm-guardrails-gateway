"""One-time helper: adds the Evaluation section to README.md and the eval step to CI.
Safe to run twice. Run from the project root:  python apply_eval_update.py
"""
from pathlib import Path

root = Path(__file__).resolve().parent

readme = root / "README.md"
section = (root / "evals" / "README_section.md").read_text()
text = readme.read_text()
if "## Evaluation" in text:
    print("README already has an Evaluation section, skipped")
else:
    marker = "## Known limitations"
    if marker in text:
        text = text.replace(marker, section + marker, 1)
    else:
        text = text.rstrip("\n") + "\n\n" + section
    readme.write_text(text)
    print("README updated")

wf = root / ".github" / "workflows" / "tests.yml"
step = ("      - name: Guardrail eval (detection floor / false-positive ceiling)\n"
        "        run: python evals/run_eval.py --min-recall 0.9 --max-fpr 0.05\n")
if not wf.exists():
    print("workflow file not found, skipped CI step")
elif "evals/run_eval.py" in wf.read_text():
    print("CI already runs the eval, skipped")
else:
    wf.write_text(wf.read_text().rstrip("\n") + "\n" + step)
    print("CI workflow updated")
