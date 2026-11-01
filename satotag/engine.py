"""Deterministic, value-conserving exposure propagation on a synthetic UTXO DAG.

Proportional attribution is an explicit modelling assumption. It does not prove
which satoshis were stolen and is not a probability of crime or a legal finding.
All quantities remain exact Fractions internally; fractions of a satoshi are
accounting estimates only, never spendable Bitcoin outputs.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import heapq
import json
import re

MAX_MONEY = 21_000_000 * 100_000_000
MAX_TRANSACTIONS = 10_000
MAX_OUTPUTS = 50_000
MAX_CASES = 100
MAX_FRACTION_BITS = 4096
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class ValidationError(ValueError):
    """An input cannot be interpreted safely under this model."""


def _require(ok, message):
    if not ok:
        raise ValidationError(message)


def _integer(value, label, maximum=MAX_MONEY):
    _require(type(value) is int and 0 <= value <= maximum,
             f"{label}: expected a non-negative integer <= {maximum}")
    return value


def _text(value, label, limit=500):
    _require(isinstance(value, str) and 0 < len(value) <= limit,
             f"{label}: expected non-empty text (max {limit} characters)")
    return value


def _identifier(value, label):
    _require(isinstance(value, str) and ID.fullmatch(value),
             f"{label}: invalid synthetic identifier")
    return value


def _object(value, required, optional, label):
    _require(isinstance(value, dict), f"{label}: expected object")
    _require(required <= value.keys(), f"{label}: missing fields {sorted(required - value.keys())}")
    _require(value.keys() <= required | optional, f"{label}: unknown fields {sorted(value.keys() - required - optional)}")


def _ref(value, label):
    _object(value, {"txid", "vout"}, set(), label)
    return (_identifier(value["txid"], label + ".txid"),
            _integer(value["vout"], label + ".vout", MAX_OUTPUTS))


def _outpoint(ref):
    return f"{ref[0]}:{ref[1]}"


def _fraction(value):
    """Strings keep large exact rationals safe in JavaScript JSON readers."""
    value = Fraction(value)
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def _bounded(value):
    _require(max(value.numerator.bit_length(), value.denominator.bit_length()) <= MAX_FRACTION_BITS,
             "Exact fraction complexity limit exceeded; use a smaller simulation")
    return value


def _haircut(value):
    _require(isinstance(value, (str, int, Decimal)) and not isinstance(value, bool),
             "haircut: use a decimal string or integer, not a floating-point number")
    _require(len(str(value)) <= 20, "haircut: value too long")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValidationError("haircut: invalid decimal") from None
    _require(number.is_finite() and 0 <= number <= 100,
             "haircut: expected a finite percentage from 0 to 100")
    _require(number.as_tuple().exponent >= -6, "haircut: at most six decimal places")
    return Fraction(number) / 100


def _validate(data):
    _object(data, {"schema_version", "network", "transactions", "cases"},
            {"name", "description"}, "dataset")
    _require(type(data["schema_version"]) is int and data["schema_version"] == 1,
             "Only schema_version 1 is supported")
    _require(data["network"] == "simulation", "Only network='simulation' is supported; no mainnet enforcement")
    for key in ("name", "description"):
        if key in data:
            _text(data[key], key, 2_000)
    rows = data["transactions"]
    _require(isinstance(rows, list) and 0 < len(rows) <= MAX_TRANSACTIONS,
             f"transactions: expected 1..{MAX_TRANSACTIONS} entries")
    txs, values, labels, spends = {}, {}, {}, {}
    parents, children = {}, defaultdict(set)
    output_count = origin_value = 0
    for row in rows:
        _object(row, {"txid", "inputs", "outputs"}, {"label"}, "transaction")
        txid = _identifier(row["txid"], "txid")
        _require(txid not in txs, f"Duplicate transaction: {txid}")
        if "label" in row:
            _text(row["label"], "transaction.label")
        _require(isinstance(row["inputs"], list) and len(row["inputs"]) <= MAX_OUTPUTS,
                 f"{txid}: invalid inputs")
        _require(isinstance(row["outputs"], list) and len(row["outputs"]) > 0,
                 f"{txid}: at least one output is required")
        output_count += len(row["outputs"])
        _require(output_count <= MAX_OUTPUTS, "Too many outputs")
        refs = [_ref(item, f"{txid}.inputs") for item in row["inputs"]]
        for ref in refs:
            _require(ref not in spends, f"Double spend: {_outpoint(ref)}")
            spends[ref] = txid
        parents[txid] = {ref[0] for ref in refs}
        for parent in parents[txid]:
            children[parent].add(txid)
        total = 0
        for i, output in enumerate(row["outputs"]):
            _object(output, {"value_sats"}, {"label"}, f"{txid}.outputs[{i}]")
            value = _integer(output["value_sats"], "value_sats")
            total += value
            values[(txid, i)] = value
            labels[(txid, i)] = _text(output.get("label", _outpoint((txid, i))), "output.label")
        _require(total <= MAX_MONEY, f"{txid}: output sum exceeds MAX_MONEY")
        if not refs:
            origin_value += total
        txs[txid] = {"txid": txid, "inputs": refs, "output_sum": total,
                     "output_count": len(row["outputs"]), "label": row.get("label", txid)}
    _require(origin_value <= MAX_MONEY, "Synthetic origins exceed MAX_MONEY")
    for ref in spends:
        _require(ref in values, f"Missing input: {_outpoint(ref)}; unknown ancestry is not treated as clean")
    for txid, tx in txs.items():
        if tx["inputs"]:
            total_in = sum(values[ref] for ref in tx["inputs"])
            _require(tx["output_sum"] <= total_in, f"{txid}: outputs exceed inputs")
    indegree = {key: len(value) for key, value in parents.items()}
    ready = [key for key, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        current = heapq.heappop(ready)
        order.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    _require(len(order) == len(txs), "Transaction graph contains a cycle")

    cases = data["cases"]
    _require(isinstance(cases, list) and len(cases) <= MAX_CASES,
             f"cases: expected at most {MAX_CASES} entries")
    case_ids, seed_map = set(), {}
    for case in cases:
        _object(case, {"case_id", "status", "seeds", "evidence"}, {"note"}, "case")
        case_id = _identifier(case["case_id"], "case_id")
        _require(case_id not in case_ids, f"Duplicate case: {case_id}")
        case_ids.add(case_id)
        _require(case["status"] in ("accepted", "pending", "revoked"), "Invalid case status")
        if "note" in case:
            _text(case["note"], "case.note", 2_000)
        _require(isinstance(case["evidence"], list) and 0 < len(case["evidence"]) <= 20,
                 f"{case_id}: at least one evidence record is required")
        for evidence in case["evidence"]:
            _object(evidence, {"reference", "description"}, {"sha256"}, "evidence")
            _text(evidence["reference"], "evidence.reference", 2_000)
            _text(evidence["description"], "evidence.description", 2_000)
            if "sha256" in evidence:
                _require(isinstance(evidence["sha256"], str) and
                         re.fullmatch(r"[a-f0-9]{64}", evidence["sha256"]), "Invalid evidence SHA-256")
        _require(isinstance(case["seeds"], list) and 0 < len(case["seeds"]) <= MAX_OUTPUTS,
                 f"{case_id}: non-empty seeds required")
        seen = set()
        for raw in case["seeds"]:
            ref = _ref(raw, "seed")
            _require(ref in values and values[ref] > 0, "Seed must reference an existing positive output")
            _require(ref not in seen, f"Duplicate seed: {_outpoint(ref)}")
            seen.add(ref)
            if case["status"] == "accepted":
                _require(ref not in seed_map, f"Overlapping active seeds: {_outpoint(ref)}")
                seed_map[ref] = case_id
    return txs, values, labels, spends, order, seed_map, origin_value


def analyze(data, haircut_percent="60"):
    """Return a JSON-compatible report. No I/O, networking, signing, or mutation.

