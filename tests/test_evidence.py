"""Adversarial checks at the evidence-screen boundary, using public test keys."""
from copy import deepcopy
import unittest
from satotag.evidence import evidence_screen, review_bytes
from satotag.engine import ValidationError
from satotag.registry import digest
from tools.evidence_demo import fixture_evidence
from tools.governance_demo import event, T3, T4
from tools.keyring_demo import sign_manifest


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.a, self.keys, self.root = fixture_evidence()
        self.package = next(iter(self.a['packages'].values()))

    def screen(self):
        return evidence_screen(**self.a)

    def resign(self):
        for r in self.package['reviews']:
            p = r['payload']
            p.update(policy_hash=digest(self.a['policy']), dossier_hash=digest(self.package['dossier']))
            r['signature'] = self.keys[p['reviewer_id']].sign(review_bytes(p)).hex()
        self.a['expected_policy'] = digest(self.a['policy'])

    def rejected(self):
        with self.assertRaises(ValidationError):
            self.screen()

    def test_complete_dossier_marks_payment(self):
        self.assertEqual(self.screen()['result'], 'marked')
        self.assertEqual(len(self.screen()['evidence_assessments'][0]['reviewers']), 2)

    def test_missing_package_fails_closed(self):
        self.a['packages'].clear()
        self.rejected()

    def test_missing_artifact(self):
        self.a['artifacts'].pop(next(iter(self.a['artifacts'])))
        self.rejected()

    def test_corrupted_artifact(self):
        self.a['artifacts'][next(iter(self.a['artifacts']))] = b'forged'
        self.rejected()

    def test_changed_dossier_requires_new_reviews(self):
        self.package['dossier']['statement'] = 'New allegation'
        self.rejected()

    def test_wrong_case_even_when_resigned(self):
        self.package['dossier']['case_id'] = 'OTHER'
        self.resign()
        self.rejected()

    def test_wrong_dataset_even_when_resigned(self):
        self.package['dossier']['dataset_hash'] = '0' * 64
        self.resign()
        self.rejected()

    def test_one_review_is_not_quorum(self):
        self.package['reviews'].pop()
        self.rejected()

    def test_duplicate_reviewer(self):
        self.package['reviews'][1] = deepcopy(self.package['reviews'][0])
        self.rejected()

    def test_same_person_with_two_keys(self):
        people = self.a['policy']['reviewers']
        people['reviewer-b']['person_id'] = people['reviewer-a']['person_id']
        self.resign()
        self.rejected()

    def test_same_organization(self):
        people = self.a['policy']['reviewers']
        people['reviewer-b']['organization_id'] = people['reviewer-a']['organization_id']
        self.resign()
        self.rejected()

    def test_claimant_self_review(self):
        self.package['dossier']['claimant_person_id'] = self.a['policy']['reviewers']['reviewer-a']['person_id']
        self.resign()
        self.rejected()

    def test_conflicted_reviewer(self):
        self.package['reviews'][0]['payload']['conflict_of_interest'] = True
        self.resign()
        self.rejected()

    def test_unknown_or_failed_checks_block(self):
        for outcome in ('unknown', 'fail'):
            with self.subTest(outcome=outcome):
                self.package['reviews'][0]['payload']['checks']['prior_control']['outcome'] = outcome
                self.resign()
                self.rejected()

    def test_missing_check(self):
        del self.package['reviews'][0]['payload']['checks']['unauthorized_transfer']
        self.resign()
        self.rejected()

    def test_empty_rationale(self):
        self.package['reviews'][0]['payload']['checks']['seed_link']['rationale'] = ''
        self.resign()
        self.rejected()

    def test_whitespace_rationale(self):
        self.package['reviews'][0]['payload']['checks']['seed_link']['rationale'] = '   '
        self.resign()
        self.rejected()

    def test_cli_valid_and_corrupted_evidence(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from satotag.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = {'bundle': {'ledger': self.a['ledger'], 'events': self.a['events']},
                    'manifest': self.a['manifest'], 'payment': self.a['payment'],
                    'evidence': {'policy': self.a['policy'], 'packages': self.a['packages'],
                                 'artifacts': {h: b.decode('utf-8') for h, b in self.a['artifacts'].items()}}}
            for key, value in data.items():
                (root / (key + '.json')).write_text(json.dumps(value))
            args = ['evidence-screen', str(root / 'bundle.json'), '--manifest', str(root / 'manifest.json'),
                    '--payment', str(root / 'payment.json'), '--evidence', str(root / 'evidence.json'),
                    '--root-key', self.a['root_public_key'], '--manifest-checkpoint', self.a['expected_manifest'],
                    '--checkpoint', self.a['checkpoint'], '--as-of', self.a['now'],
                    '--evidence-policy-checkpoint', self.a['expected_policy']]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(out.getvalue())['result'], 'marked')
            data['evidence']['artifacts'] = {}
            (root / 'evidence.json').write_text(json.dumps(data['evidence']))
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 2)
                self.assertEqual(main(args + ['--output', str(root / 'evidence.json')]), 2)

    def test_unknown_citation(self):
        self.package['reviews'][0]['payload']['checks']['seed_link']['artifact_ids'] = ['missing']
        self.resign()
        self.rejected()

    def test_single_source_corroboration(self):
        self.package['dossier']['artifacts'][1]['source_id'] = self.package['dossier']['artifacts'][0]['source_id']
        self.resign()
        self.rejected()

    def test_signature_tampering(self):
        self.package['reviews'][0]['signature'] = '00' * 64
        self.rejected()

    def test_review_cannot_move_to_another_acceptance(self):
        self.package['reviews'][0]['payload']['acceptance_hash'] = '0' * 64
        self.resign()
        self.rejected()

    def test_future_review(self):
        self.package['reviews'][0]['payload']['reviewed_at'] = T3
        self.resign()
        self.rejected()

    def test_stale_review(self):
        self.a['policy']['max_review_age_seconds'] = 1
        self.package['reviews'][0]['payload']['reviewed_at'] = '2026-11-01T12:00:00Z'
        self.resign()
        self.rejected()

    def test_unpinned_policy(self):
        self.a['policy']['max_review_age_seconds'] = 2
        self.rejected()

    def test_revoked_reviewer(self):
        p = deepcopy(self.a['manifest']['payload'])
        p['keys']['reviewer-a']['revoked'] = True
        self.a['manifest'] = sign_manifest(p, self.root)
        self.a['expected_manifest'] = digest(self.a['manifest'])
        self.rejected()

    def test_reacceptance_needs_fresh_package(self):
        for action, when in [('contest', T3), ('accept', T4)]:
            self.a['events'].append(event(self.a['ledger'], self.a['manifest']['payload']['trust'], self.keys, self.a['events'], action, when))
        self.a.update(now=T4, checkpoint=digest(self.a['events'][-1]))
        self.rejected()

    def test_revocation_still_clears_mark(self):
        self.a['events'].append(event(self.a['ledger'], self.a['manifest']['payload']['trust'], self.keys, self.a['events'], 'revoke', T3))
        self.a.update(now=T3, checkpoint=digest(self.a['events'][-1]))
        self.assertEqual(self.screen()['result'], 'no_known_mark')

    def test_undeclared_extra_package(self):
        self.a['packages']['0' * 64] = deepcopy(self.package)
        self.rejected()

    def test_no_acceptance_needs_no_package(self):
        self.a['events'] = self.a['events'][:1]
        self.a['packages'] = {}
        self.a['checkpoint'] = digest(self.a['events'][-1])
        self.assertEqual(self.screen()['result'], 'review')


if __name__ == '__main__':
    unittest.main()
