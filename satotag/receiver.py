"""Local merchant admission prototype. No wallet, deposit credit or settlement.

Trusted host supplies invoices, evidence snapshots, independent pins and clock.
The payer supplies only a payment request, never a screening result or policy.
"""
from copy import deepcopy
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import ValidationError, _require
from .evidence import evidence_screen
from .registry import canonical


class Receiver:
    def __init__(self, database, invoices, context_provider, clock):
        self.invoices = deepcopy(invoices)
        self.context_provider = context_provider
        self.clock = clock
        self.lock = threading.Lock()
        self.db = sqlite3.connect(database, check_same_thread=False, isolation_level=None)
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.execute('PRAGMA busy_timeout = 5000')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS admissions (
                request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
                decision_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reservations (
                outpoint TEXT PRIMARY KEY,
                request_id TEXT NOT NULL REFERENCES admissions(request_id));
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, request_id TEXT, decision_json TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def admit(self, payment):
        """Check current host state on EVERY call, including idempotent retries.

        Accepted means local invoice admission only. Inputs are reserved locally;
        this does not prove input ownership, a mined payment or global uniqueness.
        """
        with self.lock:
            request_id = payment.get('request_id') if isinstance(payment, dict) else None
            request_id = request_id if isinstance(request_id, str) else None
            result = {'decision': 'blocked', 'request_id': request_id,
                      'scope': 'local_admission_only', 'funds_credited': False}
            try:
                _require(isinstance(payment, dict) and set(payment) == {'request_id', 'inputs', 'recipient', 'amount_sats'},
                         'Only payment fields are accepted')
                _require(request_id in self.invoices, 'Unknown invoice')
                invoice = self.invoices[request_id]
                _require(type(payment['amount_sats']) is int and
                         payment['amount_sats'] == invoice['amount_sats'] and
                         payment['recipient'] == invoice['recipient'], 'Invoice amount or recipient mismatch')
                context = deepcopy(self.context_provider())
                _require(isinstance(context, dict) and 'payment' not in context and 'now' not in context,
                         'Invalid host context')
                screen = evidence_screen(**context, payment=payment, now=self.clock())
                result.update(screening_result=screen['result'], snapshot_head=screen['snapshot_head'],
                              evidence_policy_sha256=screen['evidence_policy_sha256'],
                              key_manifest_sha256=screen['key_manifest_sha256'])
                if screen['result'] == 'marked':
                    result.update(decision='rejected', reason='Marked inputs are not admitted by this receiver')
                elif screen['result'] == 'review':
                    result.update(decision='held', reason='Unresolved claims require review')
                else:
                    _require(screen['result'] == 'no_known_mark', 'Unknown screening result')
                    fingerprint = screen['request_hash']
                    result.update(decision='accepted', request_hash=fingerprint,
                                  reason='No known mark in the supplied scope; local reservation only')
                    # One transaction protects invoice idempotency AND unique
                    # input reservations across threads/processes using this DB.
                    self.db.execute('BEGIN IMMEDIATE')
                    try:
                        old = self.db.execute('SELECT request_hash FROM admissions WHERE request_id=?', (request_id,)).fetchone()
                        _require(old is None or old[0] == fingerprint, 'Invoice already bound to a different payment')
                        for outpoint in payment['inputs']:
                            reservation = self.db.execute('SELECT request_id FROM reservations WHERE outpoint=?', (outpoint,)).fetchone()
                            _require(reservation is None or reservation[0] == request_id, 'Input already reserved for another invoice')
                        result['idempotent'] = old is not None
                        self.db.execute('INSERT OR IGNORE INTO admissions VALUES (?,?,?)',
                                        (request_id, fingerprint, json.dumps(result, sort_keys=True)))
                        for outpoint in payment['inputs']:
                            self.db.execute('INSERT OR IGNORE INTO reservations VALUES (?,?)', (outpoint, request_id))
                        self.db.execute('COMMIT')
                    except Exception:
                        self.db.execute('ROLLBACK')
                        raise
            except ValidationError as exc:
                result.update(decision='blocked', reason=str(exc))
            except Exception:
                # An unavailable source, bad integration or database error never
                # becomes an approval. No traceback or evidence is sent to payer.
                result.update(decision='blocked', reason='Verification unavailable')
            try:
                self.db.execute('INSERT INTO attempts (request_id, decision_json) VALUES (?,?)',
                                (request_id, json.dumps(result, sort_keys=True)))
            except sqlite3.Error:
                result.update(decision='blocked', reason='Audit storage unavailable')
            return result


def make_server(receiver, port=0):
    """Loopback-only experimental HTTP adapter. Not an internet-facing service."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, payload):
            raw = canonical(payload)
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if self.path != '/admit':
                self.respond(404, {'decision': 'blocked', 'reason': 'Unknown endpoint'})
                return
            try:
                _require(self.headers.get('Transfer-Encoding') is None, 'Chunked requests not supported')
                lengths = self.headers.get_all('Content-Length') or []
                _require(len(lengths) == 1 and lengths[0].isdigit(), 'One content length required')
                length = int(lengths[0])
                _require(0 < length <= 16384, 'Request exceeds 16 KiB or is empty')
                _require(self.headers.get_content_type() == 'application/json', 'JSON required')
                self.connection.settimeout(3)
                raw = self.rfile.read(length)
                _require(len(raw) == length, 'Incomplete body')
                from .__main__ import _unique_keys
                payment = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_keys)
            except (ValidationError, ValueError, UnicodeError, OSError, RecursionError):
                self.close_connection = True
                self.respond(400, {'decision': 'blocked', 'reason': 'Invalid request'})
                return
            result = receiver.admit(payment)
            status = {'accepted': 200, 'rejected': 403, 'held': 409, 'blocked': 503}[result['decision']]
            self.respond(status, result)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
