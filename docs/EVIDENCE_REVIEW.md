# Evidence review — experimental procedure and verification gate

SatoTag now has an executable `evidence-screen` path. It verifies evidence integrity and signed, structured assessments before returning a screening result. It **does not establish that a theft occurred**, authenticate the original records, establish real-world reviewer independence, or disable spending on Bitcoin. All committed examples are synthetic and use public test keys.

## What must happen before an allegation becomes an accepted claim

| Stage | Responsible person | Required record | If incomplete or disputed |
|---|---|---|---|
| Intake | Case handler | Incident narrative, exact transaction outputs, claimant contact through a private channel, timeline and requested scope | Keep pending; do not describe an allegation as an established theft |
| Preservation | Evidence custodian | Original bytes, SHA-256, acquisition source/time/method, access log, immutable original plus redacted working copies | Request original records; record gaps rather than filling them with assumptions |
| Investigation | Each independent reviewer | Five checks below, reasons, citations and contrary evidence | A failed or unknown check blocks approval |
| Independent decision | At least two separately enrolled people from separate organizations | Signed assessments tied to this dossier, policy and exact acceptance event; no claimant or organizational self-review | Recuse conflicts; obtain replacement reviewers; do not count more keys as more people |
| Challenge | Different accountable reviewer where practicable | Challenge reference, supporting records, response, signed contest event and reason | Show the dispute; existing contest behavior retains exposure pending resolution |
| Correction | Authorized quorum | Reasoned revocation or a fresh reviewed acceptance after contest | Preserve history; revoke erroneous claims and recompute exposure |

This is a proposed operating procedure, not a deployed investigation service. No investigators, independent organizations or evidence custodians have been recruited or verified by this repository. Operators must define response deadlines, escalation ownership, appeal handling and secure retention before processing real claims.

## Five mandatory assessments

1. **Prior control:** compare records predating the incident, custody/account records and, where safe, a scoped proof of control. A signature proves key control at signing time, not legal ownership or that a transfer was unauthorized. Never ask for a seed phrase or private key.
2. **Unauthorized transfer:** examine the claimant's account, authorization records, incident timeline, compromise evidence and competing explanations. A transaction hash alone cannot establish theft.
3. **Seed link:** identify exact transaction ID and output index, amounts, network and relevant transaction history. Establish the alleged incident's link to those outputs. Document uncertainty and avoid inferring identities from mere address proximity.
4. **Independent corroboration:** cite at least two genuinely separate sources. Two websites repeating one report are one origin. The software checks distinct declared source IDs and exact bytes; a person must investigate their authenticity and independence.
5. **Alternative explanations:** examine consent, custody arrangements, internal transfers, refunds, false allegations and exculpatory records. Record why alternatives were ruled out or why the claim remains unresolved. Do not treat inability to obtain a response as proof.

A `pass` is an accountable human assessment, not a mathematical proof. The software cannot detect a dishonest rationale or colluding reviewers who have been falsely enrolled as independent.

## What the code enforces

- The existing root-signed key lifecycle, independently pinned registry head and current key-manifest checkpoint.
- A separate **verifier-pinned evidence policy** with reviewer person/organization IDs, quorum at least as large as the registry quorum and review age of at most 24 hours at acceptance.
- A dossier bound to the case, complete dataset and case evidence digest. Each artifact has a unique ID, digest, source ID and description. Every case evidence digest must be present.
- Exact SHA-256 verification against locally supplied bytes. The verifier never downloads evidence URLs or follows file paths supplied in a dossier.
- Domain-separated Ed25519 reviews bound to the exact signed acceptance event, complete dossier and evidence policy. Reviewers must also sign that acceptance, have valid non-revoked keys, declare no conflict and provide every assessment, rationale and citation.
- Distinct enrolled persons and organizations, neither matching the declared claimant. This enforces the enrolled identity claims; it does not verify that those claims are true.
- Missing, invalid, conflicted, rejected, stale-at-acceptance or unknown assessments fail closed with an error, **not** a `no_known_mark` result.
- A separate package for every acceptance, including re-acceptance after a contest. Historical accepted claims still require their audit package after revocation; revocation then clears exposure under the existing model.

`analyze`, `registry`, `authorized-screen`, receipt creation and receipt verification remain lower-level APIs. They **do not enforce evidence review**. Integrators requiring this assurance must call `evidence_screen` / `evidence-screen` on the current snapshot before acting; a legacy receipt is not an evidence certificate. The new gate does not issue an evidence-certified payment receipt.

## Reproduce the synthetic example

```sh
python -m pip install -e ".[governance]"
python -m unittest discover -s tests -v
python -m tools.evidence_demo --check
```

Inspect `examples/evidence_review.json` for the complete synthetic dossier, policy, signed assessments, original UTF-8 artifact texts and verification results. It contains no real incident evidence. The demo's evidence table is generated from this Python verification, not a browser upload or live investigation.

Minimal Python invocation using only the committed fixture:

```python
import json
from pathlib import Path
from satotag.evidence import evidence_screen

example = json.loads(Path("examples/evidence_review.json").read_text())
a = example["fixture"]
a["artifacts"] = {h: text.encode("utf-8") for h, text in a["artifacts"].items()}
print(evidence_screen(**a))
```

**Fixture-only convenience:** pins and fixed time above come from the example itself. A real verifier must obtain its root key, policy hash, latest manifest hash and latest registry head independently, persist them safely and use a trusted clock. Never trust pins delivered by a claimant. Current pins cannot be inferred from an old file. Review timestamps are signed declarations, not trusted timestamp attestations.

CLI shape (files must be prepared by the verifier):

```sh
python -m satotag evidence-screen bundle.json \
  --manifest manifest.json --root-key "$ROOT_PUBLIC_KEY" \
  --manifest-checkpoint "$LATEST_MANIFEST_HASH" \
  --checkpoint "$LATEST_REGISTRY_HEAD" --as-of "$TRUSTED_UTC_TIME" \
  --payment payment.json --evidence evidence.json \
  --evidence-policy-checkpoint "$PINNED_EVIDENCE_POLICY_HASH"
```

`bundle.json` has `ledger` and `events`; `evidence.json` has exactly `policy`, `packages`, and `artifacts`. Packages are indexed by acceptance-event digest. CLI artifacts map a digest to UTF-8 text, hashed as its exact UTF-8 encoding. The Python API accepts arbitrary bytes. Files and the artifact store are limited to 4 MiB. There is no upload service.

## Appeals, privacy and changes

Publish claim identifiers, state, policy version, decision reasons and carefully redacted evidence summaries where appropriate. Keep identifying documents, account details and sensitive incident records in a controlled evidence store, **not GitHub**. Redacted material has different bytes and therefore needs its own digest. An empty public dossier must never be passed off as a fully verified dossier.

Keep an accessible challenge channel with an accountable owner. A challenge should trigger investigation without forcing an affected holder to publish personal data. Preserve opposing evidence and a chronological decision record. If an acceptance was wrong, use a signed revocation; do not erase it. A corrected dossier changes its digest and needs new reviews. A contested claim re-accepted in the same dataset needs reviews tied to the new acceptance event. Dataset amendments require a new registry epoch because existing signatures bind the entire dataset.

Policy changes also invalidate old policy-bound assessments under this strict gate. Plan a documented migration and re-review; do not quietly lower the threshold or rewrite enrollment to rescue a failing case. The prototype has no automated policy migration, investigator credential verification, legal adjudication, trusted timestamping, secure evidence hosting, or external audit. These are deployment requirements, not features implied by passing tests.
