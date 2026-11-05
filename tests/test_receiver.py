"""Receiver tests use public synthetic keys, real local HTTP and SQLite."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

from satotag.receiver import Receiver, make_server
from satotag.registry import digest, ZERO
from tools.evidence_demo import fixture_evidence
from tools.governance_demo import event, T3


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.a, self.keys, self.root = fixture_evidence()
        self.payment = self.a.pop('payment')
        self.now = self.a.pop('now')
        self.context = deepcopy(self.a)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'receiver.sqlite')
        self.invoices = {self.payment['request_id']: {'recipient': self.payment['recipient'], 'amount_sats': self.payment['amount_sats']}}
        self.receiver = Receiver(self.path, self.invoices, lambda: self.context, lambda: self.now)

    def tearDown(self):
        self.receiver.close()
        self.tmp.cleanup()

    def clean_payment(self):
        p = deepcopy(self.payment)
        p['inputs'] = ['origin:1']
        return p

    def count(self):
        return self.receiver.db.execute('SELECT count(*) FROM admissions').fetchone()[0]

    def test_marked_rejected_no_admission(self):
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'rejected')
        self.assertEqual(self.count(), 0)

    def test_unmarked_admitted_without_credit(self):
        result = self.receiver.admit(self.clean_payment())
        self.assertEqual(result['decision'], 'accepted')
        self.assertFalse(result['funds_credited'])
        self.assertEqual(self.count(), 1)

    def test_pending_held(self):
        self.context['events'] = self.context['events'][:1]
        self.context['packages'] = {}
        self.context['checkpoint'] = digest(self.context['events'][-1])
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'held')
        self.assertEqual(self.count(), 0)

    def test_missing_evidence_blocks(self):
        self.context['artifacts'] = {}
        self.assertEqual(self.receiver.admit(self.clean_payment())['decision'], 'blocked')
        self.assertEqual(self.count(), 0)

    def test_provider_unavailable_blocks(self):
        def unavailable():
            raise OSError('private internal detail')
        self.receiver.context_provider = unavailable
        result = self.receiver.admit(self.clean_payment())
        self.assertEqual(result['decision'], 'blocked')
        self.assertNotIn('private', json.dumps(result))

    def test_payer_cannot_supply_approval_or_policy(self):
        for field in ('result', 'policy', 'checkpoint', 'manifest', 'decision', 'now'):
            p = self.clean_payment()
            p[field] = 'approved'
            self.assertEqual(self.receiver.admit(p)['decision'], 'blocked')
        self.assertEqual(self.count(), 0)

    def test_wrong_invoice_amount_or_recipient(self):
        for field, value in [('amount_sats', 1), ('recipient', 'another-shop'), ('amount_sats', True)]:
            p = self.clean_payment()
            p[field] = value
            self.assertEqual(self.receiver.admit(p)['decision'], 'blocked')

    def test_unknown_invoice(self):
        p = self.clean_payment()
        p['request_id'] = 'not-issued'
        self.assertEqual(self.receiver.admit(p)['decision'], 'blocked')

    def test_unknown_and_spent_inputs(self):
        for ref in ('unknown:0', 'origin:0'):
            p = self.clean_payment()
            p['inputs'] = [ref]
            self.assertEqual(self.receiver.admit(p)['decision'], 'blocked')

    def test_duplicate_inputs(self):
        p = self.clean_payment()
        p['inputs'] *= 2
        self.assertEqual(self.receiver.admit(p)['decision'], 'blocked')

    def test_mixed_marked_and_unmarked_rejected(self):
        p = self.clean_payment()
        p['inputs'] = ['origin:1', 'split:1']
        self.assertEqual(self.receiver.admit(p)['decision'], 'rejected')

    def test_retry_idempotent_after_restart(self):
        self.assertEqual(self.receiver.admit(self.clean_payment())['decision'], 'accepted')
        self.receiver.close()
        self.receiver = Receiver(self.path, self.invoices, lambda: self.context, lambda: self.now)
        result = self.receiver.admit(self.clean_payment())
        self.assertTrue(result['idempotent'])
        self.assertEqual(self.count(), 1)

    def test_second_invoice_cannot_reuse_inputs(self):
        p = self.clean_payment()
        self.receiver.admit(p)
        self.receiver.invoices['second'] = deepcopy(self.invoices[self.payment['request_id']])
        p['request_id'] = 'second'
        self.assertEqual(self.receiver.admit(p)['decision'], 'blocked')
        self.assertEqual(self.count(), 1)

    def test_same_invoice_different_inputs_blocked(self):
        self.context.update(events=[], packages={}, checkpoint=ZERO)
        self.receiver.admit(self.clean_payment())
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'blocked')
        self.assertEqual(self.count(), 1)

    def test_old_success_does_not_bypass_new_mark(self):
        self.context = deepcopy(self.a)
        self.context.update(events=[], packages={}, checkpoint=ZERO)
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'accepted')
        self.context = deepcopy(self.a)
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'rejected')

    def test_revocation_allows_fresh_attempt(self):
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'rejected')
        events = self.context['events']
        events.append(event(self.context['ledger'], self.context['manifest']['payload']['trust'], self.keys, events, 'revoke', T3))
        self.context['checkpoint'] = digest(events[-1])
        self.now = T3
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'accepted')

    def test_stale_head_blocks(self):
        self.context['checkpoint'] = ZERO
        self.assertEqual(self.receiver.admit(self.clean_payment())['decision'], 'blocked')

    def test_expired_manifest_blocks(self):
        self.now = '2026-11-04T12:00:00Z'
        self.assertEqual(self.receiver.admit(self.clean_payment())['decision'], 'blocked')

    def test_concurrent_duplicate_requests_have_one_admission(self):
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(self.receiver.admit, [self.clean_payment()] * 8))
        self.assertTrue(all(r['decision'] == 'accepted' for r in results))
        self.assertEqual(self.count(), 1)
        self.assertEqual(sum(not r['idempotent'] for r in results), 1)

    def test_real_sample_cannot_borrow_demo_approvals(self):
        path = Path(__file__).resolve().parents[1] / 'examples/binance_2026_10_29/dataset.json'
        self.context['ledger'] = json.loads(path.read_text())
        self.assertEqual(self.receiver.admit(self.payment)['decision'], 'blocked')
        self.assertEqual(self.count(), 0)

    def test_database_unavailable_blocks(self):
        self.receiver.db.execute('PRAGMA query_only = ON')
        self.assertEqual(self.receiver.admit(self.clean_payment())['decision'], 'blocked')
        self.assertEqual(self.count(), 0)

    def test_http_end_to_end_and_invalid_json(self):
        server = make_server(self.receiver)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(server.server_port) + '/admit'
        def post(raw):
            request = urllib.request.Request(url, data=raw, headers={'Content-Type': 'application/json'})
            try:
                response = urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, json.load(response)
        try:
            status, result = post(json.dumps(self.payment).encode())
            self.assertEqual((status, result['decision']), (403, 'rejected'))
            status, result = post(json.dumps(self.clean_payment()).encode())
            self.assertEqual((status, result['decision']), (200, 'accepted'))
            self.assertEqual(post(b'{"x":1,"x":2}')[0], 400)
            self.assertEqual(post(b'x' * 16385)[0], 400)
            self.assertEqual(post(b'not-json')[0], 400)
            self.assertEqual(post(b'[]')[1]['decision'], 'blocked')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
