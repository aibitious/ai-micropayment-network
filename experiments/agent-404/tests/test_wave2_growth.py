from fastapi.testclient import TestClient
from agent404.api import create_app
from agent404 import wave2
import sqlite3
from xml.etree import ElementTree


def test_full_32_tool_discovery_and_free_experiment(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "synthetic-admin-test")
    app = create_app(db_path=str(tmp_path / "wave2-discovery.sqlite3"), secret="synthetic")
    with TestClient(app) as c:
        assert c.get("/health").json()["experiments"] == 10
        assert c.get("/health").json()["wave2_prototypes"] == 22
        assert len(c.get("/v1/lab/catalog").json()["tools"]) == 9
        assert len(c.get("/v1/wave2/catalog").json()["prototypes"]) == 22
        landing = c.get("/").text
        assert "/404/wave2/" in landing
        assert "22" in landing
        directory = c.get("/wave2/")
        assert directory.status_code == 200
        assert "Action Policy Simulator" in directory.text
        assert c.head("/wave2/").status_code == 200
        assert c.head("/wave2/action_policy").status_code == 200
        assert c.head("/wave2/not_there").status_code == 404
        page = c.get("/wave2/action_policy")
        assert page.status_code == 200
        assert "wave2-demo" in page.text
        assert "web-playground" in page.text
        assert "data-signal" in page.text

        payload = wave2.EXAMPLES["action_policy"]
        demo = c.post("/v1/wave2/action_policy", json=payload, headers={
            "X-404-Client-Surface": "web-playground"})
        assert demo.status_code == 200
        interest = c.post("/v1/wave2/action_policy/interest", json={"signal": "pilot"},
                          headers={"X-404-Client-Surface": "web-playground"})
        assert interest.status_code == 200
        m = c.get("/v1/wave2/metrics", headers={
            "Authorization": "Bearer synthetic-admin-test"}).json()
        stages = [row for row in m["funnel_events"] if row["tool"] == "action_policy"]
        assert any(x["channel"] == "rest_playground" and x["stage"] == "launch"
                   for x in stages)
        assert any(x["channel"] == "rest_playground" and x["stage"] == "paid_demand_signal"
                   for x in stages)
        assert m["estimated_rest_returning_network_ids"].get("action_policy", 0) == 0
        assert m["estimated_rest_interest_after_launch_network_ids"].get("action_policy", 0) == 0
        assert c.get("/v1/payments").json()["enabled"] is False


def test_32_canonical_pages_and_no_directory_fanout(tmp_path):
    db_path = str(tmp_path / "directory.sqlite3")
    app = create_app(db_path=db_path, secret="synthetic")
    with TestClient(app) as c:
        urls = [node.text for node in ElementTree.fromstring(c.get('/sitemap.xml').text)
                .iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        tool_urls = [url for url in urls if '/tools/' in url and not url.endswith('/tools/')]
        wave_urls = [url for url in urls if '/wave2/' in url and not url.endswith('/wave2/')]
        assert len(tool_urls) == 10 and len(wave_urls) == 22
        for url in tool_urls + wave_urls:
            page = c.get(url.removeprefix('https://aibitious.com/404'))
            assert page.status_code == 200
            assert f'<link rel="canonical" href="{url}">' in page.text
        assert c.head('/tools/cve_verify').status_code == 200
        assert c.get('/').text.count('32 free tools') >= 1
        assert '22 offline decision prototypes' in c.get('/llms.txt').text
        assert c.get('/v1/catalog').json()['version'] == '0.3.0'
        c.get('/wave2/')
        c.get('/v1/wave2/catalog')
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM wave2_events WHERE stage='discovery'").fetchone()[0] == 22
        assert db.execute("SELECT COUNT(*) FROM discovery_events WHERE route='wave2_directory'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM discovery_events WHERE route='wave2_catalog'").fetchone()[0] == 1
