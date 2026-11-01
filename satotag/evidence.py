"""Experimental evidence gate. Signatures authenticate assessments, not facts.

Only evidence_screen enforces this layer. Existing registry/keyring APIs are
lower-level tools. Policy/identity enrollment and checkpoints are verifier-owned.
"""
import hashlib
from datetime import timedelta
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .engine import ValidationError, _object, _require, _text
from .registry import canonical, digest, timestamp, _hex, evidence_digest
from .keyring import _context, _usable, authorized_screen

DOMAIN = b"SatoTag evidence review v1\0"
CHECKS = ("prior_control", "unauthorized_transfer", "seed_link",
          "independent_corroboration", "alternative_explanations")


def _nonblank(value, label, limit=500):
    _text(value, label, limit)
    _require(bool(value.strip()) and value == value.strip(), label + ": blank or padded text")


def review_bytes(payload):
    return DOMAIN + canonical(payload)


def validate_policy(policy, expected_policy, trust):
    _hex(expected_policy, 32)
    _require(digest(policy) == expected_policy, "Evidence policy checkpoint mismatch")
    _object(policy, {"version", "registry_id", "reviewers", "quorum", "max_review_age_seconds"}, set(), "evidence policy")
    _require(type(policy["version"]) is int and policy["version"] == 1, "Unsupported evidence policy")
    _require(policy["registry_id"] == trust["registry_id"], "Wrong evidence registry")
    people = policy["reviewers"]
    _require(isinstance(people, dict) and set(people) == set(trust["reviewers"]), "Enroll every reviewer identity")
    for identity in people.values():
        _object(identity, {"person_id", "organization_id"}, set(), "reviewer identity")
        for value in identity.values():
            _nonblank(value, "identity", 100)
    _require(type(policy["quorum"]) is int and trust["quorum"] <= policy["quorum"] <= len(people), "Invalid evidence quorum")
    age = policy["max_review_age_seconds"]
    _require(type(age) is int and 1 <= age <= 86400, "Review window must be 1..86400 seconds")


