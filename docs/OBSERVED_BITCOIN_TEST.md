# First observed Bitcoin transaction replay

**Result: PASS for one bounded, conditional propagation test.**

On 1 November 2026, SatoTag replayed an observed transaction pair using captured mempool.space API responses. This replaces invented transaction amounts with observed Bitcoin data for this specific test. The underlying engine still runs in simulation mode. No production claim was approved and no Bitcoin was changed.

## Observed path

Parent transaction: [5de232…f0ba](https://mempool.space/tx/5de2320e6c53e925d135e887096b06145ef35ad04ed0e59b09fc205d7c47f0ba), output **0**.

Immediate spend: [07f4a6…3eb6](https://mempool.space/tx/07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6).

Both explorer records report confirmation in block **973732**.

| Component | BTC | Satoshis | Conditional model result |
|---|---:|---:|---|
| Selected parent output | 1,409.5 | 140,950,000,000 | Seed, assumed accepted for this experiment |
| Child output 0 | 409.499995 | 40,949,999,500 | 100% exposure to that seed |
| Child output 1 | 1,000 | 100,000,000,000 | 100% exposure to that seed |
| Child transaction fee | 0.000005 | 500 | Exposure leaves the bounded model as a fee |
| Other parent output | 3.62320176 | 362,320,176 | Unmarked by this seed; not a certificate of lawful origin |

The child spends exactly the selected parent output, with no additional input. Output values plus its 500-satoshi fee equal the selected input exactly. Parent transaction input/output conservation is also checked against the explorer response, but its earlier inputs are not replayed by the engine.

The child output 1 address, `bc1qxrxujwxfnvz040jw76d26zhjdg5jura7hs968s`, appears in the [FBI advisory dated 31 October 2026](https://www.fbi.gov/investigate/cyber/alerts/2026/north-korea-responsible-for-6-billion-binance-attack) concerning the Binance incident. That is external attribution. The parent-to-child relationship is obtained separately from transaction records. SatoTag has not independently adjudicated the alleged theft or identified the people controlling an address.

## What passed

- Captured source-byte hashes match the manifest.
- Child input outpoint and previous-output metadata match the actual parent output in the captured responses.
- Exact output amounts, fee and value conservation match.
- Under the explicit accepted-seed assumption, both child outputs inherit exposure and the sibling parent output does not.
- With the case changed to **pending**, no exposure propagates.
- With the case changed to **revoked**, no exposure propagates.
- Exposure is conserved including fees. No haircut or market-price assumption is applied (`haircut_percent = 0`).

## What this does not prove

This is **one split**, not a reconstruction of all stolen funds. It has no mixed inputs, cross-chain movement or privacy boundary and cannot demonstrate performance on those cases. A successful replay does not show that a persistent mark exists on Bitcoin.

Explorer JSON is trusted as input here. The script does not hash raw Bitcoin transaction serialization, validate Merkle inclusion or run Bitcoin consensus validation. Captured SHA-256 hashes protect reproducibility, not source authenticity. No current outspend lookup is performed: `unspent` in the engine report means a terminal output in this small graph, **not its spending status on Bitcoin today**.

The original accepted case is deliberately a **what-if assumption in the low-level engine**. The real-case evidence gate is **not approved**: no independently enrolled human reviewers or signed assessments for this case were supplied. Public demo keys cannot turn this experiment into an independently approved real-world claim. No registry events for this real case have been published.

## Reproduce offline

```sh
python -m tools.replay_binance_sample --check
```

No network access, wallet, credentials or money is needed. Run without `--check` to regenerate the derived dataset and reports from the preserved responses.

[Captured responses, source manifest, dataset and results](../examples/binance_2026_10_29/) · [Replay script](../tools/replay_binance_sample.py)

The next meaningful test is a longer bounded transaction graph with mixed inputs and explicit stopping rules, compared with an independent source or a fully validating node. Evidence review remains a separate human-dependent requirement.
