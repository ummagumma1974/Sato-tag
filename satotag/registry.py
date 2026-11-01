"""Signed, quorum-reviewed simulation registry and payment-check receipts.

Trust is supplied by the verifier, never inferred from signatures or the log.
This is an offline protocol experiment, not a theft oracle or timestamp service.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .engine import ValidationError, analyze, _object, _require, _identifier, _integer, _text

ZERO = "0" * 64
LIMIT = 1000
DOMAIN = b"SatoTag registry v0.2\x00"


def canonical(value):
    """Protocol encoding: ASCII JSON, sorted keys, integers only, no floats."""
    def walk(v, depth=0):
        _require(depth <= 40, "JSON nesting limit exceeded")
        if v is None or type(v) in (str, bool, int):
            return
        if isinstance(v, list):
            for x in v:
                walk(x, depth + 1)
        elif isinstance(v, dict) and all(type(k) is str for k in v):
            for x in v.values():
                walk(x, depth + 1)
        else:
            raise ValidationError("Signed JSON permits no floats or non-JSON values")
    walk(value)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    _require(len(raw) <= 4 * 1024 * 1024, "Signed object exceeds 4 MiB")
    return raw


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def timestamp(value):
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value),
             "Use an exact UTC timestamp YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValidationError("Invalid UTC timestamp") from None


def _hex(value, size):
    _require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{%d}" % (size * 2), value),
             "Invalid lowercase hexadecimal key, hash or signature")
    return bytes.fromhex(value)


def validate_trust(trust):
    _object(trust, {"registry_id", "reviewers", "checkers", "quorum"}, set(), "trust")
    _identifier(trust["registry_id"], "registry_id")
    for role in ("reviewers", "checkers"):
        keys = trust[role]
        _require(isinstance(keys, dict) and 1 <= len(keys) <= 20, "Invalid trusted key set")
        for key_id, key in keys.items():
            _identifier(key_id, "key_id")
            _hex(key, 32)
        _require(len(set(keys.values())) == len(keys), "Aliases of the same key are not independent reviewers")
    _integer(trust["quorum"], "quorum", len(trust["reviewers"]))
    _require(2 <= trust["quorum"] <= len(trust["reviewers"]), "At least two reviewer keys required")
    return digest(trust)


def signing_bytes(kind, payload):
    _require(kind in ("event", "receipt"), "Unknown signed message kind")
    return DOMAIN + kind.encode() + b"\x00" + canonical(payload)


def _verify(envelope, keys, required, kind):
    _object(envelope, {"payload", "signatures"}, set(), kind)
    sigs = envelope["signatures"]
    _require(isinstance(sigs, list) and 1 <= len(sigs) <= 20, "Invalid signature count")
    signers = set()
    for sig in sigs:
        _object(sig, {"key_id", "signature"}, set(), "signature")
        key_id = sig["key_id"]
        _require(isinstance(key_id, str) and key_id in keys, "Signer is not trusted for this role")
        _require(key_id not in signers, "Duplicate signer")
        try:
            Ed25519PublicKey.from_public_bytes(_hex(keys[key_id], 32)).verify(
                _hex(sig["signature"], 64), signing_bytes(kind, envelope["payload"]))
        except InvalidSignature:
            raise ValidationError("Invalid Ed25519 signature") from None
        signers.add(key_id)
    _require(len(signers) >= required, "Reviewer quorum not reached")
    return sorted(signers)


def evidence_digest(case):
    return digest({"case_id": case["case_id"], "seeds": case["seeds"], "evidence": case["evidence"]})


def replay(ledger, events, trust, as_of, expected_head=None):
    """Validate the entire supplied log; derive the prefix visible at as_of.

    expected_head can pin a separately retained latest checkpoint. A valid log
    alone cannot prove completeness, prevent equivocation, or establish time.
    """
    policy_hash = validate_trust(trust)
    cutoff = timestamp(as_of)
    analyze(ledger)  # Validate the underlying synthetic graph and case schema.
    dataset_hash = digest(ledger)
    _require(isinstance(events, list) and len(events) <= LIMIT, "Too many registry events")
    cases = {c["case_id"]: c for c in ledger["cases"]}
    states = {c: {"status": "unreported", "active": False, "history": []} for c in cases}
    head, visible_head, visible_count, previous_time = ZERO, ZERO, 0, None
    for i, event in enumerate(events):
        _object(event, {"payload", "signatures"}, set(), "event")
        p = event["payload"]
        _object(p, {"version", "registry_id", "policy_hash", "dataset_hash", "seq", "previous",
                    "timestamp", "action", "case_id", "evidence_hash", "reason"}, set(), "event.payload")
        _require(type(p["version"]) is int and p["version"] == 2, "Unsupported registry version")
        _require(p["registry_id"] == trust["registry_id"] and p["policy_hash"] == policy_hash,
                 "Wrong registry or trust policy")
        _require(p["dataset_hash"] == dataset_hash, "Event belongs to a different dataset")
        _require(type(p["seq"]) is int and p["seq"] == i + 1 and p["previous"] == head,
                 "Broken log order or previous hash")
        when = timestamp(p["timestamp"])
        _require(previous_time is None or when >= previous_time, "Event timestamps go backwards")
        previous_time = when
        _require(isinstance(p["case_id"], str) and p["case_id"] in cases, "Unknown case")
        case = cases[p["case_id"]]
        _require(p["evidence_hash"] == evidence_digest(case), "Evidence or seed commitment mismatch")
        _text(p["reason"], "reason", 2000)
        action = p["action"]
        _require(action in ("submit", "accept", "contest", "revoke"), "Unknown event action")
        signers = _verify(event, trust["reviewers"], trust["quorum"] if action in ("accept", "revoke") else 1, "event")
        # Replay every transition even after the historical cutoff.
        current = states[p["case_id"]]
        allowed = {"submit": ("unreported",), "accept": ("pending", "contested"),
                   "contest": ("pending", "accepted"), "revoke": ("pending", "accepted", "contested")}
        _require(current["status"] in allowed[action], "Invalid case transition")
        if action == "accept":
            _require(all("sha256" in e for e in case["evidence"]), "Accepted cases require evidence hashes")
            current["active"] = True
        elif action == "revoke":
            current["active"] = False
        current["status"] = {"submit": "pending", "accept": "accepted", "contest": "contested", "revoke": "revoked"}[action]
        head = digest(event)
        current["history"].append({"seq": i + 1, "action": action, "timestamp": p["timestamp"],
                                   "reason": p["reason"], "signers": signers, "event_hash": head})
        if when <= cutoff:
            visible_head, visible_count = head, i + 1
    if expected_head is not None:
        _hex(expected_head, 32)
        _require(head == expected_head, "Latest checkpoint mismatch; log may be truncated or replaced")
    # Rebuild historical states from validated events, without trusting input status.
    historical = {c: {"status": "unreported", "active": False, "history": []} for c in cases}
    for c, state in states.items():
        for h in state["history"]:
            if h["seq"] > visible_count:
                continue
            s = historical[c]
            if h["action"] == "accept":
                s["active"] = True
            elif h["action"] == "revoke":
                s["active"] = False
            s["status"] = {"submit": "pending", "accept": "accepted", "contest": "contested", "revoke": "revoked"}[h["action"]]
            s["history"].append(h)
    effective = deepcopy(ledger)
    for case in effective["cases"]:
        s = historical[case["case_id"]]
        case["status"] = "accepted" if s["active"] else "revoked" if s["status"] == "revoked" else "pending"
    return {"registry_id": trust["registry_id"], "policy_hash": policy_hash, "dataset_hash": dataset_hash,
            "as_of": as_of, "head": visible_head, "event_count": visible_count, "latest_supplied_head": head,
            "cases": historical, "report": analyze(effective),
            "assurance": "Signatures and supplied-log consistency only; evidence truth, independent identities, time and completeness are not certified."}


def _request(request):
    _object(request, {"request_id", "inputs", "recipient", "amount_sats"}, set(), "payment request")
    _identifier(request["request_id"], "request_id")
    _text(request["recipient"], "recipient", 200)
    _require(_integer(request["amount_sats"], "amount_sats") > 0, "Payment must be positive")
    refs = request["inputs"]
    _require(isinstance(refs, list) and 1 <= len(refs) <= 100, "Invalid payment input count")
    _require(all(isinstance(r, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}:[0-9]{1,5}", r) for r in refs),
             "Invalid payment outpoint")
    _require(refs == sorted(set(refs)), "Payment inputs must be unique and sorted")
    return digest(request)


def screen(ledger, events, trust, as_of, request, expected_head=None):
    _require(expected_head is not None, "An independently obtained latest checkpoint is required for screening")
    request_hash = _request(request)
    snapshot = replay(ledger, events, trust, as_of, expected_head)
    rows = {r["outpoint"]: r for r in snapshot["report"]["outputs"]}
    _require(all(r in rows and rows[r]["spent_by"] is None for r in request["inputs"]),
             "Unknown or already spent payment input; cannot certify")
    _require(sum(rows[r]["value_sats"] for r in request["inputs"]) >= request["amount_sats"],
             "Insufficient proposed input value")
    selected = [rows[r] for r in request["inputs"]]
    marked = any(r["mark"] != "none" for r in selected)
    # Pending/contested signals conservatively require review for the whole dataset.
    # This intentionally avoids interpreting an unaccepted allegation as clean.
    needs_review = any(s["status"] in ("pending", "contested") for s in snapshot["cases"].values())
    return {"result": "marked" if marked else "review" if needs_review else "no_known_mark",
            "request_hash": request_hash, "snapshot_head": snapshot["head"],
            "snapshot_event_count": snapshot["event_count"], "dataset_hash": snapshot["dataset_hash"],
            "policy_hash": snapshot["policy_hash"], "registry_id": snapshot["registry_id"],
            "as_of": as_of, "request": deepcopy(request)}


def issue_receipt(ledger, events, trust, as_of, request, checker_id, private_key, ttl_seconds=300, expected_head=None):
    """Caller holds an Ed25519 key object; no key files, wallet keys or network I/O."""
    _require(type(ttl_seconds) is int and 1 <= ttl_seconds <= 300, "Receipt lifetime must be 1..300 seconds")
    _require(checker_id in trust["checkers"], "Untrusted checker")
    p = screen(ledger, events, trust, as_of, request, expected_head)
    p.update({"version": 2, "checker_id": checker_id,
              "expires_at": (timestamp(as_of) + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    envelope = {"payload": p, "signatures": [{"key_id": checker_id,
                  "signature": private_key.sign(signing_bytes("receipt", p)).hex()}]}
    _verify(envelope, trust["checkers"], 1, "receipt")
    return envelope


def verify_receipt(ledger, events, trust, receipt, payment, now, expected_head=None):
    """Recheck now. Late marks never disappear because an old receipt exists.

    Eligibility is a research-policy classification, not proof of good faith,
    innocence, legal protection, or Bitcoin settlement. now must be actual
    acceptance time. No persistent replay store or trusted clock is provided.
    """
    validate_trust(trust)
    _verify(receipt, trust["checkers"], 1, "receipt")
    p = receipt["payload"]
    required = {"version", "checker_id", "expires_at", "result", "request_hash", "snapshot_head",
                "snapshot_event_count", "dataset_hash", "policy_hash", "registry_id", "as_of", "request"}
    _object(p, required, set(), "receipt.payload")
    _require(type(p["version"]) is int and p["version"] == 2, "Unsupported receipt version")
    _require(len(receipt["signatures"]) == 1 and receipt["signatures"][0]["key_id"] == p["checker_id"],
             "Receipt checker mismatch")
    issued, expires, accepted = timestamp(p["as_of"]), timestamp(p["expires_at"]), timestamp(now)
    _require(issued <= accepted <= expires and timedelta(0) < expires - issued <= timedelta(seconds=300),
             "Receipt is expired, future-dated or has invalid lifetime")
    _require(_request(payment) == p["request_hash"] and payment == p["request"],
             "Actual payment differs from checked inputs, recipient, amount or request id")
    old = screen(ledger, events, trust, p["as_of"], payment, expected_head)
    for key, value in old.items():
        _require(p[key] == value, "Receipt does not match the supplied historical registry")
    current = screen(ledger, events, trust, now, payment, expected_head)
    late = p["result"] == "no_known_mark" and current["result"] != "no_known_mark"
    return {"signature_valid": True, "payment_matches": True, "checked_result": p["result"],
            "current_result": current["result"], "late_signal": late,
            "policy_decision": "manual_review_late_signal" if late else "manual_review" if current["result"] != "no_known_mark" else "eligible_under_experimental_policy",
            "receipt_sha256": digest(receipt), "snapshot_head": current["snapshot_head"],
            "automatic_exemption": False, "legal_guarantee": False,
            "limitations": "No receipt erases tags or proves an actual on-chain payment, honest purchaser, trusted time or complete registry."}