The haircut is an optional hypothetical buyer policy, not a balance deduction.
Evidence references and 'accepted' claims are input assertions, NOT verified by
this engine. A hash identifies the input content, not a trusted authority.
"""
    discount = _haircut(haircut_percent)
    txs, values, labels, spends, order, seeds, origin_value = _validate(data)
    exposure, reports, fee_reports = {}, [], []
    seeded = defaultdict(Fraction)
    fees = defaultdict(Fraction)
    gross_fees = 0
    for txid in order:
        tx = txs[txid]
        total_in = sum(values[ref] for ref in tx["inputs"])
        incoming = defaultdict(Fraction)
        for ref in tx["inputs"]:
            for case_id, amount in exposure[ref].items():
                incoming[case_id] += amount
        fee = total_in - tx["output_sum"] if tx["inputs"] else 0
        gross_fees += fee
        attributed_fee = {case: _bounded(amount * Fraction(fee, total_in))
                          for case, amount in incoming.items()} if total_in else {}
        for case_id, amount in attributed_fee.items():
            fees[case_id] = _bounded(fees[case_id] + amount)
        fee_reports.append({"txid": txid, "value_sats": fee,
                            "exposure_sats": _fraction(sum(attributed_fee.values(), Fraction()))})
        for i in range(tx["output_count"]):
            ref, value = (txid, i), values[(txid, i)]
            share = {case: _bounded(amount * Fraction(value, total_in))
                     for case, amount in incoming.items() if value > 0} if total_in else {}
            if ref in seeds:
                _require(not share, f"Overlapping ancestor/descendant seed: {_outpoint(ref)}")
                share = {seeds[ref]: Fraction(value)}
                seeded[seeds[ref]] += value
            exposure[ref] = share
            amount = sum(share.values(), Fraction())
            _require(0 <= amount <= value, "Internal invariant: exposure outside output value")
            reports.append({
                "outpoint": _outpoint(ref), "txid": txid, "vout": i, "label": labels[ref],
                "value_sats": value, "spent_by": spends.get(ref),
                "mark": "seed" if ref in seeds else "inherited" if share else "none",
                "case_ids": sorted(share), "exposure_sats": _fraction(amount),
                "exposure_percent": float(amount * 100 / value) if value else 0.0,
                "exposure_by_case": {key: _fraction(share[key]) for key in sorted(share)},
                "hypothetical_discount_sats": _fraction(amount * discount),
                "hypothetical_quote_sats_equivalent": _fraction(value - amount * discount),
            })
    live = [row for row in reports if row["spent_by"] is None]
    live_by_case = defaultdict(Fraction)
    for ref in values:
        if ref not in spends:
            for case_id, amount in exposure[ref].items():
                live_by_case[case_id] += amount
    _require(all(seeded[key] == live_by_case[key] + fees[key] for key in seeded),
             "Internal invariant: marked exposure was created or lost")
    live_exposure = sum(live_by_case.values(), Fraction())
    live_value = sum(row["value_sats"] for row in live)
    _require(origin_value == live_value + gross_fees, "Internal invariant: value conservation")
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=True).encode()).hexdigest()
    return {
        "schema_version": 1, "engine_version": "0.1.0", "network": "simulation",
        "name": data.get("name", "SatoTag simulation"), "description": data.get("description", ""),
        "dataset_sha256": fingerprint, "attribution_model": "proportional",
        "haircut_percent": format(Decimal(str(haircut_percent)).normalize(), "f"),
        "limitations": [
            "Synthetic ledger only; does not modify Bitcoin or freeze assets.",
            "Accepted claims and evidence are supplied by the caller, not independently verified.",
            "Exposure is a proportional accounting model, not proof of individual satoshi provenance.",
            "No mark does not certify lawful origin; scope is limited to the supplied complete graph.",
            "Fees leave the model; miner payouts, cross-chain swaps and privacy boundaries are not traced.",
            "Quotes are hypothetical buyer policies, not prices, spendable balances or enforced penalties.",
        ],
        "cases": sorted(data["cases"], key=lambda row: row["case_id"]),
        "transactions": [{"txid": key, "label": txs[key]["label"],
                          "inputs": [_outpoint(ref) for ref in txs[key]["inputs"]],
                          "outputs": [_outpoint((key, i)) for i in range(txs[key]["output_count"])]}
                         for key in order],
        "outputs": reports, "fees": fee_reports,
        "totals": {
            "origin_sats": origin_value, "unspent_sats": live_value, "fees_sats": gross_fees,
            "seeded_sats": _fraction(sum(seeded.values(), Fraction())),
            "unspent_exposure_sats": _fraction(live_exposure),
            "fee_exposure_sats": _fraction(sum(fees.values(), Fraction())),
            "hypothetical_quote_sats_equivalent": _fraction(live_value - live_exposure * discount),
            "marked_unspent_outputs": sum(row["mark"] != "none" for row in live),
            "value_conserved": True, "exposure_conserved_including_fees": True,
        },
    }
