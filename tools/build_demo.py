"""Generate a self-contained, offline demo from the Python engine's reports."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from satotag import analyze  # noqa: E402


def build():
    reports = [analyze(json.loads((ROOT / "examples" / f"{key}.json").read_text()))
               for key in ("split", "mixed", "dust", "revoked")]
    payload = json.dumps(reports, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    template = (ROOT / "tools" / "demo_template.html").read_text()
    return template.replace("__SATOTAG_REPORTS__", payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the committed demo is stale")
    args = parser.parse_args()
    target = ROOT / "docs" / "index.html"
    text = build()
    if args.check:
        if not target.exists() or target.read_text() != text:
            raise SystemExit("Demo is stale: run python tools/build_demo.py")
        print("Demo matches the engine and fixtures.")
    else:
        target.write_text(text)
        print("Built docs/index.html")
