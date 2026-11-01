# Persistent marking: research proposal, not implemented consensus

## Intended question

Can a theft finding attach a persistent, correctable provenance mark to funds,
despite changes of address and ownership, without granting an arbitrary power
to confiscate value or contaminating unrelated funds?

The code in this repository tests **accounting consequences** on a complete,
invented UTXO graph. Its output is an external report. It is not a BIP, a fork,
a deployed smart contract, a node patch, or a generally accepted blacklist.

## Two different kinds of effect

1. **A buyer's valuation policy** can discount exposure. The buyer can also
   ignore it, and a willing intermediary can still acquire the funds. This
   policy cannot impose a universal 50–60% price loss.
2. **A consensus spending restriction** would change which transactions nodes
   accept. To make a mark unavoidable, a separate experimental protocol would
   have to define an attestation format, authorized updates, inheritance rules,
   revocations and validation. Adoption cannot be achieved by this Python app.

Burning or confiscating a fraction is a change to spendable quantity, not a
guaranteed change in market price. The demo implements neither.

## Open protocol decisions

- Who is allowed to attest a theft, with which evidence and appeal process?
- Can independent authorities disagree? How are competing decisions resolved?
- How is a mistaken mark reversed without rewriting old transactions?
- What allocation rule applies after multiple inputs are combined? Proportional,
  FIFO and boolean poisoning give different results; Bitcoin supplies no legal
  ownership answer for the original satoshis.
- How are fees and subsequent miner payouts handled without poisoning issuance?
- What happens when a thief trades a marked asset to an innocent party for a
  different asset? A mark alone does not identify the thief's new holdings.
- How are reorgs, finality, database availability and unbounded ancestry handled?
- Could an attacker use tiny transfers or false claims to censor others?
- Does the system reduce crime proceeds more than it harms legitimate holders?

## Next bounded experiment

Build a regtest-only, read-only importer with explicit reorg invalidation and
signed case attestations. Compare allocation policies and measure error cases.
Only after independent review should a **separate private research chain** be
considered for a validator-level mark rule. Do not market the present prototype
as Bitcoin theft prevention or guaranteed permanent taint across all systems.
