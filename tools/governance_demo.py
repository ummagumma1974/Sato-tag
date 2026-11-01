"""PUBLIC INSECURE DEMO KEYS. Never trust these keys for real claims.

Deterministic keys exist only to reproduce synthetic fixtures in tests/builds.
They are deliberately public; signatures demonstrate verification, not authority.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from satotag.registry import (ZERO, digest, evidence_digest, issue_receipt, replay,
                              screen, signing_bytes, verify_receipt)

ROOT = Path(__file__).resolve().parents[1]
T0 = "2026-11-01T12:00:00Z"
T1 = "2026-11-01T12:01:00Z"
T2 = "2026-11-01T12:02:00Z"
T3 = "2026-11-01T12:03:00Z"
T4 = "2026-11-01T12:04:00Z"


def fixture():
    keys = {name: Ed25519PrivateKey.from_private_bytes(hashlib.sha256(
        ("SATOTAG PUBLIC DEMO KEY ONLY: " + name).encode()).digest())
        for name in ("reviewer-a", "reviewer-b", "reviewer-c", "checker")}
    trust = {"registry_id": "DEMO-NOT-AUTHORITY", "quorum": 2,
             "reviewers": {k: v.public_key().public_bytes_raw().hex() for k, v in keys.items() if k != "checker"},
             "checkers": {"checker": keys["checker"].public_key().public_bytes_raw().hex()}}
    ledger = json.loads((ROOT / "examples" / "split.json").read_text())
    for c in ledger["cases"]:
        c["status"] = "pending"
        for e in c["evidence"]:
            e["sha256"] = hashlib.sha256(b"invented demonstration evidence; no real theft").hexdigest()
    payment = {"request_id": "DEMO-ORDER-001", "inputs": ["split:1"],
               "recipient": "synthetic-recipient", "amount_sats": 100_000}
    return ledger, trust, keys, payment


def event(ledger, trust, keys, events, action, when, signers=None, reason=None):
    signers = signers or (["reviewer-a", "reviewer-b"] if action in ("accept", "revoke") else ["reviewer-c"])
    case = ledger["cases"][0]
    payload = {"version": 2, "registry_id": trust["registry_id"], "policy_hash": digest(trust),
               "dataset_hash": digest(ledger), "seq": len(events) + 1,
               "previous": digest(events[-1]) if events else ZERO, "timestamp": when,
               "action": action, "case_id": case["case_id"], "evidence_hash": evidence_digest(case),
               "reason": reason or "Synthetic " + action + "; no real claim"}
    return {"payload": payload, "signatures": [{"key_id": k,
             "signature": keys[k].sign(signing_bytes("event", payload)).hex()} for k in signers]}


def build_examples():
    ledger, trust, keys, payment = fixture()
    events = []
    receipt = issue_receipt(ledger, events, trust, T0, payment, "checker", keys["checker"], expected_head=ZERO)
    cards = []
    for action, when in (("submit", T1), ("accept", T2), ("contest", T3), ("revoke", T4)):
        events.append(event(ledger, trust, keys, events, action, when))
        snap = replay(ledger, events, trust, when, digest(events[-1]))
        check = screen(ledger, events, trust, when, payment, digest(events[-1]))
        old_receipt = verify_receipt(ledger, events, trust, receipt, payment, when, digest(events[-1]))
        state = snap["cases"][ledger["cases"][0]["case_id"]]
        cards.append({"action": action, "state": state, "check": check, "receipt_check": old_receipt,
                      "head": snap["head"], "event_count": snap["event_count"]})
    tampered = deepcopy(receipt)
    tampered["payload"]["request"]["recipient"] = "attacker"
    from satotag.engine import ValidationError
    try:
        verify_receipt(ledger, events, trust, tampered, payment, T4, digest(events[-1]))
    except ValidationError:
        tamper_rejected = True
    else:
        raise RuntimeError("Tampered receipt was accepted")
    return {"notice": "PUBLIC DEMO KEYS — all identities, evidence, timestamps and payments are fictional.",
            "policy": {"quorum": 2, "reviewers": 3, "receipt_ttl_seconds": 300,
                       "late_signals": "manual review; no automatic exemption"},
            "tamper_rejected": tamper_rejected, "cards": cards,
            "bundle": {"ledger": ledger, "events": events}, "trust": trust,
            "receipt": receipt, "payment": payment, "latest_head": digest(events[-1])}


if __name__ == "__main__":
    print(json.dumps(build_examples(), ensure_ascii=True, indent=2))
