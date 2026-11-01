"""Generate a self-contained, offline demo from the Python engine's reports."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from satotag import analyze  # noqa: E402
from tools.evidence_demo import build_examples as evidence_examples
from tools.governance_demo import build_examples  # noqa: E402


def build():
    reports = [analyze(json.loads((ROOT / "examples" / f"{key}.json").read_text()))
               for key in ("split", "mixed", "dust", "revoked")]
    payload = json.dumps(reports, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    template = (ROOT / "tools" / "demo_template.html").read_text()
    governance = json.dumps(build_examples(), ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    evidence = json.dumps(evidence_examples()["scenarios"], ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    template = template.replace("__SATOTAG_EVIDENCE__", evidence)
    return template.replace("__SATOTAG_REPORTS__", payload).replace("__SATOTAG_GOVERNANCE__", governance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the committed demo is stale")
    args = parser.parse_args()
    target = ROOT / "docs" / "index.html"
    text = build()
    example = build_examples()
    fixtures = (("registry.json", example["bundle"]), ("registry_trust.json", example["trust"]),
                ("receipt.json", example["receipt"]), ("payment.json", example["payment"]))
    if args.check:
        if not target.exists() or target.read_text() != text:
            raise SystemExit("Demo is stale: run python tools/build_demo.py")
        for filename, value in fixtures:
            path = ROOT / "examples" / filename
            if not path.exists() or path.read_text() != json.dumps(value, ensure_ascii=True, indent=2) + "\n":
                raise SystemExit("Signed fixture is stale: " + filename)
        print("Demo matches the engine and fixtures.")
    else:
        target.write_text(text)
        for filename, value in fixtures:
            (ROOT / "examples" / filename).write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n")
        print("Built docs/index.html")

