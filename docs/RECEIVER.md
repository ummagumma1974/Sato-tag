# Receiving-service integration — local end-to-end prototype

The receiver now turns the evidence-screening result into an enforced local admission decision. A payment request passes through the complete evidence gate before an invoice can be admitted. The caller cannot supply an approval, keys, policy, clock or checkpoint.

**Scope:** an executable local merchant admission prototype using synthetic ledgers. It does not run an exchange, receive Bitcoin, credit deposits, broadcast transactions or enforce Bitcoin consensus. It has not been integrated with any external wallet or exchange.

## Decision contract

| Gate result | Receiver decision | HTTP status | Local admission created? |
|---|---|---:|---|
| Marked input | `rejected` | 403 | No |
| Pending or contested review without a marked selected input | `held` | 409 | No |
| Evidence missing, invalid signatures, stale supplied head, expired manifest or unavailable verification | `blocked` | 503 | No new admission |
| No known mark in the supplied scope | `accepted` | 200 | Yes, once per invoice; input reservation only |
| Malformed HTTP/JSON request | `blocked` | 400 | No |

A contested active mark remains marked under the existing registry policy and is rejected. `accepted` does not mean legally clean, ownership verified, paid, mined or credited. Every response includes `scope: local_admission_only` and `funds_credited: false`.

## Run the actual local service

From the repository root:

```sh
python -m pip install -e ".[governance]"
python -m tools.receiver_demo --serve
```

The server binds only to `127.0.0.1:8765`. The demonstration uses **public test keys, fictional evidence and a fixed test clock**. It writes `receiver-demo.sqlite`, which is ignored by Git. Stop it with Ctrl-C. Do not expose this development HTTP server publicly.

In another terminal, send the fictional marked payment:

```sh
curl -i http://127.0.0.1:8765/admit \
  -H 'Content-Type: application/json' \
  --data '{"request_id":"DEMO-ORDER-001","inputs":["split:1"],"recipient":"synthetic-recipient","amount_sats":100000}'
```

Expected response: **HTTP 403**, `decision: rejected`. No admission is created.

To exercise a separate unmarked output in the same fictional ledger, change `split:1` to `origin:1`. Expected response: **HTTP 200**, local admission only. Repeating that exact request does not create another admission. A conflicting request for the same invoice cannot replace its reserved inputs.

Run all six HTTP scenarios, without leaving a server running:

```sh
python -m tools.receiver_demo --check
python -m unittest discover -s tests -v
```

These commands exercise real loopback HTTP and SQLite. The website displays the recorded results from this execution. Its buttons select recorded scenarios; GitHub Pages does not host this Python server.

## Integration boundary for developers

```python
from satotag.receiver import Receiver, make_server

receiver = Receiver(
    database="merchant.sqlite",
    invoices=operator_issued_invoices,
    context_provider=load_current_verified_context,
    clock=trusted_utc_clock,
)
server = make_server(receiver, port=8765)
```

`invoices` maps server-issued request IDs to exact `recipient` and integer `amount_sats` values. `context_provider()` supplies the keyword arguments of `evidence_screen` except `payment` and `now`: ledger, registry events, root-signed manifest, independently pinned root key, latest manifest and registry checkpoints, evidence policy and its independent checkpoint, acceptance packages and original artifact bytes. The payer supplies only the four payment fields shown above. The clock supplies exact UTC timestamps of the form `2026-11-01T12:02:00Z`.

The host must obtain current state and pins independently of the payer and publish coherent snapshots. A consistent but old set of host-supplied pins cannot reveal withheld updates. The service uses the supplied snapshot for each decision; it does not discover newer registry heads by itself.

SQLite records admitted invoice request hashes, unique input reservations and application-level attempts. Admission and reservations commit in a single transaction. Concurrent repeated requests for an invoice are idempotent, including after restart. Reusing an input for another invoice is blocked locally. Every retry is screened again against current host state: an earlier success does not bypass a newly accepted mark. Database or audit failures return a blocked result. If an admission committed immediately before an audit failure, its reservation can remain and the caller still receives no approval; retry through the same gate.

The stored admission is historical. A later rejection does not delete that history or release reservations. Reservation expiry, cancellation, settlement, invoice authentication, distributed deployment and administrative recovery are not implemented. A user with direct database/code access can bypass this prototype; it is not a tamper-proof financial system.

## Before handling real deposits

The missing production boundary is explicit: verify the actual Bitcoin transaction, recipient output, input set, value, confirmation policy, replacements and reorgs using a trusted node; bind that verified transaction to the invoice; atomically combine the current policy decision with the operator's credit/settlement system. Payer-declared inputs alone cannot authorize a deposit credit. This prototype therefore never credits funds.

A production operator also needs real reviewer enrollment, evidence custody, a current checkpoint distribution service, access control, operational monitoring, secure persistence and an independent security review. The synthetic clock and public demo keys must never be used as production authority.

The [observed Binance sample](OBSERVED_BITCOIN_TEST.md) remains a bounded low-level replay. A test confirms that substituting its ledger into the demo cannot borrow the demo's signed approvals: verification blocks. We have not issued synthetic approvals for a real allegation.

[Receiver code](../satotag/receiver.py) · [Adversarial and HTTP tests](../tests/test_receiver.py) · [Recorded local HTTP results](../examples/receiver_demo.json)
