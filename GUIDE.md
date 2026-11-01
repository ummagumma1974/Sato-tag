# SatoTag usage guide

**Anti-theft marks for satoshis — an idea to test.**

SatoTag is an offline research prototype that follows provenance marks through
an **invented** transaction graph. It includes a dependency-free accounting
engine, an interactive browser demo and automated tests. Signature verification
uses the optional governance dependency.

> **Status: proof of concept, v0.2.1.** The prototype does not modify Bitcoin,
> freeze funds, verify real thefts or enforce price discounts. All examples use
> synthetic funds and publicly derivable demonstration signing keys.

## Signed registry and key authorization

The live demo includes Ed25519 signatures, reviewer quorum, challenges,
revocations and payment-bound check receipts. The original `analyze` command
uses caller-declared case statuses; `satotag.registry.replay` reconstructs
states from signed events. The browser displays reports verified by Python
at build time; it does not verify user-uploaded signatures.

The v0.2.1 `satotag.keyring` layer adds root-authorized key activation, expiry,
revocation and replacement by an enrolled reserve. Use `authorized-screen` and
`authorized-verify` to enforce these controls. Legacy registry commands do not
enforce key lifecycles. Independently current registry and manifest checkpoints,
trusted acceptance time and protected verifier state remain integration duties.

Install the optional signature support for the registry, all tests and builds:

```sh
python -m pip install -e ".[governance]"
```

Read the [signed registry specification](docs/GOVERNANCE.md) and
[key authority specification](docs/KEY_AUTHORITY.md). Signatures identify keys;
they do not establish the truth of an allegation or reviewer independence.

## Try it now

