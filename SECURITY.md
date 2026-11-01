# Security

## v0.2.1 key authority

The new `authorized-*` CLI and `satotag.keyring` enforce root-signed validity
windows, current revocations, distinct roles and pinned current manifests.
Legacy registry APIs remain low-level and do not enforce those controls.
See [KEY_AUTHORITY.md](docs/KEY_AUTHORITY.md) for persisted trust requirements,
conservative rejection of revoked historical signatures and recovery boundaries.
No production root has been created. Offline root custody is an operator duty;
all shipped keys are public test fixtures.

## v0.2 signed-registry boundary

See [the governance threat model](docs/GOVERNANCE.md). Cryptographic verification
does not establish theft, reviewer independence, trusted time, globally complete
history or legal protection. The demo keys are PUBLIC fixtures. Never use them
to approve real funds. Independent checkpoints are mandatory for screening.
A prior receipt cannot erase a later tag. This prototype is not unbreakable.

Version 0.1 is a local research prototype, not a production financial service.
It does not request private keys or send transactions. Use synthetic data only.

For issues involving forged input, incorrect exposure or browser injection,
include a minimal fictional reproduction and expected behaviour. Do not post
live credentials, victims' personal information or exploit details affecting
third-party systems. Use GitHub private vulnerability reporting if the owner
has enabled it; otherwise contact the repository owner before disclosing
sensitive details.

No supported production release or independent security audit is claimed.

