"""Root-authorized key lifecycles around the v0.2 protocol.

The root public key and latest manifest hash are verifier-owned pins. Root
private keys never enter this module. Legacy registry APIs remain low-level.
"""
from copy import deepcopy
from datetime import timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .engine import ValidationError, _object, _require
from .registry import (ZERO, LIMIT, _hex, canonical, digest, timestamp,
                       validate_trust, replay, screen, issue_receipt, verify_receipt)

DOMAIN = b"SatoTag key authority v1\x00manifest\x00"
MAX_MANIFEST_AGE = timedelta(days=7)


def manifest_bytes(payload):
    return DOMAIN + canonical(payload)


def verify_manifest(envelope, root_public_key, expected_manifest, now):
    """Reject unknown roots, stale/future manifests, aliases and role overlap.

    expected_manifest must be obtained independently, never from the bundle.
    now must be trusted acceptance time. Hash pinning is the freshness boundary;
    expiration alone cannot reveal a newer withheld revocation.
    """
    _hex(root_public_key, 32)
    _hex(expected_manifest, 32)
    _object(envelope, {"payload", "signature"}, set(), "key manifest")
    _require(digest(envelope) == expected_manifest, "Latest key manifest checkpoint mismatch")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(root_public_key)).verify(
            _hex(envelope["signature"], 64), manifest_bytes(envelope["payload"]))
    except InvalidSignature:
        raise ValidationError("Invalid root signature") from None
    p = envelope["payload"]
    _object(p, {"version", "sequence", "previous", "issued_at", "expires_at", "trust", "keys"}, set(), "key manifest payload")
    _require(type(p["version"]) is int and p["version"] == 1, "Unsupported key manifest version")
    _require(type(p["sequence"]) is int and 1 <= p["sequence"] <= 1_000_000, "Invalid manifest sequence")
    _hex(p["previous"], 32)
    _require((p["sequence"] == 1) == (p["previous"] == ZERO), "Invalid manifest predecessor")
    issued, expires, current = timestamp(p["issued_at"]), timestamp(p["expires_at"]), timestamp(now)
    _require(issued <= current < expires and timedelta(0) < expires - issued <= MAX_MANIFEST_AGE,
             "Expired, future or excessively long-lived key manifest")
    trust = p["trust"]
    validate_trust(trust)
    ids = set(trust["reviewers"]) | set(trust["checkers"])
    _require(not (set(trust["reviewers"]) & set(trust["checkers"])), "Key id crosses roles")
    public_keys = list(trust["reviewers"].values()) + list(trust["checkers"].values())
    _require(len(set(public_keys)) == len(public_keys) and root_public_key not in public_keys,
             "Root, reviewer and checker keys must be distinct")
    _require(isinstance(p["keys"], dict) and set(p["keys"]) == ids, "Every enrolled key requires exactly one certificate")
    for cert in p["keys"].values():
        _object(cert, {"not_before", "not_after", "revoked"}, set(), "key certificate")
        _require(timestamp(cert["not_before"]) < timestamp(cert["not_after"]), "Invalid key validity window")
        _require(type(cert["revoked"]) is bool, "Revoked must be a boolean")
    return deepcopy(p)


def advance_manifest(previous, successor, root_public_key, now):
    """Verify an adjacent update against an already trusted persisted envelope.

    Caller must atomically persist the returned envelope/hash before use. This
    function deliberately performs no disk I/O or automatic root replacement.
    """
    # Validate old signature/schema even if expired: expiration cannot prevent recovery.
    _object(previous, {"payload", "signature"}, set(), "previous manifest")
    old = previous["payload"]
    _object(old, {"version", "sequence", "previous", "issued_at", "expires_at", "trust", "keys"}, set(), "previous manifest payload")
    verify_manifest(previous, root_public_key, digest(previous), old["issued_at"])
    new = verify_manifest(successor, root_public_key, digest(successor), now)
    _require(new["sequence"] == old["sequence"] + 1 and new["previous"] == digest(previous),
             "Manifest rollback, skipped version or broken predecessor")
    _require(timestamp(new["issued_at"]) >= timestamp(old["issued_at"]), "Manifest time goes backwards")
    _require(new["trust"] == old["trust"], "Enrolled trust changes require a new registry epoch")
    for key_id, cert in old["keys"].items():
        _require(not cert["revoked"] or new["keys"][key_id]["revoked"], "Revoked keys cannot be reactivated")
        _require(new["keys"][key_id]["not_before"] == cert["not_before"] and
                 new["keys"][key_id]["not_after"] == cert["not_after"],
                 "Existing key validity windows cannot be rewritten")
    return deepcopy(successor)


def _usable(p, key_id, role, when):
    _require(isinstance(key_id, str) and key_id in p["trust"][role], "Key is not authorized for this role")
    cert = p["keys"][key_id]
    _require(not cert["revoked"], "Key is revoked; manual recovery required")
    _require(timestamp(cert["not_before"]) <= timestamp(when) < timestamp(cert["not_after"]),
             "Key is not active or has expired")


def _context(ledger, events, manifest, root_public_key, expected_manifest, now, checkpoint):
    p = verify_manifest(manifest, root_public_key, expected_manifest, now)
    _require(isinstance(events, list) and len(events) <= LIMIT, "Too many registry events")
    # Registry validates all schemas and signatures before inspecting lifecycle fields.
    replay(ledger, events, p["trust"], now, checkpoint)
    for e in events:
        _require(timestamp(e["payload"]["timestamp"]) <= timestamp(now), "Future registry event")
        for sig in e["signatures"]:
            _usable(p, sig["key_id"], "reviewers", e["payload"]["timestamp"])
    return p


def authorized_screen(ledger, events, manifest, root_public_key, expected_manifest, now, payment, checkpoint):
    p = _context(ledger, events, manifest, root_public_key, expected_manifest, now, checkpoint)
    result = screen(ledger, events, p["trust"], now, payment, checkpoint)
    result.update(key_manifest_sha256=expected_manifest, key_manifest_sequence=p["sequence"])
    return result


def authorized_issue(ledger, events, manifest, root_public_key, expected_manifest, now,
                     payment, checker_id, private_key, checkpoint, ttl_seconds=300):
    p = _context(ledger, events, manifest, root_public_key, expected_manifest, now, checkpoint)
    _usable(p, checker_id, "checkers", now)
    receipt = issue_receipt(ledger, events, p["trust"], now, payment, checker_id, private_key,
                            ttl_seconds=ttl_seconds, expected_head=checkpoint)
    _require(timestamp(receipt["payload"]["expires_at"]) <= timestamp(p["keys"][checker_id]["not_after"]) and
             timestamp(receipt["payload"]["expires_at"]) <= timestamp(p["expires_at"]),
             "Receipt lifetime exceeds key or manifest expiry")
    return receipt


def authorized_verify(ledger, events, manifest, root_public_key, expected_manifest, now,
                      receipt, payment, checkpoint):
    p = _context(ledger, events, manifest, root_public_key, expected_manifest, now, checkpoint)
    result = verify_receipt(ledger, events, p["trust"], receipt, payment, now, checkpoint)
    checker = receipt["payload"]["checker_id"]
    _usable(p, checker, "checkers", receipt["payload"]["as_of"])
    _usable(p, checker, "checkers", now)
    _require(timestamp(receipt["payload"]["expires_at"]) <= timestamp(p["keys"][checker]["not_after"]),
             "Receipt lifetime exceeds key expiry")
    result["key_manifest_sha256"] = expected_manifest
    result["key_manifest_sequence"] = p["sequence"]
    return result
