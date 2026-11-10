from agent404.store import Store
from agent404.core import Resolver


def test_gaps_group_repeated_subjects(tmp_path):
    st=Store(str(tmp_path/'db.sqlite3'))
    re=Resolver(st,hash_secret='test')
    assert re.report_gap('Ships missing public berth data',True)['status']=='recorded'
    assert re.report_gap('SHIPS   MISSING PUBLIC BERTH DATA',True)['status']=='recorded'
    assert st.metrics()['top_gaps'][0]['requests']==2


def test_no_pii_into_gaps(tmp_path):
    st=Store(str(tmp_path/'db.sqlite3'))
    re=Resolver(st,hash_secret='test')
    for topic in ['contact jane@example.com now','Bearer abcde_private_token','check http://example.org /secret', 'read 127.0.0.1:80']:
        assert re.report_gap(topic, True)['status']=='not_recorded'
    assert st.metrics()['top_gaps']==[]


def test_identity_not_plain_address(tmp_path):
    re=Resolver(Store(str(tmp_path/'db.sqlite3')),hash_secret='secret')
    assert '192.0.2.10' not in re.identity('192.0.2.10')
    assert re.identity('192.0.2.10') != re.identity('192.0.2.11')
