import copy
from fractions import Fraction
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from satotag import ValidationError, analyze

ROOT = Path(__file__).resolve().parents[1]


def fixture(name="split"):
    return json.loads((ROOT / "examples" / f"{name}.json").read_text())


def number(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def by_id(report, outpoint):
    return next(row for row in report["outputs"] if row["outpoint"] == outpoint)


class ExposureTests(unittest.TestCase):
    def test_mark_survives_split_and_second_payment(self):
        report = analyze(fixture())
        self.assertEqual(by_id(report, "payment:0")["case_ids"], ["DEMO-001"])
        self.assertEqual(number(by_id(report, "payment:0")["exposure_sats"]), 20_000_000)
        self.assertEqual(by_id(report, "origin:1")["mark"], "none")

    def test_unspent_plus_fees_equals_seed(self):
        totals = analyze(fixture())["totals"]
        self.assertEqual(totals["fees_sats"], 150_000)
        self.assertEqual(number(totals["unspent_exposure_sats"]), 99_850_000)
        self.assertEqual(number(totals["seeded_sats"]), 100_000_000)
        self.assertEqual(number(totals["fee_exposure_sats"]), 150_000)

    def test_mix_preserves_twenty_percent_not_hundred(self):
        report = analyze(fixture("mixed"))
        self.assertEqual(by_id(report, "merge:0")["exposure_percent"], 20.0)
        self.assertEqual(number(by_id(report, "merge:0")["exposure_sats"]), 50_000_000)

    def test_tiny_exposure_is_not_rounded_away(self):
        row = by_id(analyze(fixture("dust")), "merge:0")
        self.assertEqual(row["mark"], "inherited")
        self.assertEqual(number(row["exposure_sats"]), Fraction(100_000_000, 100_001))
        self.assertLess(row["exposure_percent"], 0.001)
        self.assertGreater(row["exposure_percent"], 0)

    def test_revoked_case_retains_record_without_active_exposure(self):
        report = analyze(fixture("revoked"))
        self.assertEqual(number(report["totals"]["unspent_exposure_sats"]), 0)
        self.assertEqual(report["cases"][0]["status"], "revoked")
        self.assertTrue(all(row["mark"] == "none" for row in report["outputs"]))

    def test_pending_case_does_not_mark(self):
        data = fixture()
        data["cases"][0]["status"] = "pending"
        self.assertEqual(number(analyze(data)["totals"]["seeded_sats"]), 0)

    def test_quote_affects_only_exposure_and_not_balance(self):
        report = analyze(fixture("mixed"), "60")
        row = by_id(report, "merge:0")
        self.assertEqual(row["value_sats"], 250_000_000)
        self.assertEqual(number(row["hypothetical_quote_sats_equivalent"]), 220_000_000)
        self.assertEqual(number(row["hypothetical_discount_sats"]), 30_000_000)

    def test_quotes_at_zero_and_hundred_percent(self):
        for discount, expected in [("0", 20_000_000), ("100", 0)]:
            row = by_id(analyze(fixture(), discount), "payment:0")
            self.assertEqual(number(row["hypothetical_quote_sats_equivalent"]), expected)
            self.assertEqual(row["value_sats"], 20_000_000)

    def test_decimal_haircut_is_exact(self):
        row = by_id(analyze(fixture(), "12.345"), "payment:0")
        self.assertEqual(number(row["hypothetical_discount_sats"]), 2_469_000)

    def test_order_of_input_rows_does_not_change_result(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["transactions"].reverse()
        first, second = analyze(a), analyze(b)
        self.assertEqual(first["outputs"], second["outputs"])
        self.assertEqual(first["totals"], second["totals"])

    def test_multiple_independent_cases_remain_distinct(self):
        data = fixture("mixed")
        second = copy.deepcopy(data["cases"][0])
        second["case_id"] = "DEMO-002"
        second["seeds"][0]["vout"] = 1
        data["cases"].append(second)
        row = by_id(analyze(data), "merge:0")
        self.assertEqual(row["case_ids"], ["DEMO-001", "DEMO-002"])
        self.assertEqual(number(row["exposure_by_case"]["DEMO-001"]), 50_000_000)
        self.assertEqual(number(row["exposure_by_case"]["DEMO-002"]), 200_000_000)

    def test_fingerprint_is_reproducible_and_input_not_mutated(self):
        data = fixture()
        original = copy.deepcopy(data)
        self.assertEqual(analyze(data), analyze(data))
        self.assertEqual(data, original)
        data["cases"][0]["status"] = "revoked"
        self.assertNotEqual(analyze(data)["dataset_sha256"], analyze(original)["dataset_sha256"])

    def test_zero_value_output_has_no_exposure(self):
        data = fixture()
        data["transactions"][1]["outputs"].append({"value_sats": 0})
        self.assertEqual(by_id(analyze(data), "split:2")["mark"], "none")

    def test_generated_graphs_conserve_value_and_exposure(self):
        # Many distinct merge/split paths; invariants independent of any fixture.
        for run in range(100):
            rng = random.Random(run)
            data = fixture("mixed")
            data["transactions"] = data["transactions"][:1]
            live = [("origin", 0, 100_000_000), ("origin", 1, 400_000_000)]
            for i in range(25):
                selected = rng.sample(live, min(len(live), rng.randint(1, 3)))
                total = sum(item[2] for item in selected)
                fee = min(rng.randrange(100), total)
                a = rng.randint(0, total - fee)
                txid = f"step{i}"
                data["transactions"].append({"txid": txid,
                    "inputs": [{"txid": t, "vout": n} for t, n, _ in selected],
                    "outputs": [{"value_sats": a}, {"value_sats": total - fee - a}]})
                live = [item for item in live if item not in selected]
                live.extend([(txid, 0, a), (txid, 1, total - fee - a)])
            report = analyze(data)
            totals = report["totals"]
            self.assertEqual(number(totals["unspent_exposure_sats"]) +
                             number(totals["fee_exposure_sats"]), 100_000_000)
            self.assertEqual(totals["unspent_sats"] + totals["fees_sats"], 500_000_000)
            for row in report["outputs"]:
                self.assertLessEqual(number(row["exposure_sats"]), row["value_sats"])


class ValidationTests(unittest.TestCase):
    def test_rejects_double_spend(self):
        data = fixture()
        data["transactions"][2]["inputs"] = [{"txid": "origin", "vout": 0}]
        with self.assertRaisesRegex(ValidationError, "Double spend"):
            analyze(data)

    def test_rejects_missing_input(self):
        data = fixture()
        data["transactions"][1]["inputs"][0]["txid"] = "unknown"
        with self.assertRaisesRegex(ValidationError, "Missing input"):
            analyze(data)

    def test_rejects_negative_float_and_boolean_values(self):
        for invalid in [-1, 1.5, True, "100"]:
            data = fixture()
            data["transactions"][0]["outputs"][0]["value_sats"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                analyze(data)

    def test_rejects_created_money(self):
        data = fixture()
        data["transactions"][1]["outputs"][0]["value_sats"] = 500_000_000
        with self.assertRaisesRegex(ValidationError, "outputs exceed inputs"):
            analyze(data)

    def test_rejects_cycles(self):
        data = fixture()
        data["transactions"] = [
            {"txid": "a", "inputs": [{"txid": "b", "vout": 0}], "outputs": [{"value_sats": 1}]},
            {"txid": "b", "inputs": [{"txid": "a", "vout": 0}], "outputs": [{"value_sats": 1}]},
        ]
        with self.assertRaisesRegex(ValidationError, "cycle"):
            analyze(data)

    def test_rejects_overlapping_seeds(self):
        data = fixture()
        data["cases"][0]["seeds"].append({"txid": "payment", "vout": 0})
        with self.assertRaisesRegex(ValidationError, "Overlapping ancestor"):
            analyze(data)

    def test_rejects_duplicate_seed_between_cases(self):
        data = fixture()
        other = copy.deepcopy(data["cases"][0])
        other["case_id"] = "OTHER"
        data["cases"].append(other)
        with self.assertRaisesRegex(ValidationError, "Overlapping active seeds"):
            analyze(data)

    def test_requires_evidence_for_each_claim(self):
        data = fixture()
        data["cases"][0]["evidence"] = []
        with self.assertRaisesRegex(ValidationError, "evidence"):
            analyze(data)

    def test_rejects_mainnet(self):
        data = fixture()
        data["network"] = "bitcoin-mainnet"
        with self.assertRaisesRegex(ValidationError, "simulation"):
            analyze(data)

    def test_rejects_unknown_fields(self):
        data = fixture()
        data["casez"] = []
        with self.assertRaisesRegex(ValidationError, "unknown fields"):
            analyze(data)

    def test_rejects_invalid_haircuts(self):
        for invalid in ["NaN", "Infinity", "-1", "101", "abc", True, 0.6, "0.0000001"]:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                analyze(fixture(), invalid)

    def test_rejects_duplicate_transaction(self):
        data = fixture()
        data["transactions"].append(copy.deepcopy(data["transactions"][0]))
        with self.assertRaisesRegex(ValidationError, "Duplicate transaction"):
            analyze(data)


class CLITests(unittest.TestCase):
    def test_cli_emits_parseable_json(self):
        result = subprocess.run([sys.executable, "-m", "satotag", "analyze", "examples/split.json"],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(result.stdout)["totals"]["value_conserved"])

    def test_cli_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text('{"network":"simulation","network":"mainnet"}')
            result = subprocess.run([sys.executable, "-m", "satotag", "analyze", str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Duplicate JSON key", result.stderr)

    def test_cli_prevents_overwriting_source(self):
        result = subprocess.run([sys.executable, "-m", "satotag", "analyze", "examples/split.json",
                                 "--output", "examples/split.json"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("overwrite", result.stderr)


if __name__ == "__main__":
    unittest.main()
