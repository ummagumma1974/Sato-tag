# SatoTag TRACE — independent two-hop Bitcoin Core challenge (7 November 2026)

**Purpose:** Ask an independent reviewer to falsify TRACE's outpoint graph against a fully validating Bitcoin Core node. This is not an allegation of theft, an attribution of wallet ownership, or an independent audit.

**Code baseline:** [`edec065da45d3405f596dcaa00968b40050eaf16`](https://github.com/ummagumma1974/Sato-tag/tree/edec065da45d3405f596dcaa00968b40050eaf16). [TRACE browser](https://ummagumma1974.github.io/Sato-tag/trace.html) · [Implementation](trace.html) · [Original one-edge replay](OBSERVED_BITCOIN_TEST.md).

## One verified edge (bounded, observed-data baseline)

- Parent TXID: `5de2320e6c53e925d135e887096b06145ef35ad04ed0e59b09fc205d7c47f0ba`, outpoint `:0`, 140,950,000,000 sat.
- Spending TXID: `07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6` (one input, referring to parent `:0`).
- Spending outputs: `:0` 40,949,999,500 sat and `:1` 100,000,000,000 sat; fee 500 sat.
- Conservation: `40,949,999,500 + 100,000,000,000 + 500 = 140,950,000,000` sat.
- Both transaction records in the preserved fixture report block height `973732`. The parent also has an independent sibling output `:1`, which is **not** seeded in the conditional example.
- This one-edge relation, the amounts and fee were recomputed from committed captured explorer JSON on 7 November 2026; they are not independently revalidated against a Bitcoin Core node here. Public [mempool.space spending transaction](https://mempool.space/tx/07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6) and [Trezor parent transaction](https://bitcoin.prod.gke.papers.tech/tx/5de2320e6c53e925d135e887096b06145ef35ad04ed0e59b09fc205d7c47f0ba) provide external comparison.

## Challenge A — verify the first edge against Bitcoin Core

On an archival or otherwise block-available, fully validating **mainnet** Bitcoin Core node:

```sh
PARENT=5de2320e6c53e925d135e887096b06145ef35ad04ed0e59b09fc205d7c47f0ba
CHILD=07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6
HASH=$(bitcoin-cli getblockhash 973732)
bitcoin-cli getblock "$HASH" 2 > block-973732.json
python - <<'PY'
import json
from decimal import Decimal
from pathlib import Path
j = json.loads(Path("block-973732.json").read_text(), parse_float=Decimal)
p = "5de2320e6c53e925d135e887096b06145ef35ad04ed0e59b09fc205d7c47f0ba"
c = "07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6"
d = {t["txid"]: t for t in j["tx"]}
assert p in d and c in d, "One or both transactions absent from block"
parent, child = d[p], d[c]
assert len(child["vin"]) == 1
assert child["vin"][0]["txid"] == p and child["vin"][0]["vout"] == 0
sat = lambda x: int(Decimal(x) * 100000000)
assert sat(parent["vout"][0]["value"]) == 140950000000
assert [sat(v["value"]) for v in child["vout"]] == [40949999500, 100000000000]
assert sat(parent["vout"][0]["value"]) - sum(sat(v["value"]) for v in child["vout"]) == 500
print("PASS: first edge, amount conservation, same confirmed block")
PY
```

If Core is pruned and the block is unavailable, record this as an **unperformed check**, not a pass. The comparison must use the node's own validated chain; a block downloaded from the same explorer is **not** independent verification.

## Challenge B — a genuinely observed second spend, not a guess

1. Open TRACE, enter the *child* TXID `07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6` and select output `:0` (repeat independently for `:1` if useful). Choose depth **2**, export the JSON and record UTC observation time.
2. If that output is spent, record the **actual** next spending TXID given by the explorer; do **not** invent one. On an archival `txindex=1` node, run `bitcoin-cli getrawtransaction NEXT_TXID true` or retrieve its containing block by height, and verify that at least one input spends the exact child `TXID:VOUT`. If no next spend exists, report “unspent according to the queried explorer at observation time” and stop; there is no claimed second edge.
3. Compare **all** observed input counts and output values, confirmation state and whether the export explicitly reports **multi-input ambiguity, depth/node limit or incomplete API coverage**. A many-input transaction must not be represented as unique ownership or a provably inherited stolen amount.
4. If a different source or Core disagrees, preserve the conflicting response, the block hash and height, time of observation, exact starting outpoint, and reproduction steps. An ordinary mempool/reorg difference must be distinguished from a bug.

**Decision criteria:** PASS only for matching, independently confirmed outpoint edges and honest uncertainty flags. FAIL if a nonexistent edge is asserted, an input is mislinked, partial coverage is presented as complete, or multi-input ownership/taint is claimed as fact. Otherwise report **INCONCLUSIVE** and why.

## Deliverable for independent reviewer

Provide: Bitcoin Core version, network, block hash/height, selected starting outpoint, observed next-spend TXID if any, exported JSON, expected vs actual, and a concise verdict. Redact personal wallet data. No secrets, seeds, victim identities, or unverified allegations.

**Current status:** The first edge was rechecked against our preserved explorer capture and publicly displayed transaction amounts. **No independent Core-node two-hop verification or external reviewer verdict has been obtained.** TRACE relies on explorer data and uses no proprietary chain forensics.
