# Sato-tag

**Open-source Bitcoin provenance research: UTXO exposure tracking, signed case reports and root-authorized key lifecycles.**

[Try the demo](https://ummagumma1974.github.io/Sato-tag/) · [Research overview](https://ummagumma1974.github.io/Sato-tag/research.html) · [Download current source ZIP](https://github.com/ummagumma1974/Sato-tag/archive/refs/heads/main.zip) · [Public review challenge](https://github.com/ummagumma1974/Sato-tag/issues/3)

Synthetic, offline research prototype. MIT license. No token, wallet connection or Bitcoin consensus change. See the research overview for scope and reproducible checks.


SatoTag started with a question I still can’t get my head around.

Someone steals, moves, splits, mixes. A trail remains. Then what? Who accepts that money? How do they spend it?

That’s where the idea came from: let’s try “stamping” the origin of the funds and see what happens as they move.

We’ve built a demo using made-up data. You can split funds, combine them with others, see how much of the total is flagged, and what changes when a report is revoked. You can also simulate a discount on that flagged portion.

For now, it’s a laboratory. It doesn’t freeze bitcoin or decide what it’s actually worth.

But the tricky part comes straight away: who applies the stamp? Based on what evidence? And what if they get it wrong?

I want to understand whether this idea can work without giving someone the power to decide which bitcoin has value and which doesn’t. Otherwise, we’re back to fiat money.

That’s what the code is for: putting the idea on the table and trying to break it.

Let’s see where it holds up.

---

## Try it

**[Open the live demo](https://ummagumma1974.github.io/Sato-tag/)**

Works in your browser, including on a phone. No downloads or wallet connection required. All scenarios use fictional data.


- [Usage guide](GUIDE.md)
- [Downloadable offline demo](docs/index.html)
- [Python source](satotag/engine.py)


## v0.2 — Signed registry

The prototype now verifies Ed25519 attestations, a reviewer quorum, hash-linked
case history and signed payment-check receipts. Late signals trigger manual
review; an earlier receipt never removes a tag or grants automatic immunity.
Verifier-selected trust keys and an independently obtained latest checkpoint
are required. The public demo uses deliberately public test keys and fictional
evidence. Signatures do not prove theft or reviewer independence.

[Protocol, limitations and adversarial tests](docs/GOVERNANCE.md)

```bash
python -m pip install -e ".[governance]"
python -m unittest discover -s tests -v
python tools/build_demo.py --check
```

## v0.2.1 — Key authorization

Root-signed key lifetimes, irreversible revocation checks and replacement by a
pre-enrolled reserve are now available through `satotag.keyring` and the
`authorized-screen` / `authorized-verify` commands. They require an independently
pinned root public key and current manifest hash, in addition to the registry
checkpoint. Legacy APIs do not enforce key lifecycles.

[Protocol, integration and reproducible example](docs/KEY_AUTHORITY.md).

## Evidence review — executable experimental gate

`evidence-screen` now checks evidence bytes, a case-bound dossier, five mandatory signed assessments, conflicts and separately enrolled reviewer identities/organizations before returning a payment-screening result. Missing evidence or an unresolved assessment stops this path. Each acceptance needs its own reviews.

[Investigation procedure, limitations and runnable example](docs/EVIDENCE_REVIEW.md) · [Synthetic dossier](examples/evidence_review.json) · [Demo evidence checks](https://ummagumma1974.github.io/Sato-tag/#evidence-review)

This authenticates structured assessments, not the truth of an allegation. Real investigators must verify records and independence. Existing low-level screening and receipt APIs do not enforce the evidence gate. No real theft investigation or Bitcoin spending restriction is implemented.

## First observed Bitcoin replay

[Read the reproducible transaction test](docs/OBSERVED_BITCOIN_TEST.md): a captured 1,409.5 BTC input splits into 1,000 BTC, 409.499995 BTC and a 500-satoshi fee. Conditional propagation, sibling isolation and pending/revoked controls pass. This is one explorer-derived replay, not an approved real-world claim or a full incident trace.

```sh
python -m tools.replay_binance_sample --check
```
