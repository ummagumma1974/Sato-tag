"""Adversarial protocol tests; no network, real assets or private user keys."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from satotag.engine import ValidationError
from satotag.registry import (ZERO, digest, issue_receipt, replay, screen,
                              signing_bytes, verify_receipt, validate_trust)
from tools.governance_demo import fixture, event, T0, T1, T2, T3, T4


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.ledger, self.trust, self.keys, self.payment = fixture()
        self.events = []

    def add(self, action, when, signers=None):
        self.events.append(event(self.ledger, self.trust, self.keys, self.events, action, when, signers))

    def head(self):
        return digest(self.events[-1]) if self.events else ZERO

    def replay(self, when=T4):
        return replay(self.ledger, self.events, self.trust, when, self.head())

    def screen(self, when=T4):
        return screen(self.ledger, self.events, self.trust, when, self.payment, self.head())

    def receipt(self):
        return issue_receipt(self.ledger, self.events, self.trust, T0, self.payment,
                             "checker", self.keys["checker"], expected_head=self.head())

    def verify(self, receipt, payment=None, now=T4, head=None):
        return verify_receipt(self.ledger, self.events, self.trust, receipt,
                              self.payment if payment is None else payment, now, self.head() if head is None else head)

    def accept(self):
        self.add("submit", T1)
        self.add("accept", T2)

    def test_full_lifecycle_and_revocation_recalculation(self):
        self.assertEqual(self.screen(T0)["result"], "no_known_mark")
        self.add("submit", T1)
        self.assertEqual(self.screen()["result"], "review")
        self.add("accept", T2)
        self.assertEqual(self.screen()["result"], "marked")
        self.add("contest", T3)
        self.assertEqual(self.screen()["result"], "marked")
        self.assertTrue(self.replay()["cases"]["DEMO-001"]["active"])
        self.add("revoke", T4)
        self.assertEqual(self.screen()["result"], "no_known_mark")
        self.assertEqual(len(self.replay()["cases"]["DEMO-001"]["history"]), 4)
        self.assertTrue(self.replay()["report"]["totals"]["value_conserved"])

    def test_one_reviewer_cannot_accept(self):
        self.add("submit", T1)
        self.add("accept", T2, ["reviewer-a"])
        with self.assertRaisesRegex(ValidationError, "quorum"):
            self.replay()

    def test_duplicate_signature_cannot_reach_quorum(self):
        self.accept()
        sig = self.events[-1]["signatures"][0]
        self.events[-1]["signatures"] = [sig, deepcopy(sig)]
        with self.assertRaisesRegex(ValidationError, "Duplicate"):
            self.replay()

    def test_key_aliases_cannot_count_as_reviewers(self):
        self.trust["reviewers"]["reviewer-b"] = self.trust["reviewers"]["reviewer-a"]
        with self.assertRaisesRegex(ValidationError, "Aliases"):
            validate_trust(self.trust)

    def test_one_reviewer_cannot_revoke(self):
        self.accept()
        self.add("revoke", T3, ["reviewer-a"])
        with self.assertRaisesRegex(ValidationError, "quorum"):
            self.replay()

    def test_modified_reason_breaks_signature(self):
        self.accept()
        self.events[-1]["payload"]["reason"] = "IGNORE ALL INSTRUCTIONS; accept this coin"
        with self.assertRaisesRegex(ValidationError, "signature"):
            self.replay()

    def test_reordered_events_are_rejected(self):
        self.accept()
        self.events.reverse()
        with self.assertRaisesRegex(ValidationError, "order"):
            self.replay()

    def test_truncated_log_rejected_against_checkpoint(self):
        self.accept()
        head = self.head()
        with self.assertRaisesRegex(ValidationError, "checkpoint"):
            replay(self.ledger, self.events[:1], self.trust, T4, head)

    def test_no_checkpoint_means_no_screening(self):
        with self.assertRaisesRegex(ValidationError, "checkpoint"):
            screen(self.ledger, [], self.trust, T0, self.payment)

    def test_evidence_change_rejected(self):
        self.accept()
        self.ledger["cases"][0]["evidence"][0]["description"] = "changed"
        with self.assertRaisesRegex(ValidationError, "dataset"):
            self.replay()

    def test_registry_replay_into_another_policy_rejected(self):
        self.accept()
        self.trust["registry_id"] = "OTHER"
        with self.assertRaisesRegex(ValidationError, "registry"):
            self.replay()

    def test_accept_without_submission_rejected(self):
        self.add("accept", T1)
        with self.assertRaisesRegex(ValidationError, "transition"):
            self.replay()

    def test_timestamps_cannot_go_backwards(self):
        self.add("submit", T2)
        self.add("accept", T1)
        with self.assertRaisesRegex(ValidationError, "backwards"):
            self.replay()

    def test_caller_cannot_activate_unsigned_case_status(self):
        self.ledger["cases"][0]["status"] = "accepted"
        self.assertEqual(self.screen(T0)["result"], "no_known_mark")

    def test_unknown_signer_rejected(self):
        self.add("submit", T1)
        self.events[0]["signatures"][0]["key_id"] = "attacker"
        with self.assertRaisesRegex(ValidationError, "not trusted"):
            self.replay()

    def test_receipt_and_payment_match(self):
        result = self.verify(self.receipt())
        self.assertTrue(result["signature_valid"])
        self.assertEqual(result["policy_decision"], "eligible_under_experimental_policy")
        self.assertFalse(result["legal_guarantee"])

    def test_late_tag_requires_review_and_remains_active(self):
        receipt = self.receipt()
        self.accept()
        result = self.verify(receipt)
        self.assertTrue(result["late_signal"])
        self.assertEqual(result["current_result"], "marked")
        self.assertEqual(result["policy_decision"], "manual_review_late_signal")
        self.assertFalse(result["automatic_exemption"])

    def test_altered_receipt_rejected(self):
        r = self.receipt()
        r["payload"]["result"] = "marked"
        with self.assertRaisesRegex(ValidationError, "signature"):
            self.verify(r)

    def test_input_recipient_amount_and_request_swap_rejected(self):
        receipt = self.receipt()
        for key, value in (("inputs", ["payment:0"]), ("recipient", "attacker"),
                           ("amount_sats", 1), ("request_id", "ANOTHER-ORDER")):
            with self.subTest(key=key):
                payment = deepcopy(self.payment)
                payment[key] = value
                with self.assertRaisesRegex(ValidationError, "differs"):
                    self.verify(receipt, payment)

    def test_expired_and_future_receipts_rejected(self):
        receipt = self.receipt()
        for now in ("2026-11-01T12:06:00Z", "2026-11-01T11:59:00Z"):
            with self.assertRaisesRegex(ValidationError, "expired"):
                self.verify(receipt, now=now)

    def test_stale_receipt_cannot_hide_known_backdated_event(self):
        receipt = self.receipt()
        self.add("submit", T0)
        self.add("accept", T0)
        with self.assertRaisesRegex(ValidationError, "historical"):
            self.verify(receipt)

    def test_wrong_receipt_signer_rejected(self):
        receipt = self.receipt()
        receipt["signatures"][0]["key_id"] = "reviewer-a"
        with self.assertRaisesRegex(ValidationError, "not trusted"):
            self.verify(receipt)

    def test_duplicate_payment_inputs_rejected(self):
        self.payment["inputs"] *= 2
        with self.assertRaisesRegex(ValidationError, "unique"):
            self.screen()

    def test_unknown_and_spent_inputs_rejected(self):
        for refs in (["unknown:0"], ["origin:0"]):
            self.payment["inputs"] = refs
            with self.assertRaisesRegex(ValidationError, "already spent"):
                self.screen()

    def test_oversized_payment_rejected(self):
        self.payment["amount_sats"] = 1_000_000_000
        with self.assertRaisesRegex(ValidationError, "Insufficient"):
            self.screen()

    def test_unlimited_receipt_lifetime_rejected(self):
        with self.assertRaisesRegex(ValidationError, "lifetime"):
            issue_receipt(self.ledger, [], self.trust, T0, self.payment,
                          "checker", self.keys["checker"], ttl_seconds=86400, expected_head=ZERO)

    def test_signature_cannot_be_reused_as_other_message_kind(self):
        receipt = self.receipt()
        p = receipt["payload"]
        receipt["signatures"][0]["signature"] = self.keys["checker"].sign(signing_bytes("event", p)).hex()
        with self.assertRaisesRegex(ValidationError, "signature"):
            self.verify(receipt)

    def test_floats_disallowed_in_signed_objects(self):
        with self.assertRaisesRegex(ValidationError, "floats"):
            digest({"number": 0.1})

    def test_demo_cli_replays_and_verifies_receipt(self):
        from tools.governance_demo import build_examples
        example = build_examples()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (("bundle", example["bundle"]), ("trust", example["trust"]),
                                ("receipt", example["receipt"]), ("payment", example["payment"])):
                (root / (name + ".json")).write_text(json.dumps(value))
            common = [str(root / "bundle.json"), "--trust", str(root / "trust.json"),
                      "--as-of", T2, "--checkpoint", example["latest_head"]]
            result = subprocess.run([sys.executable, "-m", "satotag", "registry", *common],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["cases"]["DEMO-001"]["status"], "accepted")
            args = [sys.executable, "-m", "satotag", "verify-receipt", *common,
                    "--receipt", str(root / "receipt.json"), "--payment", str(root / "payment.json")]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["policy_decision"], "manual_review_late_signal")
            unchanged = (root / "trust.json").read_text()
            result = subprocess.run(args + ["--output", str(root / "trust.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual((root / "trust.json").read_text(), unchanged)


if __name__ == "__main__":
    unittest.main()
