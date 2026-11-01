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


def _load(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValidationError("Input exceeds 4 MiB")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)


def main(argv=None):
    parser = argparse.ArgumentParser(description="SatoTag — offline, synthetic UTXO research prototype")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("analyze", help="Replay a synthetic ledger and emit an exact exposure report")
    cmd.add_argument("input", type=Path, help="JSON simulation dataset (max 4 MiB)")
    cmd.add_argument("--haircut", default="60", help="Hypothetical discount on exposure, 0..100 (default: 60)")
    cmd.add_argument("--output", type=Path, help="Save JSON; defaults to stdout")
    for command in ("registry", "verify-receipt"):
        gov = sub.add_parser(command, help="Verify signed simulation registry" if command == "registry" else "Verify a payment-check receipt and recheck current marks")
        gov.add_argument("input", type=Path, help="JSON object with ledger and events")
        gov.add_argument("--trust", type=Path, required=True, help="Verifier-chosen public keys and quorum; never trust arbitrary bundled keys")
        gov.add_argument("--as-of", required=True, help="UTC check/acceptance time")
        gov.add_argument("--checkpoint", required=True, help="Independently obtained latest registry head hash")
        gov.add_argument("--output", type=Path)
        if command == "verify-receipt":
            gov.add_argument("--receipt", type=Path, required=True)
            gov.add_argument("--payment", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        inputs = [args.input] + [getattr(args, k) for k in ("trust", "receipt", "payment") if hasattr(args, k)]
        if args.output and args.output.resolve() in [p.resolve() for p in inputs]:
            raise ValidationError("Output must not overwrite the input dataset")
        data = _load(args.input)
        if args.command == "analyze":
            report = analyze(data, args.haircut)
        else:
            try:
                from .registry import replay, verify_receipt
            except ImportError:
                raise ValidationError('Install signature support: python -m pip install -e ".[governance]"') from None
            if not isinstance(data, dict) or set(data) != {"ledger", "events"}:
                raise ValidationError("Registry bundle must contain exactly ledger and events")
            trust = _load(args.trust)
            if args.command == "registry":
                report = replay(data["ledger"], data["events"], trust, args.as_of, args.checkpoint)
            else:
                report = verify_receipt(data["ledger"], data["events"], trust,
                                        _load(args.receipt), _load(args.payment), args.as_of, args.checkpoint)
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

