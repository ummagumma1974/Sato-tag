"""Run a local receiving-service demo. PUBLIC TEST KEYS, FICTIONAL PAYMENTS."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import urllib.error
import urllib.request

from satotag.receiver import Receiver, make_server
from satotag.registry import digest
from tools.evidence_demo import fixture_evidence
from tools.governance_demo import event, T3


def setup(database):
    args, keys, _ = fixture_evidence()
    payment = args.pop('payment')
    now = args.pop('now')
    state = {'context': args, 'now': now}
    invoices = {payment['request_id']: {'recipient': payment['recipient'], 'amount_sats': payment['amount_sats']}}
    receiver = Receiver(database, invoices, lambda: state['context'], lambda: state['now'])
    return receiver, state, payment, keys


def build_examples():
    with tempfile.TemporaryDirectory() as directory:
        receiver, state, payment, keys = setup(str(Path(directory) / 'demo.sqlite'))
        original = deepcopy(state)
        server = make_server(receiver)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(server.server_port) + '/admit'
        scenarios = []
        def post(name, request, expected):
            req = urllib.request.Request(url, data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
            try:
                response = urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                status, result = response.status, json.load(response)
            assert result['decision'] == expected, (name, result)
            scenarios.append({'name': name, 'http_status': status, 'response': result})
        try:
            post('Marked payment', payment, 'rejected')
            state['context']['events'] = state['context']['events'][:1]
            state['context']['packages'] = {}
            state['context']['checkpoint'] = digest(state['context']['events'][-1])
            post('Pending investigation', payment, 'held')
            state.update(deepcopy(original))
            state['context']['artifacts'] = {}
            post('Evidence unavailable', payment, 'blocked')
            state.update(deepcopy(original))
            forged = deepcopy(payment)
            forged['decision'] = 'accepted'
            post('Payer supplies a fake approval', forged, 'blocked')
            events = state['context']['events']
            events.append(event(state['context']['ledger'], state['context']['manifest']['payload']['trust'], keys, events, 'revoke', T3))
            state['context']['checkpoint'] = digest(events[-1])
            state['now'] = T3
            post('Claim revoked, checked again', payment, 'accepted')
            post('Same payment retried', payment, 'accepted')
            assert scenarios[-1]['response']['idempotent']
            assert receiver.db.execute('SELECT count(*) FROM admissions').fetchone()[0] == 1
            attempts = receiver.db.execute('SELECT count(*) FROM attempts').fetchone()[0]
            return {'notice': 'Real local HTTP and SQLite execution with PUBLIC TEST KEYS and FICTIONAL assessments. No real payment, wallet or deposit credit.',
                    'scenarios': scenarios, 'admissions': 1, 'attempts': attempts,
                    'funds_credited': False}
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            receiver.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--serve', action='store_true', help='Serve the marked-payment fixture on localhost only')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--database', default='receiver-demo.sqlite')
    args = parser.parse_args()
    if args.serve:
        receiver, _, payment, _ = setup(args.database)
        server = make_server(receiver, args.port)
        print('DEMO ONLY: public keys and fixed fictional clock. No wallet or funds. Localhost only.', flush=True)
        print('POST http://127.0.0.1:' + str(server.server_port) + '/admit', flush=True)
        print(json.dumps(payment), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            receiver.close()
    else:
        path = Path(__file__).resolve().parents[1] / 'examples' / 'receiver_demo.json'
        content = json.dumps(build_examples(), ensure_ascii=True, indent=2) + '\n'
        if args.check:
            assert path.read_text() == content, 'Stale receiver demo: python -m tools.receiver_demo'
            print('Receiver HTTP, persistence and decision scenarios verified.')
        else:
            path.write_text(content)
            print(path)
