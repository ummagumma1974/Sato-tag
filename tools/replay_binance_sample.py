"""Offline, read-only replay of one observed Bitcoin split, not a live registry.

No claim approval is performed. An accepted seed is an explicit what-if input
to the low-level engine. Raw explorer JSON is preserved for reproducibility.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from satotag.engine import analyze

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'examples' / 'binance_2026_10_29'
SEED = '5de2320e6c53e925d135e887096b06145ef35ad04ed0e59b09fc205d7c47f0ba'
SPLIT = '07f4a69342697979b62860184c0416dc49f002802822a3aeefedb53938463eb6'
LISTED = 'bc1qxrxujwxfnvz040jw76d26zhjdg5jura7hs968s'


def build():
    sources = json.loads((DATA / 'sources.json').read_text())
    for source in sources['records']:
        raw = (DATA / source['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source['sha256'], 'Captured source bytes changed'
    seed, split = [json.loads((DATA / (txid + '.json')).read_text()) for txid in (SEED, SPLIT)]
    assert seed['txid'] == SEED and split['txid'] == SPLIT
    assert seed['status']['confirmed'] and split['status']['confirmed']
    assert seed['status']['block_hash'] == split['status']['block_hash']
    assert len(split['vin']) == 1
    vin = split['vin'][0]
    assert (vin['txid'], vin['vout']) == (SEED, 0)
    assert vin['prevout'] == seed['vout'][0], 'Input metadata does not match parent output'
    assert seed['vout'][0]['value'] == 140950000000
    assert [v['value'] for v in split['vout']] == [40949999500, 100000000000]
    assert split['vout'][1]['scriptpubkey_address'] == LISTED
    assert split['fee'] == 500
    assert sum(v['prevout']['value'] for v in split['vin']) == sum(v['value'] for v in split['vout']) + split['fee']
    assert sum(v['prevout']['value'] for v in seed['vin']) == sum(v['value'] for v in seed['vout']) + seed['fee']
    # Parent inputs are outside this bounded replay. Both parent outputs remain
    # in the graph; only output 0 is seeded. Parent change is a negative control.
    ledger = {'schema_version': 1, 'network': 'simulation',
              'name': 'Observed Bitcoin split replay — conditional seed',
              'description': 'Explorer-derived values in a bounded simulation. Not a verified theft claim or current UTXO snapshot.',
              'transactions': [
                  {'txid': SEED, 'inputs': [], 'outputs': [{'value_sats': v['value']} for v in seed['vout']]},
                  {'txid': SPLIT, 'inputs': [{'txid': SEED, 'vout': 0}], 'outputs': [{'value_sats': v['value']} for v in split['vout']]}],
              'cases': [{'case_id': 'BINANCE-2026-SAMPLE-WHATIF', 'status': 'accepted',
                         'seeds': [{'txid': SEED, 'vout': 0}],
                         'evidence': [{'reference': sources['attribution_source'],
                                       'description': 'External address attribution; approval is hypothetical for this replay only.'}]}]}
    report = analyze(ledger, '0')
    outputs = {r['outpoint']: r for r in report['outputs']}
    for i in (0, 1):
        row = outputs[f'{SPLIT}:{i}']
        assert row['mark'] == 'inherited' and row['exposure_percent'] == 100
    assert outputs[f'{SEED}:1']['mark'] == 'none', 'Parent change must not inherit the sibling seed'
    assert report['totals']['fees_sats'] == 500
    assert report['totals']['value_conserved'] and report['totals']['exposure_conserved_including_fees']
    controls = {}
    for status in ('pending', 'revoked'):
        alternative = deepcopy(ledger)
        alternative['cases'][0]['status'] = status
        result = analyze(alternative, '0')
        assert all(row['mark'] == 'none' for row in result['outputs'])
        controls[status] = 'No exposure propagated'
    summary = {'scope': 'One real parent output and its immediate spend, replayed conditionally. Not the entire incident.',
               'captured_at': [s['retrieved_at'] for s in sources['records']],
               'block_height': split['status']['block_height'],
               'seed_outpoint': SEED + ':0', 'seed_sats': seed['vout'][0]['value'],
               'outputs': [{'outpoint': SPLIT + ':' + str(i), 'sats': v['value'],
                            'address': v['scriptpubkey_address'], 'conditional_exposure_percent': 100}
                           for i, v in enumerate(split['vout'])],
               'fee_sats': split['fee'], 'parent_change_mark': 'none', 'controls': controls,
               'result': 'PASS: linked outpoints, exact amounts, conditional propagation and conservation match.',
               'evidence_gate': 'NOT APPROVED: no independently enrolled human reviews of this real case were supplied.',
               'limits': ['Explorer responses are trusted inputs here; no raw transaction hashing, Merkle proof or full-node consensus verification.',
                          'Source hashes preserve captured bytes, not their truth or independent authenticity.',
                          'Parent inputs and later spends are outside scope. Engine unspent means terminal in this graph, not unspent on Bitcoin today.',
                          'No tag was written to Bitcoin or a production registry. No funds moved, frozen or repriced.',
                          'The low-level accepted seed is a what-if assumption; the evidence-review gate has not been satisfied.']}
    return {'dataset.json': ledger, 'engine_report.json': report, 'result.json': summary}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for filename, value in build().items():
        content = json.dumps(value, ensure_ascii=True, indent=2) + '\n'
        path = DATA / filename
        if args.check:
            assert path.read_text() == content, 'Stale replay result: ' + filename
        else:
            path.write_text(content)
    print('PASS: observed split replay and pending/revoked negative controls.')