def validate_acceptance(ledger, event, package, policy, manifest_payload, artifacts):
    """Called only after registry, manifest and policy validation by evidence_screen.

    artifacts maps SHA-256 to exact bytes supplied by the verifier, never URLs.
    No network access, path following, or automatic interpretation of evidence.
    """
    _object(package, {"dossier", "reviews"}, set(), "acceptance package")
    dossier = package["dossier"]
    _object(dossier, {"version", "case_id", "dataset_hash", "evidence_hash", "claimant_person_id",
                     "claimant_organization_id", "statement", "artifacts"}, set(), "dossier")
    p = event["payload"]
    case = next(c for c in ledger["cases"] if c["case_id"] == p["case_id"])
    _require(type(dossier["version"]) is int and dossier["version"] == 1, "Unsupported dossier")
    _require(dossier["case_id"] == p["case_id"] and dossier["dataset_hash"] == digest(ledger)
             and dossier["evidence_hash"] == evidence_digest(case), "Dossier does not bind this case and dataset")
    for field in ("claimant_person_id", "claimant_organization_id", "statement"):
        _nonblank(dossier[field], field, 2000)
    refs = dossier["artifacts"]
    _require(isinstance(refs, list) and 1 <= len(refs) <= 20, "Dossier needs 1..20 artifacts")
    by_id = {}
    hashes = set()
    for artifact in refs:
        _object(artifact, {"id", "sha256", "source_id", "description"}, set(), "artifact")
        for field in ("id", "source_id", "description"):
            _nonblank(artifact[field], field, 1000)
        sha = artifact["sha256"]
        _hex(sha, 32)
        _require(artifact["id"] not in by_id and sha not in hashes, "Duplicate artifact")
        _require(sha in artifacts and type(artifacts[sha]) is bytes, "Missing evidence bytes")
        _require(hashlib.sha256(artifacts[sha]).hexdigest() == sha, "Evidence bytes changed")
        by_id[artifact["id"]] = artifact
        hashes.add(sha)
    _require({e["sha256"] for e in case["evidence"]} <= hashes, "Dossier omits case evidence")
    reviews = package["reviews"]
    _require(isinstance(reviews, list) and 1 <= len(reviews) <= 20, "Invalid review count")
    signers, persons, organizations = set(), set(), set()
    event_signers = {s["key_id"] for s in event["signatures"]}
    for envelope in reviews:
        _object(envelope, {"payload", "signature"}, set(), "evidence review")
        r = envelope["payload"]
        _object(r, {"version", "reviewer_id", "policy_hash", "acceptance_hash", "dossier_hash",
                    "reviewed_at", "conflict_of_interest", "decision", "checks"}, set(), "review payload")
        _require(type(r["version"]) is int and r["version"] == 1, "Unsupported review")
        reviewer = r["reviewer_id"]
        _require(isinstance(reviewer, str) and reviewer in policy["reviewers"] and reviewer in event_signers,
                 "Reviewer must also sign this acceptance")
        _require(reviewer not in signers, "Duplicate reviewer")
        _usable(manifest_payload, reviewer, "reviewers", r["reviewed_at"])
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(manifest_payload["trust"]["reviewers"][reviewer])).verify(
                _hex(envelope["signature"], 64), review_bytes(r))
        except InvalidSignature:
            raise ValidationError("Invalid evidence review signature") from None
        _require(r["policy_hash"] == digest(policy) and r["acceptance_hash"] == digest(event)
                 and r["dossier_hash"] == digest(dossier), "Review binding mismatch")
        delta = timestamp(p["timestamp"]) - timestamp(r["reviewed_at"])
        _require(timedelta(0) <= delta <= timedelta(seconds=policy["max_review_age_seconds"]), "Stale or future review")
        _require(r["conflict_of_interest"] is False and r["decision"] == "approve", "Conflicted or non-approving review")
        identity = policy["reviewers"][reviewer]
        person, organization = identity["person_id"], identity["organization_id"]
        _require(person != dossier["claimant_person_id"] and organization != dossier["claimant_organization_id"], "Claimant cannot review own claim")
        _require(person not in persons and organization not in organizations, "Reviewers must be independently enrolled people and organizations")
        checks = r["checks"]
        _object(checks, set(CHECKS), set(), "review checklist")
        for name in CHECKS:
            check = checks[name]
            _object(check, {"outcome", "rationale", "artifact_ids"}, set(), "check")
            _require(check["outcome"] == "pass", "Unresolved evidence check: " + name)
            _nonblank(check["rationale"], "check rationale", 2000)
            ids = check["artifact_ids"]
            _require(isinstance(ids, list) and 1 <= len(ids) <= 20 and all(isinstance(i, str) and i in by_id for i in ids), "Invalid evidence citations")
            _require(len(set(ids)) == len(ids), "Duplicate evidence citation")
            if name == "independent_corroboration":
                _require(len({by_id[i]["source_id"] for i in ids}) >= 2, "Corroboration needs two declared sources")
        signers.add(reviewer)
        persons.add(person)
        organizations.add(organization)
    _require(len(signers) >= policy["quorum"], "Insufficient evidence reviews")
    return {"case_id": p["case_id"], "acceptance_hash": digest(event),
            "dossier_hash": digest(dossier), "reviewers": sorted(signers)}


def evidence_screen(ledger, events, manifest, root_public_key, expected_manifest, now,
                    payment, checkpoint, policy, expected_policy, packages, artifacts):
    """Fail closed for missing/invalid evidence, including historical acceptances.

    This is a simulation gate, not theft adjudication or Bitcoin enforcement.
    Every acceptance (also re-acceptance after contest) needs its own review set.
    The caller supplies a trusted clock, policy pin and latest independent heads.
    """
    m = _context(ledger, events, manifest, root_public_key, expected_manifest, now, checkpoint)
    validate_policy(policy, expected_policy, m["trust"])
    accepted = {digest(e): e for e in events if e["payload"]["action"] == "accept"}
    _require(isinstance(packages, dict) and set(packages) == set(accepted), "Each acceptance needs exactly one evidence package")
    _require(isinstance(artifacts, dict) and len(artifacts) <= 20000, "Invalid artifact store")
    _require(all(type(v) is bytes for v in artifacts.values()), "Artifacts must be bytes")
    _require(sum(len(v) for v in artifacts.values()) <= 4 * 1024 * 1024, "Artifacts exceed 4 MiB")
    assessments = [validate_acceptance(ledger, e, packages[h], policy, m, artifacts) for h, e in accepted.items()]
    result = authorized_screen(ledger, events, manifest, root_public_key, expected_manifest, now, payment, checkpoint)
    result.update(evidence_policy_sha256=expected_policy, evidence_assessments=assessments,
                  evidence_assurance="Integrity and signed human assessments verified; truth and independence are not established by software.")
    return result
