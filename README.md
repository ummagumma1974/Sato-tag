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
