# Threat model

This prototype operates on local, synthetic input. A caller controls the whole
dataset. There is no authentication, trusted adjudicator, peer consensus,
tamper-proof log, wallet, network client, or transaction signer.

| Risk | Current behaviour / remaining work |
|---|---|
| False allegation | Evidence is required structurally but not verified. Never treat a demo report as an accusation. A deployed registry needs independent review, appeals and accountable attestors. |
| Dust poisoning | Track proportional exposure separately from the inherited case marker. Do not label a whole wallet guilty. A boolean block policy would reintroduce this vulnerability. |
| Dilution by repeated merging | Exact fractions prevent rounding away the exposure marker. Quantity can become tiny; that is not proof of innocence or guilt. |
| Model-dependent attribution | No claim of uniquely identifying original satoshis. Proportional allocation can expose innocent recipients and must not be treated as an objective legal allocation. |
| Duplicate claims | Reject overlapping active seed outputs, including seeded descendants, rather than inflate exposure. |
| Missing history | Fail on omitted referenced inputs. Opening funds remain caller assumptions. |
| Cross-asset swaps | Do not automatically transfer a BTC mark to an unrelated asset. The BTC may now be held by an innocent counterparty; ownership/control attribution is a separate problem. |
| Fee laundering boundary | Record attributed fees as an explicit exit, not as clean funds. Miner coinbase payouts are not traced. |
| Reorganizations | Not implemented. All input graph edges are hypothetical. |
| Wrong adjudication | Recompute after a revocation and retain the case in the report. External version history and signed revocations are future work. |
| Malicious JSON | Strict field/type checks, duplicate-key rejection in CLI, graph validation, bounded input and fraction growth. No external URLs are fetched. |
| Browser injection | Demo strings use textContent; embedded JSON escapes `<`. The demo has no upload form or remote script dependencies. |
| Misleading valuation | Hypothetical discount shown separately from the balance. Export keeps exact rational arithmetic. No claim of a market price or universal enforcement. |

Do not deploy this as a mainnet enforcement or financial decision service.
Testing validates internal consistency, not the truth of claims or the economic
and governance merits of coin marking.
