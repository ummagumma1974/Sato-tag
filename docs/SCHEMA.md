# Data contract v1

Only `network: "simulation"` is accepted. Identifiers are synthetic ASCII names
matching `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`; they are not real Bitcoin transaction hashes.
Unknown object fields are rejected to catch typos. Missing inputs are an error,
never a reason to infer a clean origin. The input is never mutated.

```json
{
  "schema_version": 1,
  "network": "simulation",
  "name": "Minimal example",
  "transactions": [
    {"txid": "origin", "inputs": [], "outputs": [{"value_sats": 100000000}]},
    {"txid": "payment", "inputs": [{"txid": "origin", "vout": 0}],
     "outputs": [{"value_sats": 99999000}]}
  ],
  "cases": [{
    "case_id": "DEMO-001",
    "status": "accepted",
    "seeds": [{"txid": "origin", "vout": 0}],
    "evidence": [{"reference": "urn:synthetic:demo", "description": "Fictional demonstration only"}]
  }]
}
```

Dataset `name` and `description`, transaction `label`, output `label`, and case
`note` are optional strings. `inputs: []` declares synthetic opening funds; it
does not verify a coinbase transaction. Each transaction must have at least one
output; zero-valued outputs are allowed and carry no exposure. Satoshi values
must be non-negative integers, not floats or booleans. Origins combined may not
exceed 21 million BTC. Outputs may not exceed inputs. The difference is a fee.

A seed marks a full positive output; partial seeds are not supported. Accepted
seeds may not overlap on the same output or on its already-marked descendants.
This restriction prevents double counting; real overlapping claims require a
future attribution/reconciliation layer. Pending and revoked cases remain in
the report and do not create active exposure.

Each case requires at least one evidence object containing a non-empty
`reference` and `description`. An optional lowercase hex `sha256` can identify
an external evidence artifact. The engine checks syntax only: it does not fetch
the artifact, validate the digest against its bytes, or verify the claim.

## Report

- `dataset_sha256`: SHA-256 of sorted-key compact JSON input. Reordering arrays
  changes the fingerprint; reordering transaction rows does not change the
  calculated outputs. This hash is not an authentication signature.
- `outputs`: every output, its amount, whether it has been spent, active case
  IDs, exact exposure, and hypothetical valuation.
- `mark`: `seed`, `inherited`, or `none`. `none` means unmarked in this supplied
  model, not legally clean. A tiny nonzero exposure keeps the inherited mark.
- `exposure_percent`: rounded display convenience, not a probability.
- `exposure_sats`: exact rational `{"numerator":"…","denominator":"…"}`.
  String fields avoid JSON integer precision problems across languages.
- `fees`: fee values and attributed exposure that leave the model's perimeter.
- `totals`: counts only unspent outputs; historical outputs are not counted again.
- `hypothetical_quote_sats_equivalent`: a model value, never a spendable balance.
- `cases`, `limitations`: the input registry and explicit interpretation limits.

The engine guarantees:

```text
origin value = unspent value + all fees
active seeded exposure = unspent exposure + exposure attributed to fees
0 <= exposure of each output <= output value
```

Limits: 4 MiB CLI input, 10,000 transactions, 50,000 outputs, 100 cases, 20
evidence objects per case. Exact fraction growth is bounded to 4,096 bits per
propagated case amount. Large, hostile graphs should be processed with external
CPU/memory limits; this is not an untrusted public API service.
