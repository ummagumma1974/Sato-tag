"""Run from the repository root: python -m satotag --help."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .engine import ValidationError, analyze

MAX_INPUT_BYTES = 4 * 1024 * 1024


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValidationError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def main(argv=None):
    parser = argparse.ArgumentParser(description="SatoTag — offline, synthetic UTXO research prototype")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("analyze", help="Replay a synthetic ledger and emit an exact exposure report")
    cmd.add_argument("input", type=Path, help="JSON simulation dataset (max 4 MiB)")
    cmd.add_argument("--haircut", default="60", help="Hypothetical discount on exposure, 0..100 (default: 60)")
    cmd.add_argument("--output", type=Path, help="Save JSON; defaults to stdout")
    args = parser.parse_args(argv)
    try:
        if args.output and args.input.resolve() == args.output.resolve():
            raise ValidationError("Output must not overwrite the input dataset")
        with args.input.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValidationError("Input exceeds 4 MiB")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
        report = analyze(data, args.haircut)
        text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    except (ValidationError, OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        print(f"SatoTag: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
