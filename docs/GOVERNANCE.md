# Signed registry and payment checks — v0.2

This is an **offline simulation protocol**, not a production theft registry,
Bitcoin consensus change, legal safe harbour, or unbreakable security system.
The existing `analyze` API remains available for the four original scenarios.
It accepts caller-supplied statuses; use `registry.replay` for signed governance.

## What is verified

- Ed25519 signatures from verifier-selected public keys.
- A threshold of at least two distinct reviewer keys for acceptance and revocation.
- One reviewer may submit or contest. Contesting an active case keeps its tag active.
- An ordered hash-linked event log with valid state transitions and monotonic
  **declared** UTC timestamps. Revocation preserves earlier events in the supplied log.
- Commitments to the exact synthetic dataset, evidence records, seed outputs,
  trust configuration, registry id and previous event.
- Payment-check receipts bound to the exact request id, ordered inputs,
  recipient, amount, historical checkpoint, result, policy and expiry (at most 5 minutes).
- Rechecking at acceptance time. A late signal requires manual review. An earlier
  receipt never removes exposure, automatically exempts funds, or changes their balance.

An evidence digest commits to bytes; it does not prove an accusation. Multiple
keys are not proof of independent people. Signature validation identifies keys.

## Trust boundary and rollback resistance

`trust` is a separate, verifier-selected object. Never accept keys suggested by
an untrusted payment sender or arbitrary bundled metadata. Its schema is:

```json
{"registry_id":"chosen-registry","reviewers":{"r1":"32-byte hex public key","r2":"another key"},"checkers":{"checker":"32-byte hex public key"},"quorum":2}
```

Screening and receipt verification **require an independently obtained latest
checkpoint** (`expected_head`). An omitted checkpoint or a truncated/rewritten
log that differs from the pinned head is rejected. Obtain the pin through an
authenticated independent channel; using the attacker's checkpoint defeats this
protection. Different valid signed histories can still exist if trusted reviewers
equivocate; signatures and hash links alone cannot establish a globally unique log.

Input case status is never an activation authority in `replay`: the effective
states are reconstructed from signed events. All supplied events, including
those after a historical cutoff, are validated before historical state is used.
Unknown/missing or already spent inputs are rejected. Pending or contested cases
conservatively require review of payments throughout the supplied dataset.
This broad rule can cause false alarms/denial of service; it is deliberate in
this limited simulation and must not be advertised as a production classifier.

## Events

An envelope has exactly `payload` and `signatures`. The payload has:
`version=2`, `registry_id`, `policy_hash`, `dataset_hash`, `seq`, `previous`,
`timestamp`, `action`, `case_id`, `evidence_hash`, `reason`.

Transitions: unreported → submit/pending → accept/accepted; pending or accepted
→ contest/contested; contested → accept/accepted; pending, accepted or contested
→ revoke/revoked. A revoked case cannot be reopened under the same id.
Accepted cases require SHA-256 evidence commitments. Logs may contain at most
1,000 events and policies at most 20 keys per role. Key aliases within a role
are rejected and repeated signatures cannot reach quorum.

Signing bytes are the ASCII prefix `SatoTag registry v0.2` plus a zero byte,
then `event` or `receipt`, then a zero byte, then canonical payload JSON.
Canonical JSON is Python `json.dumps(sort_keys=True, separators=(',', ':'),
ensure_ascii=True)` encoded as UTF-8, with floats and non-JSON types forbidden.
This is a versioned local encoding, **not a claim of RFC 8785 compliance**.
Event hashes commit to the entire envelope (including signature array order).

## Reproduce the public fixtures

Requires Python 3.11+ and the optional signature dependency:

```bash
python -m pip install -e ".[governance]"
python -m unittest discover -s tests -v
python tools/build_demo.py
python tools/build_demo.py --check
```

The builder creates `examples/registry.json`, `registry_trust.json`,
`receipt.json` and `payment.json`. **All demo keys are deliberately public and
reproducible in `tools/governance_demo.py`. They have no real authority.**
The files describe invented identities, evidence, times and funds.

Print the final demo checkpoint:

```bash
python -c "import json; from satotag.registry import digest; d=json.load(open('examples/registry.json')); print(digest(d['events'][-1]))"
```

Copy that hash as `HEAD` below for fixture testing only. This is not an independent
checkpoint acquisition procedure for real-world use.

```bash
python -m satotag registry examples/registry.json --trust examples/registry_trust.json --as-of 2026-11-01T12:02:00Z --checkpoint HEAD
python -m satotag verify-receipt examples/registry.json --trust examples/registry_trust.json --as-of 2026-11-01T12:02:00Z --checkpoint HEAD --receipt examples/receipt.json --payment examples/payment.json
```

The second command returns `manual_review_late_signal`: the original receipt
declared no known mark at 12:00; a signed case activated at 12:02. With 12:04 as
acceptance time the supplied example includes the later signed revocation.

Programmatic API: `replay`, `screen`, `issue_receipt`, `verify_receipt` in
`satotag.registry`. `issue_receipt` takes a caller-held Ed25519 private key
object; no wallet keys, key uploads, network calls or disk key storage are used.
Keep signing keys outside this repository. Persist consumed request ids in any
application integrating these APIs; this library provides no durable replay store.

## What an attacker can still do

| Threat | v0.2 handling and remaining boundary |
|---|---|
| Alter a signed field | Reject invalid signature; a compromised trusted key can sign new lies |
| Reuse one review signature twice | Reject duplicates and same-key aliases; cannot identify human independence |
| Delete/reorder history | Reject broken links or pinned-head mismatch; no globally immutable storage |
| Present a stale clean receipt | Expiry, exact request binding and current recheck; requires trusted acceptance clock and latest pin |
| Obtain receipts before reporting a theft | Later signals still trigger manual review; good faith cannot be proven automatically |
| Replace the checked payment | Reject changed inputs, recipient, amount or order id; no Bitcoin transaction parser or settlement proof |
| Collude as a quorum | Not prevented; external governance, accountability and key custody are required |
| Hide every trace of a report | Not detectable without independent publication/checkpoints and a completeness policy |
| Compromise website/build/checker | Not solved by a demo; pin and verify code, isolate keys, independently audit implementations |
| Feed text instructing an AI to ignore rules | Text is data, never evaluated or sent to a model; AI-assisted attackers face the same crypto boundaries |

Do not use this prototype to accept/refuse real deposits. Before that, it needs
an independent audit, external timestamp/checkpoint publication, evidence review
procedures, production key custody/recovery, authenticated current-state distribution,
durable replay protection, real-chain imports with reorg handling, privacy
controls and measured false-positive/false-negative rates.

The live page shows **Python-verified, precomputed fixture results**, not a
browser verifier for user-supplied signatures. Its JSON export includes public
trust keys for reproduction; it is not an authority certificate.

The optional [v0.2.1 key authority layer](KEY_AUTHORITY.md) now implements signed
key lifetimes, revocations and pre-enrolled reserve replacement. Use its
authorization-enforcing entry points; the low-level APIs described above remain
available for research and legacy fixtures.
