import pytest
from fastapi.testclient import TestClient

from agent404.api import create_app
from agent404.lab import LabInputError
from agent404 import wave2


@pytest.mark.parametrize('slug', sorted(wave2.wave2_more.TOOLS))
def test_expanded_prototype_examples(slug):
    result = wave2.run(slug, wave2.EXAMPLES[slug])
    assert result['tool'] == slug
    assert result['status'] in ('ok','issues')
    assert isinstance(result['details'], dict)


def test_expanded_high_risk_decisions():
    assert wave2.run('budget_envelope', {'limit_usd':'0','spent_usd':'0',
        'reserved_usd':'0','proposed_worst_case_usd':'0.01'})['details']['admit'] is False
    assert wave2.run('release_gate', {'required':['ci'],
        'checks':[{'id':'ci','status':'pending'}]})['details']['ready'] is False
    assert wave2.run('scope_delta', {'before':['read'],'after':['read','delete'],
        'approved_additions':[]})['details']['unapproved_additions'] == ['delete']


def test_mcp_exposes_all_distinct_tools_with_examples():
    from agent404.mcp_server import mcp
    listed = mcp._tool_manager.list_tools()
    names = [tool.name for tool in listed]
    assert len(names) == len(set(names)) == 35
    assert {"company_card", "project_signals"} <= set(names)
    for slug in wave2.wave2_more.TOOLS:
        tool = next(item for item in listed if item.name == slug)
        assert 'Supply payload like' in tool.description
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False
        assert tool.annotations.idempotent_hint is False


def test_every_prototype_rest_route(tmp_path):
    app = create_app(db_path=str(tmp_path/'all.sqlite3'), secret='test-secret')
    with TestClient(app) as client:
        for slug in wave2.TOOLS:
            response = client.post(f'/v1/wave2/{slug}', json=wave2.EXAMPLES[slug])
            assert response.status_code == 200, (slug, response.text)
            assert response.json()['tool'] == slug


def test_all_five_decision_aids():
    policy = wave2.run('action_policy', {'action': {'tool':'mail.send','effect':'send'},
        'rules':[{'tool':'*','effect':'send','decision':'approval'}]})
    assert policy['details']['decision'] == 'approval'
    assert wave2.run('action_policy', {'action': {'tool':'mail.send','effect':'send'},
        'rules':[]})['details']['decision'] == 'deny'

    recovery = wave2.run('workflow_recovery', {'steps':[
        {'id':'reserve','state':'completed','compensation':'release'},
        {'id':'charge','state':'completed','depends_on':['reserve'],'compensation':'refund'},
        {'id':'notify','state':'failed','depends_on':['charge']} ]})
    assert [x['step'] for x in recovery['details']['compensation_plan']] == ['charge','reserve']

    hooks = wave2.run('webhook_triage', {'attempts':[
        {'event_id':'evt1','status':500,'at':100},
        {'event_id':'evt1','status':200,'at':200},
        {'event_id':'evt1','status':200,'at':300}]})
    assert 'duplicate_success' in [x['code'] for x in hooks['findings']]

    claims = wave2.run('claim_provenance', {'sources':[{'id':'src1'}], 'claims':[
        {'id':'a','evidence':['src1']}, {'id':'b','evidence':['a']},
        {'id':'c','evidence':['d']}, {'id':'d','evidence':['c']}]})
    assert claims['details']['source_reachable_claims'] == 2
    assert {'c','d'} == {x['path'] for x in claims['findings'] if x['code']=='no_source_path'}

    privacy = wave2.run('data_minimizer', {'fields':[
        {'name':'email','retention_days':90,'sent_to_model':True,'sensitivity':'personal'}],
        'allowed_fields':[], 'max_retention_days':30})
    assert {x['code'] for x in privacy['findings']} == {
        'undeclared_field','retention_exceeds_limit','sensitive_model_transfer'}


def test_reject_cycles_and_large_inputs():
    with pytest.raises(LabInputError, match='cycle'):
        wave2.run('workflow_recovery', {'steps':[
            {'id':'a','state':'completed','depends_on':['b']},
            {'id':'b','state':'completed','depends_on':['a']}]})
    with pytest.raises(LabInputError, match='20 KB'):
        wave2.run('action_policy', {'junk':'x'*20001})


def test_isolated_funnel_and_original_baseline(tmp_path, monkeypatch):
    monkeypatch.setenv('ADMIN_TOKEN','test-admin')
    app = create_app(db_path=str(tmp_path/'events.sqlite3'), secret='test-secret')
    with TestClient(app) as client:
        assert client.get('/health').json()['experiments'] == 10
        assert client.get('/health').json()['wave2_prototypes'] == 22
        assert client.get('/v1/lab/catalog').json()['experiments'] == 10
        assert len(client.get('/v1/wave2/catalog').json()['prototypes']) == 22
        assert client.get('/wave2/action_policy').status_code == 200
        action = {'action': {'tool':'read_file','effect':'read'},
                  'rules':[{'tool':'read_file','effect':'read','decision':'allow'}]}
        assert client.post('/v1/wave2/action_policy',json=action).json()['status'] == 'ok'
        assert client.post('/v1/wave2/action_policy/interest',json={'signal':'pilot'}).status_code == 200
        assert client.get('/v1/wave2/metrics').status_code == 403
        metrics = client.get('/v1/wave2/metrics',headers={'Authorization':'Bearer test-admin'}).json()
        stages = {x['stage'] for x in metrics['funnel_events'] if x['tool']=='action_policy'}
        assert stages == {'discovery','launch','paid_demand_signal'}
        assert client.get('/v1/lab/metrics',headers={'Authorization':'Bearer test-admin'}).status_code == 200


def test_marked_internal_calls_excluded(tmp_path, monkeypatch):
    monkeypatch.setenv('ADMIN_TOKEN','test-admin')
    app = create_app(db_path=str(tmp_path/'internal.sqlite3'), secret='test-secret')
    with TestClient(app) as client:
        headers={'x-404-internal-test':'test-admin'}
        client.get('/v1/wave2/catalog',headers=headers)
        client.post('/v1/wave2/action_policy',json={'action':{'tool':'x','effect':'read'},'rules':[]},headers=headers)
        metrics = client.get('/v1/wave2/metrics',headers={'Authorization':'Bearer test-admin'}).json()
        assert metrics['funnel_events'] == []
        assert any(x['stage']=='launch' for x in metrics['internal_test_events'])


def test_return_is_distinct_day_launch_only(tmp_path):
    app = create_app(db_path=str(tmp_path/'returns.sqlite3'), secret='test-secret')
    store = app.state.store
    store.wave2_event('action_policy','network1','discovery','catalog','rest')
    store.wave2_event('action_policy','network1','launch','ok','rest')
    with store.connection() as db:
        db.execute("UPDATE wave2_events SET at=at-86400 WHERE stage='launch'")
    store.wave2_event('action_policy','network1','launch','issues','rest')
    store.wave2_event('action_policy','mcp-shared','launch','ok','mcp')
    store.wave2_event('action_policy','network2','launch','invalid_input','rest')
    with store.connection() as db:
        db.execute("UPDATE wave2_events SET at=at-86400 WHERE identity='network2'")
    store.wave2_event('action_policy','network2','launch','rate_limited','rest')
    store.wave2_event('action_policy','network2','paid_demand_signal','pricing','rest')
    store.wave2_event('action_policy','network1','paid_demand_signal','pilot','rest')
    metrics = store.wave2_metrics()
    assert metrics['estimated_rest_returning_network_ids']['action_policy'] == 1
    assert metrics['estimated_rest_interest_after_launch_network_ids']['action_policy'] == 1
