# SatoTag TRACE — public technical review invitation

**SatoTag TRACE v0.2** is an experimental, wallet-agnostic, read-only Bitcoin UTXO path explorer. It accepts a public Bitcoin mainnet TXID or single address from any wallet. It does not use seed phrases, private keys, xpubs, wallet connections or transaction signing.

- [Try the live explorer](https://ummagumma1974.github.io/Sato-tag/trace.html)
- [Inspect the standalone implementation](trace.html)
- [Original governance review challenge](https://github.com/ummagumma1974/Sato-tag/issues/3)

## Scope and limitations

The browser retrieves observed Bitcoin transactions and output spend status from mempool.space's public API. A user chooses an output and TRACE follows its spending transaction's outputs for one to three hops, with at most 70 output nodes. A multiple-input transaction is marked ambiguous. An address search shows outgoing transactions for one address only; it cannot find the entire wallet.

Explorer input is not validated independently. A transaction graph does not prove ownership, criminality, theft, provenance after CoinJoin, movements within a custodial exchange, or cross-chain destinations. The browser sends queried TXIDs and addresses to the public API. There is no independent security review and no guarantee that every descendant was found.

## Reproducible review procedure

1. Open the [live tool](https://ummagumma1974.github.io/Sato-tag/trace.html), or locally serve the repository's docs directory with: python -m http.server 8000 --bind 127.0.0.1 --directory docs
2. Select TXID and load the bundled research example: 07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6. This is an observed transaction in a bounded fixture, **not a certified theft**.
3. Choose a particular output, follow up to two spending hops, then export the JSON report.
4. Compare transaction IDs, outpoints, input counts, values and spending status with an independent explorer or ideally a Bitcoin Core node.
5. Record the exact starting outpoint, Git commit, browser and OS, observed behavior, expected behavior and API errors. Avoid posting wallet secrets or personal identifying information.

## Specific technical questions for reviewers

- Can a displayed path be mistaken for unique ownership after a multi-input transaction?
- Are unconfirmed/reorganized transactions, missing history, depth limits or API rate limits disclosed clearly enough?
- Can huge fan-out or concurrent searches freeze the UI, mislead the user or leave an unmarked partial report?
- Does address pagination miss a relevant payment?
- Can the export be independently reproduced, or should it store block height, API response hashes and observation time?
- Does the browser code contain an injection, privacy, or unwanted-network-request problem?
- What would it take to validate the tracer against a fully validating Bitcoin Core node?

## Finding template

- Commit:
- Browser / OS:
- Synthetic example or public TXID:VOUT:
- Reproduction steps:
- Expected:
- Actual:
- Supporting evidence:
- Assumptions changed:

Open a dedicated GitHub issue with a minimal reproducible finding; code-review pull requests are welcome.

## Outreach and ethics

Invite technical criticism, not endorsements or upvotes. Only share in channels where self-submitted open-source research is permitted. Do not mass-mention contributors or post advertisements in unrelated issues. Never publish an accusation about a holder based solely on address similarity or modeled exposure.

**Short description for communities allowing project announcements:**

SatoTag TRACE is an open-source, read-only Bitcoin transaction-path browser. Start with a public TXID or address, inspect observed outspends and explore bounded successor paths. It explicitly labels ambiguous branches from multi-input transactions and does not claim to identify owners or stolen funds through mixing. We invite reproducible counterexamples, privacy critiques and adversarial UI review: https://ummagumma1974.github.io/Sato-tag/trace.html

**Hacker News:** the rules require human-written, non-automated submissions; the creator should post in their own words and be available for discussion. Do not use generated copy there. **Reddit:** verify each community's self-promotion rules first. **Bitcoin-dev:** not for generic product advertising; reserve it for substantive protocol research.