Open the **[live demo](https://ummagumma1974.github.io/Sato-tag/)**. No account,
download or wallet connection is required. All project pages are in English.

For offline use, download the source repository and open
[docs/index.html](docs/index.html) in a browser. The demo is a self-contained
HTML file and works on a phone. GitHub's file viewer displays HTML source;
open the downloaded file in a browser or serve it locally to interact with it.

With Python 3.11 or later, run these commands from the project directory:

```sh
python -m satotag analyze examples/split.json
python -m satotag analyze examples/mixed.json --haircut 60 --output report.json
python -m unittest discover -s tests -v
```

The `analyze` command needs no additional packages. The full test suite and demo
build require the optional signature support above. Some systems use `python3`.

To serve the demo locally:

```sh
python -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Open `http://127.0.0.1:8000` on the same device. Another phone cannot access that
loopback address; the server remains local.

## Implemented behavior

| Component | Actual behavior |
| --- | --- |
| Case records | Declared evidence, seed outputs and case status |
| Propagation engine | Keeps references to active cases on descendant outputs |
| Proportional attribution | A small marked share does not label the whole balance as stolen |
| Exact accounting | Rational fractions preserve small exposures without rounding them away |
| Validation | Rejects missing inputs, double spends, cycles, invalid values and overlapping origins |
| Economic simulation | A hypothetical discount changes a quote, **never the balance** |
| Interactive demo | Four scenarios, selectable outputs, adjustable discount and JSON exports |
| Signed registry | Verifies signatures, quorum, linked history and payment-check receipts |
| Key authority | Checks root-signed operating-key lifecycles through the authorized entry points |
| Reproducibility | Dataset hashes, deterministic output, tests and GitHub Actions checks |

## The four experiments

1. **Split and transfer:** the mark survives multiple modeled transfers.
2. **Merge two origins:** one marked BTC plus four unmarked BTC in the dataset
   produces 20% modeled exposure rather than 100%.
3. **Small amounts:** 1,000 marked satoshis merged with one BTC remain visible
   without treating the entire BTC as stolen. Exposure stays proportional.
4. **Correction:** revocation removes the active effect on recalculation. The
   case stays in the report so the decision remains visible. Keeping earlier
   datasets in Git is a reviewer's choice, not a guaranteed audit log supplied
   by the accounting engine.

## How the mark works

An accepted case identifies one or more **whole outputs** as marked origins.
Each transaction allocates exposure in proportion to output values and fees.
The case reference remains even at very small exposure: there is no threshold
that silently clears it.

```text
E_output = E_input * output_value / total_input_value
E_fee    = E_input * fee / total_input_value
```

`E` is attributed accounting exposure, not a probability of guilt. Fractional
satoshis are exposure estimates only; transaction values stay integer satoshis.
The model does not identify every original satoshi. Bitcoin does not impose a
unique pairing of each input with each output in a merged transaction.

The demo defaults to a **60% discount on attributed exposure only**. An output
with a balance of 1 BTC and exposure of 0.2 BTC therefore has a hypothetical
quote equivalent to 0.88 BTC. Its spendable balance stays 1 BTC. Participants
can ignore this voluntary policy; the software neither enforces nor forecasts
a market price.

## What the prototype does not resolve

- **Evidence truth:** the accounting engine accepts `accepted` as an input
  assertion. The signed path authenticates keys and decisions, not the truth
  of evidence. A hash does not certify an accusation.
- **Real-chain validation:** there is no Bitcoin node, real transaction parser,
  Bitcoin signature validation, consensus, blocks, confirmations or reorg handling.
  The optional Ed25519 signatures belong to the external simulation registry.
- **Perimeter:** miner payments, coinbase transactions, cross-asset swaps,
  custodial intermediaries and unknown paths are not followed beyond the
  dataset. Fees are recorded as leaving its perimeter, not as laundered funds.
- **Uncertainty:** missing data is rejected. A synthetic origin is a declared
  starting point, not proof of lawful provenance. The engine neither estimates
  probabilities nor resolves ambiguous real-world associations.
- **Third-party protection:** exposure and guilt are distinct. The algorithm
  does not make legal decisions or automate seizures.
- **Network-wide persistence:** persistence is a simulation rule. Making marks
  mandatory on Bitcoin would require protocol changes and adoption. See the
  [protocol research proposal](docs/PROTOCOL_PROPOSAL.md).

Taint analysis and provenance screening already exist. SatoTag does not claim
to have invented them. This repository makes the rules, consequences and limits
of an experimental marking policy inspectable.

## Development and verification

```sh
python -m unittest discover -s tests -v
python tools/build_demo.py
python tools/build_demo.py --check
python -m tools.keyring_demo
python -m tools.keyring_demo --check
```

The demo embeds reports generated by the **same Python engine**, not a second
tracking implementation. The browser recalculates only the discount using
BigInt rational arithmetic. Display values are rounded; exported JSON keeps
exact fractions. The scenarios do not load data from the network.

The `Test SatoTag` workflow runs Python 3.11, 3.12 and 3.13, checks demo freshness
and verifies the key-authority fixture. Check the actual run results in GitHub;
a workflow file alone is not evidence that checks passed.

## File map

| Path | Contents |
| --- | --- |
| `satotag/engine.py` | Validation, graph ordering, exposure accounting and reports |
| `satotag/registry.py` | Signed registry, screening and check receipts |
| `satotag/keyring.py` | Root-authorized key lifecycles and update checks |
| `satotag/__main__.py` | CLI with readable errors and input limits |
| `examples/*.json` | Synthetic scenarios and reproducible signed fixtures |
| `tests/` | Accounting, registry, key-authority and CLI checks |
| `tools/build_demo.py` | Reproducible demo generation |
| `tools/demo_template.html` | English offline interface |
| `tools/keyring_demo.py` | Public-key authority fixture generator |
| `docs/index.html` | Ready-to-open interactive demo |
| `docs/research.html` | Public technical overview |
| `docs/SCHEMA.md` | Data format and report contract |
| `docs/THREAT_MODEL.md` | Threats and mitigation boundaries |
| `docs/PROTOCOL_PROPOSAL.md` | Requirements for a possible network-level mark |

## Next experiments

1. Independent review of attribution rules and tests.
2. Production designs for key custody, checkpoint distribution and recovery.
3. A **read-only** Bitcoin Core regtest importer with reorg handling.
4. A separate experimental protocol study with no claim to modify mainnet.
5. Measurement of false positives and third-party harm before any use with real funds.

## References

- [Bitcoin transactions and outputs](https://developer.bitcoin.org/devguide/transactions.html)
- [Bitcoin transaction format](https://developer.bitcoin.org/reference/transactions.html)
- [Chainalysis address screening](https://www.chainalysis.com/product/address-screening/)
- [Elliptic wallet and transaction screening](https://www.elliptic.co/products/lens/)

Original idea: ummagumma1974. Prototype code developed with AI assistance;
not independently audited. [MIT license](LICENSE).
