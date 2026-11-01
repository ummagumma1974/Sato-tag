"""Synthetic evidence workflow with PUBLIC TEST KEYS; no real allegations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from satotag.evidence import CHECKS, evidence_screen, review_bytes
from satotag.engine import ValidationError
from satotag.registry import digest, evidence_digest
from tools.governance_demo import event, T1, T2
from tools.keyring_demo import fixture_manifest


def fixture_evidence():
    ledger, keys, payment, root, manifest = fixture_manifest()
    trust = manifest['payload']['trust']
    events = []
    for action, when in [('submit', T1), ('accept', T2)]:
        events.append(event(ledger, trust, keys, events, action, when))
    policy = {'version': 1, 'registry_id': trust['registry_id'], 'quorum': 2,
              'max_review_age_seconds': 3600, 'reviewers': {
                  k: {'person_id': 'fictional-person-' + k, 'organization_id': 'fictional-org-' + k}
                  for k in trust['reviewers']}}
    blobs = [b'invented demonstration evidence; no real theft', b'Fictional independent incident record. No real claim.']
    artifacts = {hashlib.sha256(b).hexdigest(): b for b in blobs}
    case = ledger['cases'][0]
    dossier = {'version': 1, 'case_id': case['case_id'], 'dataset_hash': digest(ledger),
               'evidence_hash': evidence_digest(case), 'claimant_person_id': 'fictional-claimant',
               'claimant_organization_id': 'fictional-claimant-org',
               'statement': 'Invented unauthorized transfer from origin:0; demonstration only.',
               'artifacts': [{'id': 'artifact-' + str(i), 'sha256': h, 'source_id': 'fictional-source-' + str(i),
                              'description': 'Synthetic record; not proof of a real event.'} for i, h in enumerate(artifacts)]}
    package = {'dossier': dossier, 'reviews': []}
    for reviewer in ('reviewer-a', 'reviewer-b'):
        p = {'version': 1, 'reviewer_id': reviewer, 'policy_hash': digest(policy),
             'acceptance_hash': digest(events[-1]), 'dossier_hash': digest(dossier), 'reviewed_at': T2,
             'conflict_of_interest': False, 'decision': 'approve', 'checks': {
                 name: {'outcome': 'pass', 'rationale': 'Fictional assessment of ' + name + '; fixture only, no human review performed.',
                        'artifact_ids': ['artifact-0', 'artifact-1']} for name in CHECKS}}
        package['reviews'].append({'payload': p, 'signature': keys[reviewer].sign(review_bytes(p)).hex()})
    args = dict(ledger=ledger, events=events, manifest=manifest,
                root_public_key=root.public_key().public_bytes_raw().hex(), expected_manifest=digest(manifest),
                now=T2, payment=payment, checkpoint=digest(events[-1]), policy=policy,
                expected_policy=digest(policy), packages={digest(events[-1]): package}, artifacts=artifacts)
    return args, keys, root


def build_examples():
    args, _, _ = fixture_evidence()
    result = evidence_screen(**args)
    scenarios = [{'name': 'Complete synthetic dossier', 'outcome': 'verified', 'detail': result['evidence_assurance']}]
    for title, change in [
        ('Missing evidence bytes', lambda a: a['artifacts'].clear()),
        ('Changed evidence bytes', lambda a: a['artifacts'].update({next(iter(a['artifacts'])): b'altered'})),
        ('Only one review', lambda a: next(iter(a['packages'].values()))['reviews'].pop()),
        ('Changed assessment', lambda a: next(iter(a['packages'].values()))['reviews'][0]['payload'].update(decision='reject')),
    ]:
        bad = deepcopy(args)
        change(bad)
        try:
            evidence_screen(**bad)
        except ValidationError as exc:
            scenarios.append({'name': title, 'outcome': 'blocked', 'detail': str(exc)})
        else:
            raise RuntimeError('Invalid evidence accepted: ' + title)
    serializable = deepcopy(args)
    serializable['artifacts'] = {h: b.decode('utf-8') for h, b in args['artifacts'].items()}
    return {'notice': 'PUBLIC TEST KEYS. FICTIONAL EVIDENCE AND IDENTITIES. No human investigation has taken place.',
            'fixture': serializable, 'result': result, 'scenarios': scenarios}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / 'examples' / 'evidence_review.json'
    content = json.dumps(build_examples(), ensure_ascii=True, indent=2) + '\n'
    if args.check:
        if not path.exists() or path.read_text() != content:
            raise SystemExit('Evidence fixture is stale: python -m tools.evidence_demo')
        print('Evidence fixture matches verified results.')
    else:
        path.write_text(content)
        print(path)
