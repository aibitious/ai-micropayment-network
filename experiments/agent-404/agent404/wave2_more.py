"""Additional bounded offline agent decision aids for the broad exploration cohort."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import math

from .lab import LabInputError


def need(ok, message):
    if not ok:
        raise LabInputError(message)


def items(value, name, maximum=100):
    need(isinstance(value, list) and len(value) <= maximum, f'{name} must be a list of at most {maximum} items')
    return value


def ident(value, name):
    need(isinstance(value, str) and 1 <= len(value) <= 80 and value.isascii()
         and all(c.isalnum() or c in '._-:/#' for c in value), f'{name} must be a short identifier')
    return value


def integer(value, name, low=0, high=1000000):
    need(type(value) is int and low <= value <= high, f'{name} must be an integer from {low} to {high}')
    return value


def money(value, name):
    need(isinstance(value, (str, int, float)) and not isinstance(value, bool), f'{name} must be numeric')
    try: amount = Decimal(str(value))
    except InvalidOperation: raise LabInputError(f'{name} must be numeric') from None
    need(amount.is_finite() and 0 <= amount <= 1000000000, f'{name} out of range')
    return amount


def outcome(slug, issues, **details):
    return {'tool': slug, 'status': 'issues' if issues else 'ok',
            'findings': issues[:30], 'details': details, 'limitations': LIMITATIONS[slug]}


def issue(code, path='', severity='warning'):
    return {'code': code, 'path': path, 'severity': severity}


def scope_delta(p):
    before = set(ident(x,'before permission') for x in items(p.get('before'),'before'))
    after = set(ident(x,'after permission') for x in items(p.get('after'),'after'))
    approved = set(ident(x,'approved permission') for x in items(p.get('approved_additions',[]),'approved_additions'))
    added = sorted(after-before)
    unapproved = sorted(set(added)-approved)
    return outcome('scope_delta',[issue('unapproved_scope',x,'error') for x in unapproved],
                   added=added,removed=sorted(before-after),unapproved_additions=unapproved)


def approval_packet(p):
    action = p.get('action')
    need(isinstance(action,dict),'action must be an object')
    required = ('actor','tool','target','effect','reason','expiry_unix')
    missing = [key for key in required if action.get(key) in (None,'')]
    for key in required[:-1]:
        if key not in missing: ident(action[key],key)
    if 'expiry_unix' not in missing: integer(action['expiry_unix'],'expiry_unix',1,4102444800)
    now = integer(p.get('now_unix'),'now_unix',1,4102444800)
    if 'expiry_unix' not in missing and action['expiry_unix'] <= now:
        missing.append('valid_expiry')
    return outcome('approval_packet',[issue('missing_or_expired',x,'error') for x in missing],
                   ready=not missing,missing=missing)


def budget_envelope(p):
    limit = money(p.get('limit_usd'),'limit_usd')
    spent = money(p.get('spent_usd'),'spent_usd')
    reserved = money(p.get('reserved_usd'),'reserved_usd')
    proposed = money(p.get('proposed_worst_case_usd'),'proposed_worst_case_usd')
    margin = money(p.get('margin_usd',0),'margin_usd')
    projected = spent+reserved+proposed+margin
    findings = [issue('budget_exceeded','proposed_worst_case_usd','error')] if projected > limit else []
    return outcome('budget_envelope',findings,admit=not findings,
                   projected_usd=str(projected),remaining_usd=str(limit-projected))


def retry_schedule(p):
    attempts=integer(p.get('attempts'),'attempts',1,20)
    first=integer(p.get('first_delay_seconds'),'first_delay_seconds',1,86400)
    cap=integer(p.get('max_delay_seconds'),'max_delay_seconds',1,86400)
    deadline=integer(p.get('deadline_seconds'),'deadline_seconds',1,604800)
    delays=[];elapsed=0
    for n in range(attempts):
        delay=min(cap,first*(2**n))
        if elapsed+delay>deadline: break
        delays.append(delay);elapsed+=delay
    findings=[issue('attempts_do_not_fit_deadline','deadline_seconds')] if len(delays)<attempts else []
    return outcome('retry_schedule',findings,delays_seconds=delays,total_wait_seconds=elapsed,
                   remaining_attempts=attempts-len(delays),jitter_required_in_production=True)


def duplicate_actions(p):
    calls=items(p.get('calls'),'calls')
    seen={};findings=[]
    for index,call in enumerate(calls):
        need(isinstance(call,dict),'Each call must be an object')
        key=ident(call.get('idempotency_key'),'idempotency_key')
        fingerprint=ident(call.get('payload_fingerprint'),'payload_fingerprint')
        if key in seen:
            code='key_reused_for_different_payload' if seen[key]!=fingerprint else 'duplicate_attempt'
            findings.append(issue(code,str(index),'error' if code.startswith('key_reused') else 'warning'))
        else: seen[key]=fingerprint
    return outcome('duplicate_actions',findings,unique_keys=len(seen),attempts=len(calls))


def prerequisite_gate(p):
    requirements=items(p.get('requirements'),'requirements')
    evidence=set(ident(x,'evidence') for x in items(p.get('available_evidence'),'available_evidence'))
    missing=[]
    for row in requirements:
        need(isinstance(row,dict),'Each requirement must be an object')
        name=ident(row.get('id'),'requirement.id')
        refs=[ident(x,'evidence_ref') for x in items(row.get('evidence_refs',[]),'evidence_refs',20)]
        if not refs or not all(ref in evidence for ref in refs): missing.append(name)
    return outcome('prerequisite_gate',[issue('missing_evidence',x,'error') for x in missing],
                   ready=not missing,missing=missing)


def evidence_expiry(p):
    now=integer(p.get('now_unix'),'now_unix',1,4102444800)
    records=items(p.get('records'),'records')
    findings=[];fresh=[]
    for record in records:
        need(isinstance(record,dict),'Each record must be an object')
        name=ident(record.get('id'),'record.id')
        observed=integer(record.get('observed_unix'),'observed_unix',0,4102444800)
        ttl=integer(record.get('ttl_seconds'),'ttl_seconds',0,31536000)
        if observed>now: findings.append(issue('future_observation',name,'error'))
        elif now-observed>ttl: findings.append(issue('stale_evidence',name,'error'))
        else: fresh.append(name)
    return outcome('evidence_expiry',findings,fresh=fresh,stale_or_invalid=[x['path'] for x in findings])


def citation_matrix(p):
    claims=items(p.get('claims'),'claims')
    citations=set(ident(x,'citation') for x in items(p.get('citations'),'citations'))
    missing=[];unknown=[]
    for claim in claims:
        need(isinstance(claim,dict),'Each claim must be an object')
        name=ident(claim.get('id'),'claim.id')
        refs=[ident(x,'citation_ref') for x in items(claim.get('citation_refs',[]),'citation_refs',20)]
        if not refs: missing.append(name)
        unknown += [f'{name}/{ref}' for ref in refs if ref not in citations]
    findings=[issue('uncited_claim',x,'error') for x in missing]
    findings += [issue('unknown_citation',x,'error') for x in unknown]
    return outcome('citation_matrix',findings,claim_count=len(claims),uncited_count=len(missing))


def schema_impact(p):
    before=p.get('before');after=p.get('after')
    need(isinstance(before,dict) and isinstance(after,dict),'before and after must be objects')
    consumers=items(p.get('consumers'),'consumers')
    findings=[];affected=[]
    for consumer in consumers:
        need(isinstance(consumer,dict),'Each consumer must be an object')
        name=ident(consumer.get('id'),'consumer.id')
        required=[ident(x,'required field') for x in items(consumer.get('required_fields',[]),'required_fields',50)]
        broken=[key for key in required if key not in after or (key in before and type(before[key]) is not type(after[key]))]
        if broken:
            affected.append({'consumer':name,'fields':broken})
            findings.append(issue('consumer_breakage',name,'error'))
    return outcome('schema_impact',findings,affected_consumers=affected,
                   removed_fields=sorted(set(before)-set(after)),added_fields=sorted(set(after)-set(before)))


def boundary_cases(p):
    fields=items(p.get('fields'),'fields',30)
    cases=[]
    for field in fields:
        need(isinstance(field,dict),'Each field must be an object')
        name=ident(field.get('name'),'field.name')
        kind=field.get('type')
        need(kind in ('integer','string','boolean'),'type must be integer, string or boolean')
        if kind=='integer':
            low=integer(field.get('minimum',0),'minimum',-1000000,1000000)
            high=integer(field.get('maximum',100),'maximum',-1000000,1000000)
            need(low<=high,'minimum exceeds maximum')
            cases += [{'field':name,'value':value,'expected':'valid' if low<=value<=high else 'invalid'}
                      for value in (low-1,low,high,high+1)]
        elif kind=='string':
            limit=integer(field.get('max_length',100),'max_length',0,1000)
            cases += [{'field':name,'length':length,'expected':'valid' if length<=limit else 'invalid'}
                      for length in (0,limit,limit+1)]
        else: cases += [{'field':name,'value':False,'expected':'valid'},
                       {'field':name,'value':True,'expected':'valid'}]
    return outcome('boundary_cases',[],cases=cases[:120],generated=len(cases))


def slo_burn(p):
    target=money(p.get('target_percent'),'target_percent')
    need(target<100,'target_percent must be below 100')
    total=integer(p.get('total'),'total',1,1000000000)
    bad=integer(p.get('bad'),'bad',0,total)
    allowed=(Decimal(100)-target)/100
    observed=Decimal(bad)/Decimal(total)
    burn=observed/allowed if allowed else Decimal('Infinity')
    threshold=money(p.get('alert_burn_rate',2),'alert_burn_rate')
    findings=[issue('burn_rate_high','bad','error')] if burn>=threshold else []
    return outcome('slo_burn',findings,burn_rate=str(burn.quantize(Decimal('0.001'))),
                   observed_bad_percent=str((observed*100).quantize(Decimal('0.001'))),
                   sample_size=total)


def queue_forecast(p):
    backlog=integer(p.get('backlog'),'backlog',0,100000000)
    incoming=integer(p.get('incoming_per_hour'),'incoming_per_hour',0,100000000)
    capacity=integer(p.get('capacity_per_hour'),'capacity_per_hour',0,100000000)
    hours=integer(p.get('horizon_hours'),'horizon_hours',1,720)
    projected=max(0,backlog+(incoming-capacity)*hours)
    findings=[issue('backlog_grows','capacity_per_hour','error')] if projected>backlog else []
    drain=math.ceil(backlog/(capacity-incoming)) if backlog and capacity>incoming else None
    return outcome('queue_forecast',findings,projected_backlog=projected,
                   drain_hours=drain,capacity_gap_per_hour=capacity-incoming)


def permission_paths(p):
    edges=items(p.get('edges'),'edges',100)
    start=ident(p.get('start'),'start')
    sensitive=set(ident(x,'sensitive target') for x in items(p.get('sensitive_targets'),'sensitive_targets'))
    graph=defaultdict(set)
    for edge in edges:
        need(isinstance(edge,dict),'Each edge must be an object')
        graph[ident(edge.get('from'),'edge.from')].add(ident(edge.get('to'),'edge.to'))
    queue=[start];seen={start}
    for node in queue:
        for child in sorted(graph[node]):
            if child not in seen:
                seen.add(child);queue.append(child)
        need(len(seen)<=101,'Graph too large')
    reached=sorted(seen&sensitive)
    return outcome('permission_paths',[issue('sensitive_reachable',x,'error') for x in reached],
                   reached_sensitive_targets=reached,reachable_nodes=len(seen))


def context_budget(p):
    capacity=integer(p.get('max_tokens'),'max_tokens',1,1000000)
    chunks=items(p.get('chunks'),'chunks',100)
    parsed=[]
    for chunk in chunks:
        need(isinstance(chunk,dict),'Each chunk must be an object')
        parsed.append((ident(chunk.get('id'),'chunk.id'),
                       integer(chunk.get('tokens'),'chunk.tokens',1,1000000),
                       integer(chunk.get('priority'),'chunk.priority',0,100)))
    need(len({x[0] for x in parsed})==len(parsed),'Duplicate chunk.id')
    parsed.sort(key=lambda x:(-x[2]/x[1],-x[2],x[0]))
    chosen=[];used=0
    for name,tokens,_ in parsed:
        if used+tokens<=capacity: chosen.append(name);used+=tokens
    findings=[issue('chunks_excluded','max_tokens')] if len(chosen)<len(parsed) else []
    return outcome('context_budget',findings,selected=chosen,used_tokens=used,
                   excluded=sorted(set(x[0] for x in parsed)-set(chosen)),algorithm='greedy_priority_density')


def release_gate(p):
    checks=items(p.get('checks'),'checks',100)
    required=set(ident(x,'required check') for x in items(p.get('required'),'required',100))
    status={}
    for check in checks:
        need(isinstance(check,dict),'Each check must be an object')
        name=ident(check.get('id'),'check.id')
        need(name not in status,'Duplicate check.id')
        need(check.get('status') in ('success','failed','pending'),'Invalid check.status')
        status[name]=check['status']
    blocked=sorted(x for x in required if status.get(x)!='success')
    findings=[issue('required_check_not_green',x,'error') for x in blocked]
    return outcome('release_gate',findings,ready=not blocked,blocked=blocked)


def manifest_drift(p):
    expected=p.get('expected');observed=p.get('observed')
    need(isinstance(expected,dict) and isinstance(observed,dict),'expected and observed must be objects')
    need(len(expected)<=100 and len(observed)<=100,'Too many manifest entries')
    for key in set(expected)|set(observed): ident(key,'manifest key')
    missing=sorted(set(expected)-set(observed))
    extra=sorted(set(observed)-set(expected))
    changed=sorted(k for k in set(expected)&set(observed) if expected[k]!=observed[k])
    findings=[issue('missing_entry',k,'error') for k in missing]
    findings += [issue('changed_entry',k,'error') for k in changed]
    findings += [issue('extra_entry',k) for k in extra]
    return outcome('manifest_drift',findings,missing=missing,changed=changed,extra=extra)


def receipt_chain(p):
    receipts=items(p.get('receipts'),'receipts',100)
    previous=p.get('root_sha256')
    need(isinstance(previous,str) and len(previous)==64 and all(c in '0123456789abcdef' for c in previous),
         'root_sha256 must be lowercase SHA-256 hex')
    findings=[]
    for i,receipt in enumerate(receipts):
        need(isinstance(receipt,dict),'Each receipt must be an object')
        digest=receipt.get('sha256');parent=receipt.get('previous_sha256')
        need(isinstance(digest,str) and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),
             'receipt.sha256 must be lowercase SHA-256 hex')
        if parent!=previous: findings.append(issue('broken_chain',str(i),'error'))
        previous=digest
    return outcome('receipt_chain',findings,receipts_checked=len(receipts),head_sha256=previous,
                   note='Only linkage is checked; bytes and signatures are not verified.')


TOOLS={
 'scope_delta':('Permission Scope Delta','Find newly granted permissions outside an approved set.'),
 'approval_packet':('Approval Packet Check','Find missing or expired fields before seeking human approval.'),
 'budget_envelope':('Budget Envelope','Check worst-case proposed cost against a local hard budget.'),
 'retry_schedule':('Retry Schedule','Preview capped exponential retries against a deadline.'),
 'duplicate_actions':('Idempotency Audit','Find duplicate attempts and conflicting key reuse.'),
 'prerequisite_gate':('Prerequisite Gate','Check whether all declared evidence prerequisites are present.'),
 'evidence_expiry':('Evidence Freshness','Flag stale observations before an agent acts.'),
 'citation_matrix':('Citation Matrix','Find claims with missing or unknown citation identifiers.'),
 'schema_impact':('Consumer Schema Impact','Identify downstream consumers broken by changed fields.'),
 'boundary_cases':('Boundary Case Builder','Generate bounded edge cases from simple field constraints.'),
 'slo_burn':('SLO Burn Check','Measure error-budget burn against a supplied target.'),
 'queue_forecast':('Queue Capacity Forecast','Project backlog and drain time from supplied rates.'),
 'permission_paths':('Permission Path Explorer','Find sensitive targets reachable through declared capability edges.'),
 'context_budget':('Context Budget Packer','Select prioritized context chunks inside a token limit.'),
 'release_gate':('Release Gate Check','Require named checks to be green before a release.'),
 'manifest_drift':('Manifest Drift','Compare expected and observed resource manifests.'),
 'receipt_chain':('Receipt Chain Check','Check links in a supplied digest receipt chain.'),
}
LIMITATIONS={slug:'Offline supplied-data analysis only; it does not enforce policy or verify live systems.' for slug in TOOLS}
LIMITATIONS['context_budget']='Greedy heuristic; it does not guarantee the mathematically optimal selection.'
LIMITATIONS['receipt_chain']='Checks digest links only, not signatures or underlying bytes.'
LIMITATIONS['budget_envelope']='Uses supplied amounts; it cannot guarantee a provider billing hard stop.'
EXAMPLES={
 'scope_delta':{'before':['read'],'after':['read','send'],'approved_additions':[]},
 'approval_packet':{'now_unix':100,'action':{'actor':'agent','tool':'mail.send','target':'draft1','effect':'send','reason':'owner_request','expiry_unix':200}},
 'budget_envelope':{'limit_usd':'0','spent_usd':'0','reserved_usd':'0','proposed_worst_case_usd':'0'},
 'retry_schedule':{'attempts':3,'first_delay_seconds':2,'max_delay_seconds':10,'deadline_seconds':30},
 'duplicate_actions':{'calls':[{'idempotency_key':'k1','payload_fingerprint':'hash1'},{'idempotency_key':'k1','payload_fingerprint':'hash1'}]},
 'prerequisite_gate':{'requirements':[{'id':'deploy','evidence_refs':['ci']}],'available_evidence':['ci']},
 'evidence_expiry':{'now_unix':200,'records':[{'id':'health','observed_unix':100,'ttl_seconds':120}]},
 'citation_matrix':{'claims':[{'id':'claim1','citation_refs':['src1']}],'citations':['src1']},
 'schema_impact':{'before':{'id':1},'after':{},'consumers':[{'id':'client','required_fields':['id']}]},
 'boundary_cases':{'fields':[{'name':'count','type':'integer','minimum':0,'maximum':10}]},
 'slo_burn':{'target_percent':'99','total':1000,'bad':20,'alert_burn_rate':2},
 'queue_forecast':{'backlog':100,'incoming_per_hour':10,'capacity_per_hour':20,'horizon_hours':4},
 'permission_paths':{'start':'agent','edges':[{'from':'agent','to':'secret'}],'sensitive_targets':['secret']},
 'context_budget':{'max_tokens':100,'chunks':[{'id':'source1','tokens':40,'priority':10}]},
 'release_gate':{'required':['test'],'checks':[{'id':'test','status':'success'}]},
 'manifest_drift':{'expected':{'version':'1'},'observed':{'version':'2'}},
 'receipt_chain':{'root_sha256':'0'*64,'receipts':[{'previous_sha256':'0'*64,'sha256':'1'*64}]},
}
HANDLERS={name:globals()[name] for name in TOOLS}
