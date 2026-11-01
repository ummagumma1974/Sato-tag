"""Reproducible key-authority fixtures. ALL PRIVATE KEYS ARE PUBLIC TEST KEYS."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from satotag.keyring import manifest_bytes, authorized_issue, authorized_verify, advance_manifest
from satotag.registry import ZERO, digest
from tools.governance_demo import fixture, T0, T1


def fixture_manifest():
    ledger, trust, keys, payment = fixture()
    keys['checker-reserve'] = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b'SATOTAG PUBLIC RESERVE DEMO ONLY').digest())
    trust['checkers']['checker-reserve'] = keys['checker-reserve'].public_key().public_bytes_raw().hex()
    root = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b'SATOTAG PUBLIC ROOT DEMO ONLY').digest())
    p = {"version": 1, "sequence": 1, "previous": ZERO, "issued_at": T0,
         "expires_at": "2026-11-02T12:00:00Z", "trust": trust,
         "keys": {k: {"not_before": T0, "not_after": "2026-11-03T12:00:00Z", "revoked": False} for k in keys}}
    p['keys']['checker-reserve']['not_before'] = T1
    return ledger, keys, payment, root, sign_manifest(p, root)


def sign_manifest(payload, root):
    return {"payload": deepcopy(payload), "signature": root.sign(manifest_bytes(payload)).hex()}


def build_examples():
    ledger, keys, payment, root, manifest = fixture_manifest()
    public = root.public_key().public_bytes_raw().hex()
    receipt = authorized_issue(ledger, [], manifest, public, digest(manifest), T0,
                               payment, 'checker', keys['checker'], ZERO)
    valid = authorized_verify(ledger, [], manifest, public, digest(manifest), T1, receipt, payment, ZERO)
    next_payload = deepcopy(manifest['payload'])
    next_payload.update(sequence=2, previous=digest(manifest), issued_at=T1)
    next_payload['keys']['checker']['revoked'] = True
    revoked = sign_manifest(next_payload, root)
    advance_manifest(manifest, revoked, public, T1)
    from satotag.engine import ValidationError
    try:
        authorized_verify(ledger, [], revoked, public, digest(revoked), T1, receipt, payment, ZERO)
    except ValidationError as exc:
        rejection = str(exc)
    else:
        raise RuntimeError('Revoked checker was accepted')
    replacement = authorized_issue(ledger, [], revoked, public, digest(revoked), T1,
                                   payment, 'checker-reserve', keys['checker-reserve'], ZERO)
    replacement_result = authorized_verify(ledger, [], revoked, public, digest(revoked), T1,
                                            replacement, payment, ZERO)
    return {"replacement_receipt": replacement, "replacement_result": replacement_result, "notice": "PUBLIC TEST KEYS, SYNTHETIC DATA, FIXED TEST CLOCK. NOT PRODUCTION AUTHORITY.",
            "root_public_key": public, "manifest_checkpoint": digest(manifest), "manifest": manifest,
            "revoked_checkpoint": digest(revoked), "revoked_manifest": revoked,
            "bundle": {"ledger": ledger, "events": []}, "payment": payment, "receipt": receipt,
            "valid_result": valid, "revoked_result": rejection}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build_examples()
    path = Path(__file__).resolve().parents[1] / 'examples' / 'key_authority.json'
    content = json.dumps(result, indent=2, ensure_ascii=True) + '\n'
    if args.check:
        if not path.exists() or path.read_text() != content:
            raise SystemExit('Key authority fixture is stale: python -m tools.keyring_demo')
        print('Key authority fixture matches verified lifecycle results.')
    else:
        path.write_text(content)
        print(path)
