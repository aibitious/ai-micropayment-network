"""Second-wave, offline decision aids. Inputs are never persisted."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json

from .lab import LabInputError


TOOLS = {
    'action_policy': ('Action Policy Simulator', 'Check an agent action against explicit allow, deny and approval rules.'),
    'workflow_recovery': ('Workflow Recovery Planner', 'Order compensations for a failed multi-step workflow.'),
    'webhook_triage': ('Webhook Delivery Triage', 'Diagnose retry and duplicate risks from supplied delivery attempts.'),
    'claim_provenance': ('Claim Provenance Check', 'Find unsupported or circular claims in a supplied evidence graph.'),
    'data_minimizer': ('Data Minimizer', 'Compare proposed agent data fields with a declared task and retention policy.'),
}
LIMITATIONS = {
    'action_policy': 'Simulation only; it does not enforce access or authenticate an actor.',
    'workflow_recovery': 'A plan only; it never executes a compensation or guarantees reversibility.',
    'webhook_triage': 'Supplied attempt metadata only; no live delivery, signature or provider verification.',
    'claim_provenance': 'Graph consistency only; it cannot establish the truth or quality of a source.',
    'data_minimizer': 'Declared fields only; it cannot inspect actual data or certify privacy compliance.',
}
EXAMPLES = {
    'action_policy': {'action': {'tool': 'mail.send', 'effect': 'send'},
                      'rules': [{'tool': '*', 'effect': 'send', 'decision': 'approval'}]},
    'workflow_recovery': {'steps': [{'id': 'reserve', 'state': 'completed', 'compensation': 'release'},
                                    {'id': 'charge', 'state': 'failed', 'depends_on': ['reserve']}]},
    'webhook_triage': {'attempts': [{'event_id': 'event1', 'status': 500, 'at': 1794300000},
                                    {'event_id': 'event1', 'status': 200, 'at': 1794300060}]},
    'claim_provenance': {'sources': [{'id': 'source1'}],
                         'claims': [{'id': 'claim1', 'evidence': ['source1']}]},
    'data_minimizer': {'fields': [{'name': 'email', 'retention_days': 30,
                                  'sensitivity': 'personal', 'sent_to_model': False}],
                       'allowed_fields': ['email'], 'max_retention_days': 30},
}


def describe_tools():
    return [{'slug': slug, 'name': name, 'description': description,
             'path': f'/v1/wave2/{slug}', 'method': 'POST',
             'limitations': LIMITATIONS[slug], 'example_input': EXAMPLES[slug],
             'price': {'amount': 0, 'currency': 'USD'}}
            for slug, (name, description) in TOOLS.items()]


def _require(condition, message):
    if not condition:
        raise LabInputError(message)


def _items(value, name, maximum=100):
    _require(isinstance(value, list) and len(value) <= maximum, f'{name} must be a list of at most {maximum} items')
    return value


def _name(value, name):
    _require(isinstance(value, str) and 1 <= len(value) <= 80 and value.isascii()
             and all(c.isalnum() or c in '_-./:' for c in value), f'{name} must be a short identifier')
    return value


def _result(slug, findings, **details):
    return {'tool': slug, 'status': 'issues' if findings else 'ok',
            'findings': findings[:30], 'details': details, 'limitations': LIMITATIONS[slug]}


def _finding(code, path, severity='warning'):
    return {'code': code, 'path': path, 'severity': severity}


def action_policy(p):
    action = p.get('action')
    _require(isinstance(action, dict), 'action must be an object')
    tool = _name(action.get('tool'), 'action.tool')
    effect = action.get('effect')
    _require(effect in ('read', 'write', 'send', 'spend', 'delete'), 'Invalid action.effect')
    rules = _items(p.get('rules'), 'rules', 50)
    matches = []
    for i, rule in enumerate(rules):
        _require(isinstance(rule, dict), 'Each rule must be an object')
        rtool = rule.get('tool')
        _require(rtool == '*' or _name(rtool, 'rule.tool'), 'Invalid rule.tool')
        reffect = rule.get('effect')
        _require(reffect in ('*', 'read', 'write', 'send', 'spend', 'delete'), 'Invalid rule.effect')
        _require(rule.get('decision') in ('allow', 'deny', 'approval'), 'Invalid rule.decision')
        if rtool in ('*', tool) and reffect in ('*', effect):
            matches.append((i, rule['decision']))
    decisions = [decision for _, decision in matches]
    decision = 'deny' if 'deny' in decisions or not decisions else ('approval' if 'approval' in decisions else 'allow')
    findings = [] if decision == 'allow' else [_finding('action_blocked' if decision == 'deny' else 'approval_required', 'action', 'error')]
    return _result('action_policy', findings, decision=decision,
                   matching_rule_indexes=[i for i, _ in matches], default='deny')


def workflow_recovery(p):
    steps = _items(p.get('steps'), 'steps', 50)
    _require(bool(steps), 'steps cannot be empty')
    ids = []
    completed = []
    dependency = {}
    compensation = {}
    for step in steps:
        _require(isinstance(step, dict), 'Each step must be an object')
        ident = _name(step.get('id'), 'step.id')
        ids.append(ident)
        deps = [_name(x, 'depends_on item') for x in _items(step.get('depends_on', []), 'depends_on', 20)]
        dependency[ident] = deps
        state = step.get('state')
        _require(state in ('pending', 'completed', 'failed'), 'Invalid step.state')
        if state == 'completed': completed.append(ident)
        comp = step.get('compensation')
        _require(comp is None or isinstance(comp, str) and 1 <= len(comp) <= 120, 'Invalid compensation')
        compensation[ident] = comp
    _require(len(ids) == len(set(ids)), 'Duplicate step.id')
    _require(all(d in ids and d != s for s, deps in dependency.items() for d in deps), 'Unknown or self dependency')
    order = []
    visiting = set()
    visited = set()
    def visit(node):
        _require(node not in visiting, 'Dependency cycle')
        if node in visited: return
        visiting.add(node)
        for dep in dependency[node]: visit(dep)
        visiting.remove(node)
        visited.add(node)
        order.append(node)
    for ident in ids: visit(ident)
    completed_set = set(completed)
    plan = [{'step': ident, 'compensation': compensation[ident]}
            for ident in reversed(order) if ident in completed_set and compensation[ident]]
    irreversible = [ident for ident in reversed(order) if ident in completed_set and not compensation[ident]]
    findings = [_finding('missing_compensation', ident, 'error') for ident in irreversible]
    findings += [_finding('dependency_not_completed', f'{s}/{d}') for s in completed for d in dependency[s] if d not in completed_set]
    return _result('workflow_recovery', findings, compensation_plan=plan,
                   irreversible_steps=irreversible, plan_requires_human_review=True)


def webhook_triage(p):
    attempts = _items(p.get('attempts'), 'attempts', 100)
    _require(bool(attempts), 'attempts cannot be empty')
    groups = defaultdict(list)
    for attempt in attempts:
        _require(isinstance(attempt, dict), 'Each attempt must be an object')
        event_id = _name(attempt.get('event_id'), 'event_id')
        status = attempt.get('status')
        _require(isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599, 'Invalid HTTP status')
        when = attempt.get('at')
        _require(isinstance(when, int) and not isinstance(when, bool) and 0 <= when <= 4102444800, 'at must be a Unix timestamp')
        groups[event_id].append((when, status))
    findings = []
    summaries = []
    for event_id, values in sorted(groups.items()):
        values.sort()
        successes = sum(200 <= status < 300 for _, status in values)
        if successes > 1: findings.append(_finding('duplicate_success', event_id, 'error'))
        if not successes: findings.append(_finding('undelivered', event_id, 'error'))
        if any(status in (401, 403) for _, status in values): findings.append(_finding('authentication_failure', event_id, 'error'))
        if any(status == 429 for _, status in values): findings.append(_finding('rate_limited', event_id))
        if any(500 <= status < 600 for _, status in values): findings.append(_finding('server_error', event_id))
        summaries.append({'event_id': event_id, 'attempt_count': len(values), 'success_count': successes,
                          'last_status': values[-1][1]})
    return _result('webhook_triage', findings, events=summaries,
                   note='Verify signatures and idempotency in the real handler before replaying.')


def claim_provenance(p):
    sources = _items(p.get('sources'), 'sources', 100)
    claims = _items(p.get('claims'), 'claims', 100)
    source_ids = set()
    for source in sources:
        _require(isinstance(source, dict), 'Each source must be an object')
        source_ids.add(_name(source.get('id'), 'source.id'))
    _require(len(source_ids) == len(sources), 'Duplicate source.id')
    graph = {}
    for claim in claims:
        _require(isinstance(claim, dict), 'Each claim must be an object')
        ident = _name(claim.get('id'), 'claim.id')
        _require(ident not in graph, 'Duplicate claim.id')
        refs = [_name(x, 'evidence item') for x in _items(claim.get('evidence', []), 'evidence', 20)]
        graph[ident] = refs
    findings = []
    for ident, refs in graph.items():
        if not refs: findings.append(_finding('unsupported_claim', ident, 'error'))
        for ref in refs:
            if ref not in source_ids and ref not in graph: findings.append(_finding('unknown_evidence', f'{ident}/{ref}', 'error'))
    def reaches_source(node, seen):
        if node in seen: return False
        return any(ref in source_ids or (ref in graph and reaches_source(ref, seen | {node}))
                   for ref in graph[node])
    for ident in graph:
        if graph[ident] and not reaches_source(ident, set()):
            findings.append(_finding('no_source_path', ident, 'error'))
    return _result('claim_provenance', findings, claims=len(graph), sources=len(source_ids),
                   source_reachable_claims=sum(reaches_source(i, set()) for i in graph))


def data_minimizer(p):
    fields = _items(p.get('fields'), 'fields', 100)
    allowed = {_name(x, 'allowed field') for x in _items(p.get('allowed_fields'), 'allowed_fields', 100)}
    max_days = p.get('max_retention_days')
    _require(isinstance(max_days, int) and not isinstance(max_days, bool) and 0 <= max_days <= 3650,
             'max_retention_days must be 0..3650')
    findings = []
    names = []
    for field in fields:
        _require(isinstance(field, dict), 'Each field must be an object')
        name = _name(field.get('name'), 'field.name')
        names.append(name)
        days = field.get('retention_days')
        _require(isinstance(days, int) and not isinstance(days, bool) and 0 <= days <= 3650,
                 'retention_days must be 0..3650')
        if name not in allowed: findings.append(_finding('undeclared_field', name, 'error'))
        if days > max_days: findings.append(_finding('retention_exceeds_limit', name, 'error'))
        if field.get('sent_to_model') is True and field.get('sensitivity') in ('personal', 'secret'):
            findings.append(_finding('sensitive_model_transfer', name, 'error'))
    _require(len(names) == len(set(names)), 'Duplicate field.name')
    return _result('data_minimizer', findings, checked_fields=len(names),
                   undeclared_fields=sum(f['code'] == 'undeclared_field' for f in findings))


HANDLERS = {'action_policy': action_policy, 'workflow_recovery': workflow_recovery,
            'webhook_triage': webhook_triage, 'claim_provenance': claim_provenance,
            'data_minimizer': data_minimizer}


def run(slug, payload):
    _require(slug in HANDLERS, 'Unknown wave-two prototype')
    _require(isinstance(payload, dict), 'Input must be a JSON object')
    try: encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError): raise LabInputError('Input must be finite JSON') from None
    _require(len(encoded.encode('utf-8')) <= 20000, 'Input exceeds 20 KB')
    return HANDLERS[slug](payload)
