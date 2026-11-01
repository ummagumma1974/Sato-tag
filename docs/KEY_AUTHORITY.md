# Key authority — v0.2.1

SatoTag now has an optional, **enforced Python/CLI authorization layer** above
the low-level v0.2 registry. It uses Ed25519, not secret syntax or custom crypto.
A separately pinned root public key verifies a signed manifest that authorizes
the enrolled reviewer/checker keys and their validity windows. The root private
key is never loaded by this verifier. Keeping it offline is an operator custody
requirement, not something this library can enforce.

## What is implemented

- A strict, domain-separated root-signed manifest; unknown fields are rejected.
- Separate root, reviewer and checker keys: no shared public keys or role ids.
- Key activation/expiration, and irreversible revocation in adjacent updates.
- Current manifest hash pinning, in addition to the existing registry checkpoint.
- Manifest expiration (exclusive endpoint) and a maximum seven-day lifetime.
- Sequential update verification: sequence N+1, exact predecessor hash, no edits
  to established validity windows and no reactivation of revoked keys.
- Replacement by a previously enrolled reserve key, without changing the
  ledger's trust hash. Add new keys by creating a **new registry epoch** and
  explicitly migrating/reviewing history; arbitrary trust edits are rejected by
  `advance_manifest`. Automatic cross-epoch history migration is not implemented.
- Current revocation checks even for a previously signed receipt. A receipt must
  fit inside the checker's lifetime; issuance also caps it at manifest expiry.

There is no fallback from an authorization failure to the low-level API. The
legacy commands remain explicitly available for older fixtures and research;
**do not expose them as an alternative route in an authorization-enforcing
service**. A caller controlling its own program can always remove its own checks.
This layer governs what an honest verifier accepts, not Bitcoin consensus.

## Run the reproducible demonstration

Install `python -m pip install -e ".[governance]"`, then run:

```sh
python -m tools.keyring_demo
python -m unittest discover -s tests -v
python -m tools.keyring_demo --check
```

`examples/key_authority.json` contains a valid receipt, a root-signed checker
revocation, its rejection, and a valid replacement receipt signed by the reserve.
**Every private key used to produce this fixture is publicly derivable from
source. All data, times and identities are invented. Never trust the fixture's
root or operating keys for real claims.**

The CLI accepts separate JSON files for the bundle (`ledger`, `events`),
manifest envelope, receipt and payment. With those files and independently
obtained pins:

```sh
python -m satotag authorized-screen bundle.json \
  --manifest manifest.json --root-key ROOT_PUBLIC_KEY_HEX \
  --manifest-checkpoint LATEST_MANIFEST_SHA256 \
  --checkpoint LATEST_REGISTRY_HEAD --as-of ACTUAL_UTC_TIME \
  --payment payment.json

python -m satotag authorized-verify bundle.json \
  --manifest manifest.json --root-key ROOT_PUBLIC_KEY_HEX \
  --manifest-checkpoint LATEST_MANIFEST_SHA256 \
  --checkpoint LATEST_REGISTRY_HEAD --as-of ACTUAL_UTC_TIME \
  --receipt receipt.json --payment payment.json
```

The placeholders above are deliberately not supplied by an untrusted bundle.
`authorized_issue` takes a caller-held operating key object; no private key CLI
flag or key upload is provided. Root authorization signs
`manifest_bytes(payload)` externally. This is authorization by signature, not
encryption or wrapping of Bitcoin wallet keys.

## Integration and persisted trust

Use `satotag.keyring.authorized_screen`, `authorized_issue`, and
`authorized_verify`. Do not pass attacker-provided values for root, latest
manifest hash, registry checkpoint or current time. Reject errors; never map
an exception to “no known mark”. The verifier checks the complete supplied log
before checking historical key validity. Expiry preserves events signed during
validity; **revocation conservatively rejects any supplied history containing
that key**, including old entries, and requires manual recovery. It never
silently deletes an event or clears a tag.

For an update, call `advance_manifest(trusted_previous, proposed_successor,
root_public_key, now)`. The previous envelope must come from verifier-owned
persistent state. A successful result must be atomically persisted together
with its digest before accepting operations. Protect this state from rollback.
The function does not implement a disk database, multi-process locking or an
authenticated distribution service. If the older manifest has expired, a valid
adjacent successor can still recover it. Both signatures are checked.

A pin to a known current manifest rejects a stale manifest. A pin that is itself
stale cannot reveal a withheld newer revocation. Expiration limits the stale
window but does not eliminate it. Initial installation, pin distribution and
trusted time remain integration requirements. The seven-day cap is an upper
bound, not a recommended operational revocation delay.

## Threats checked and boundaries

| Attempt | Implemented outcome |
| --- | --- |
| Change an authorization without the root signature | Reject |
| Supply an authorization signed by another root | Reject against pinned root |
| Hide a revocation using old metadata | Reject against independently current hash |
| Use a checker before activation or at/after expiry | Reject |
| Verify an old receipt after its checker is revoked | Reject; manual recovery |
| Replace a checker with a reserve | Accept only within its authorized window |
| Reuse a reviewer key as checker or root | Reject |
| Extend an existing certificate in a sequential update | Reject; enroll a new key/epoch |
| Rewrite, skip or roll back an update | Reject against persisted predecessor |
| Steal the offline root | Not solved; root recovery/rotation is not implemented |
| Backdate an event with a once-valid key | No trusted timestamp proof; retain independent checkpoints |
| Revoke a historical reviewer to cause denial of service | Fail closed; recovery must preserve/review prior evidence |
| Compromise the executing verifier or replace its code/pins | Outside this library's enforcement boundary |

The design borrows well-established separation, expiry and versioning ideas
from [The Update Framework metadata model](https://theupdateframework.io/docs/metadata/).
It is a small research protocol; it is **not a TUF implementation**, an audited
PKI, a hardware keystore, or an on-chain enforcement mechanism. Root rotation,
threshold root custody, durable replay protection and independent evidence
adjudication remain future work. Operational reviewer quorum remains required.
