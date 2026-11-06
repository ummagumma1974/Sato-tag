# SatoTag — product differentiation and evidence gate (2026-11-06)

## Product boundary
TRACE is a read-only Bitcoin transaction path explorer; SatoTag's signed case registry is a distinct experimental governance layer. Neither can freeze BTC, invalidate transactions, prove theft from a transaction graph, or reliably attribute ownership after CoinJoin or custodial transfers. Do not market either as those capabilities.

## What already exists
Public blockchain explorers, transaction-graph tools, and forensic tracing exist. Basic output-spend traversal and provenance flags are not a differentiator by themselves.

## Candidate product advantage to test
A **reproducible, source-pinned, uncertainty-aware evidence package** for investigators and incident responders: explicit start outpoint, timestamped raw sources, bounded paths, ambiguities, stop reasons, hash manifest, reproducibility instructions, and reviewer decisions with revocation history. This is a candidate positioning, not a novelty or commercial validation claim.

## Mandatory acceptance gates
1. At least 3 independent external technical reviewers reproduce the same report or provide falsifying cases.
2. Benchmark at least 10 publicly documented incidents/transactions with mixed-input and custodial stopping boundaries; use verified case sources, never assert theft from heuristics alone.
3. Test false-positive behavior on CoinJoin and shared-custody examples; distinguish observed edge from inferred ownership.
4. Demonstrate report portability and offline verification of captured evidence bytes.
5. Obtain explicit feedback from at least 3 prospective investigative/compliance users on whether the evidence export solves a paid problem.
6. Only then decide on commercial API, hosted service, or partnerships. Do not implement coercive payment blacklists or global taint claims as if Bitcoin consensus enforced them.

## Current verified scope
Repository has a synthetic registry, read-only TRACE, one observed transaction replay, and local receiver demo. No demonstrated theft prevention, universal wallet monitoring, guaranteed post-mix attribution, external adoption, or ability to render stolen BTC unspendable.

## Decision
Keep code and tests; stop adding publicity features until the above external validation gates are met. Separate TRACE product utility from SatoTag governance policy.

## Research caution
CoinJoin breaks simplistic multi-input ownership inference; see https://link.springer.com/article/10.1007/s12117-023-09505-1 .
