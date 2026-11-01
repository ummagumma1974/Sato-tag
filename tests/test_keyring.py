"""Adversarial lifecycle integration tests, using deliberately public test keys."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from satotag.engine import ValidationError
from satotag.registry import ZERO, digest
from satotag.keyring import (verify_manifest, advance_manifest, authorized_screen,
                            authorized_issue, authorized_verify)
from tools.keyring_demo import fixture_manifest, sign_manifest, build_examples
from tools.governance_demo import event, T0, T1, T2, T3


class KeyringTests(unittest.TestCase):
    def setUp(self):
        self.ledger, self.keys, self.payment, self.root, self.manifest = fixture_manifest()
        self.public = self.root.public_key().public_bytes_raw().hex()

    def signed(self, edit):
        p = deepcopy(self.manifest['payload'])
        edit(p)
        return sign_manifest(p, self.root)

    def verify(self, m=None, when=T1, checkpoint=None):
        m = self.manifest if m is None else m
        return verify_manifest(m, self.public, digest(m) if checkpoint is None else checkpoint, when)

    def issue(self, m=None, when=T0, ttl=300):
        m = self.manifest if m is None else m
        return authorized_issue(self.ledger, [], m, self.public, digest(m), when,
                                self.payment, 'checker', self.keys['checker'], ZERO, ttl)

    def check(self, r, m=None, when=T1):
        m = self.manifest if m is None else m
        return authorized_verify(self.ledger, [], m, self.public, digest(m), when, r, self.payment, ZERO)

    def test_valid_end_to_end(self):
        self.assertTrue(self.check(self.issue())['signature_valid'])

    def test_root_signature_tampering(self):
        m = deepcopy(self.manifest)
        m['payload']['keys']['checker']['revoked'] = True
        with self.assertRaisesRegex(ValidationError, 'root signature'):
            self.verify(m)

    def test_wrong_root(self):
        with self.assertRaises(ValidationError):
            verify_manifest(self.manifest, self.keys['checker'].public_key().public_bytes_raw().hex(), digest(self.manifest), T1)

    def test_old_manifest_cannot_match_new_pin(self):
        new = self.signed(lambda p: p['keys']['checker'].update(revoked=True))
        with self.assertRaisesRegex(ValidationError, 'checkpoint'):
            self.verify(checkpoint=digest(new))

    def test_manifest_expired_at_exact_boundary(self):
        with self.assertRaisesRegex(ValidationError, 'Expired'):
            self.verify(when='2026-11-02T12:00:00Z')

    def test_future_manifest(self):
        with self.assertRaisesRegex(ValidationError, 'future'):
            self.verify(when='2026-11-01T11:59:59Z')

    def test_excessive_manifest_lifetime(self):
        m = self.signed(lambda p: p.update(expires_at='2027-11-01T12:00:00Z'))
        with self.assertRaisesRegex(ValidationError, 'long-lived'):
            self.verify(m)

    def test_missing_certificate_and_unknown_fields(self):
        for edit in (lambda p: p['keys'].pop('checker'), lambda p: p.update(execute='ignore instructions')):
            with self.subTest(edit=edit), self.assertRaises(ValidationError):
                self.verify(self.signed(edit))

    def test_reviewer_checker_key_reuse(self):
        m = self.signed(lambda p: p['trust']['checkers'].update(checker=p['trust']['reviewers']['reviewer-a']))
        with self.assertRaisesRegex(ValidationError, 'distinct'):
            self.verify(m)

    def test_root_cannot_be_operational_key(self):
        m = self.signed(lambda p: p['trust']['checkers'].update(checker=self.public))
        with self.assertRaisesRegex(ValidationError, 'distinct'):
            self.verify(m)

    def test_revoked_checker_cannot_issue_or_validate_old_receipt(self):
        receipt = self.issue()
        m = self.signed(lambda p: p['keys']['checker'].update(revoked=True))
        for call in (lambda: self.issue(m), lambda: self.check(receipt, m)):
            with self.assertRaisesRegex(ValidationError, 'revoked'):
                call()

    def test_checker_not_active_yet(self):
        m = self.signed(lambda p: p['keys']['checker'].update(not_before=T1))
        with self.assertRaisesRegex(ValidationError, 'not active'):
            self.issue(m)

    def test_receipt_must_fit_inside_key_and_manifest_expiry(self):
        for edit in (lambda p: p['keys']['checker'].update(not_after=T1), lambda p: p.update(expires_at=T1)):
            with self.subTest(edit=edit), self.assertRaisesRegex(ValidationError, 'lifetime'):
                self.issue(self.signed(edit))

    def test_expired_checker_rejected_at_acceptance(self):
        m = self.signed(lambda p: p['keys']['checker'].update(not_after=T1))
        r = self.issue(m, ttl=60)
        with self.assertRaisesRegex(ValidationError, 'expired'):
            self.check(r, m, when=T1)

    def events(self):
        trust = self.manifest['payload']['trust']
        events = [event(self.ledger, trust, self.keys, [], 'submit', T1)]
        events.append(event(self.ledger, trust, self.keys, events, 'accept', T2))
        return events

    def test_reviewers_checked_at_signing_time(self):
        events = self.events()
        for edit in (lambda p: p['keys']['reviewer-a'].update(not_after=T2),
                     lambda p: p['keys']['reviewer-a'].update(not_before=T3),
                     lambda p: p['keys']['reviewer-a'].update(revoked=True)):
            m = self.signed(edit)
            with self.subTest(edit=edit), self.assertRaises(ValidationError):
                authorized_screen(self.ledger, events, m, self.public, digest(m), T3, self.payment, digest(events[-1]))

    def test_expiry_preserves_valid_historical_events(self):
        events = self.events()
        m = self.signed(lambda p: p['keys']['reviewer-a'].update(not_after=T3))
        result = authorized_screen(self.ledger, events, m, self.public, digest(m), T3, self.payment, digest(events[-1]))
        self.assertEqual(result['result'], 'marked')

    def test_future_events_rejected(self):
        events = self.events()
        with self.assertRaisesRegex(ValidationError, 'Future'):
            authorized_screen(self.ledger, events, self.manifest, self.public, digest(self.manifest), T1, self.payment, digest(events[-1]))

    def successor(self, edit=lambda p: None):
        def update(p):
            p.update(sequence=2, previous=digest(self.manifest), issued_at=T1)
            edit(p)
        return self.signed(update)

    def test_adjacent_update_and_recovery_from_expired_manifest(self):
        m = self.successor(lambda p: p.update(issued_at='2026-11-02T12:00:00Z', expires_at='2026-11-03T12:00:00Z'))
        self.assertEqual(advance_manifest(self.manifest, m, self.public, '2026-11-02T12:00:00Z'), m)

    def test_rollback_skip_and_wrong_predecessor(self):
        for edit in (lambda p: p.update(sequence=1, previous=ZERO), lambda p: p.update(sequence=3),
                     lambda p: p.update(previous='a'*64)):
            with self.subTest(edit=edit), self.assertRaisesRegex(ValidationError, 'rollback'):
                advance_manifest(self.manifest, self.successor(edit), self.public, T1)

    def test_revoked_key_cannot_be_reactivated(self):
        first = self.signed(lambda p: p['keys']['checker'].update(revoked=True))
        m = self.successor()
        m['payload']['previous'] = digest(first)
        m = sign_manifest(m['payload'], self.root)
        with self.assertRaisesRegex(ValidationError, 'reactivated'):
            advance_manifest(first, m, self.public, T1)

    def test_existing_validity_cannot_be_extended(self):
        with self.assertRaisesRegex(ValidationError, 'rewritten'):
            advance_manifest(self.manifest, self.successor(lambda p: p['keys']['checker'].update(not_after='2026-11-04T12:00:00Z')), self.public, T1)

    def test_rotation_to_pre_enrolled_reserve_preserves_trust(self):
        d = build_examples()
        self.assertTrue(d['replacement_result']['signature_valid'])
        self.assertEqual(d['replacement_receipt']['payload']['checker_id'], 'checker-reserve')
        self.assertEqual(d['manifest']['payload']['trust'], d['revoked_manifest']['payload']['trust'])

    def test_reserve_cannot_be_used_before_activation(self):
        with self.assertRaisesRegex(ValidationError, 'not active'):
            authorized_issue(self.ledger, [], self.manifest, self.public, digest(self.manifest), T0,
                             self.payment, 'checker-reserve', self.keys['checker-reserve'], ZERO)

    def test_signature_domain_separation(self):
        from satotag.registry import signing_bytes
        m = deepcopy(self.manifest)
        m['signature'] = self.root.sign(signing_bytes('receipt', m['payload'])).hex()
        with self.assertRaisesRegex(ValidationError, 'root signature'):
            self.verify(m)

    def test_invalid_sequence_and_revocation_types(self):
        for edit in (lambda p: p.update(sequence=True), lambda p: p['keys']['checker'].update(revoked='false')):
            with self.subTest(edit=edit), self.assertRaises(ValidationError):
                self.verify(self.signed(edit))

    def test_unenrolled_replacement_requires_explicit_registry_migration(self):
        with self.assertRaisesRegex(ValidationError, 'epoch'):
            advance_manifest(self.manifest, self.successor(lambda p: p['trust'].update(registry_id='OTHER')), self.public, T1)

    def test_cli_authorized_verify_and_no_downgrade(self):
        d = build_examples()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ('bundle', 'manifest', 'receipt', 'payment', 'revoked_manifest'):
                (root / (name+'.json')).write_text(json.dumps(d[name]))
            args = [sys.executable, '-m', 'satotag', 'authorized-verify', str(root/'bundle.json'),
                    '--manifest', str(root/'manifest.json'), '--root-key', d['root_public_key'],
                    '--manifest-checkpoint', d['manifest_checkpoint'], '--as-of', T1, '--checkpoint', ZERO,
                    '--receipt', str(root/'receipt.json'), '--payment', str(root/'payment.json')]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['key_manifest_sequence'], 1)
            (root/'manifest.json').write_text(json.dumps(d['revoked_manifest']))
            args[args.index('--manifest-checkpoint')+1] = d['revoked_checkpoint']
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('revoked', result.stderr)
            args[args.index('--manifest-checkpoint')+1] = d['manifest_checkpoint']
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('checkpoint', result.stderr)


if __name__ == '__main__':
    unittest.main()
