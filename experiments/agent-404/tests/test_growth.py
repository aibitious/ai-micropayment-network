"""Privacy-safe acquisition instrumentation: not a claim of unique people."""
from fastapi.testclient import TestClient
from agent404.api import create_app
from agent404.store import Store
import sqlite3
import time


def test_playground_has_synthetic_example_and_real_endpoint(tmp_path):
    app = create_app(db_path=str(tmp_path / "demo.sqlite3"), secret="test-secret")
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert 'Try a working demo' in home.text
        assert 'rel="canonical"' in home.text
        detail = client.get("/tools/json_guard")
        assert detail.status_code == 200
        assert '<textarea' in detail.text
        assert 'fetch(endpoint' in detail.text
        assert 'data-slug="json_guard"' in detail.text
        assert client.get("/tools/does_not_exist").status_code == 404
        result = client.post("/v1/lab/json_guard", json={
            "document": {"id": 1},
            "schema": {"type": "object", "required": ["id"]}},
            headers={"X-404-Client-Surface": "web-playground"})
        assert result.status_code == 200


def test_discovery_separates_synthetic_bot_and_unclassified(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-private-monitor-token")
    db_path = str(tmp_path / "discovery.sqlite3")
    app = create_app(db_path=db_path, secret="test-secret")
    with TestClient(app) as client:
        assert client.get("/", headers={
            "x-404-internal-test": "test-private-monitor-token"}).status_code == 200
        assert client.get("/tools/", headers={"user-agent": "Googlebot/2.1"}).status_code == 200
        assert client.get("/docs", headers={"user-agent": "Mozilla/5.0",
                                           }).status_code == 200
        assert client.get("/tools/json_guard?src=github",
                          headers={"user-agent": "Mozilla/5.0"}).status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/v1/lab/metrics").status_code == 403
        report = client.get("/v1/lab/metrics",
                            headers={"authorization": "Bearer test-private-monitor-token"}).json()
        rows = report["discovery"]["by_day_route"]
        assert report["discovery"]["internal_probes_excluded"] == 1
        assert not any(x["route"] == "landing" for x in rows)
        assert any(x["route"] == "tools_directory" and
                   x["segment"] == "declared_automated" for x in rows)
        assert any(x["route"] == "tool_detail" and x["campaign"] == "github" for x in rows)
        assert any(x["route"] == "health_probe" for x in rows)
        assert "people" in report["discovery"]["interpretation"]
        assert "estimated_returning_unclassified_network_ids" in report["discovery"]
        with sqlite3.connect(db_path) as db:
            schema = [r[1] for r in db.execute("PRAGMA table_info(discovery_events)")]
            assert not any(k in schema for k in ("user_agent", "ip_address", "referrer", "payload"))


def test_unclassified_does_not_mean_confirmed_human_and_returning_is_days(tmp_path):
    store = Store(str(tmp_path / "repeat.sqlite3"))
    store.discovery_event("landing", "GET", "network-hmac-a", "unclassified",
                          "unattributed", 200)
    store.discovery_event("landing", "GET", "network-hmac-a", "unclassified",
                          "unattributed", 200)
    assert store.discovery_metrics()["estimated_returning_unclassified_network_ids"] == 0
    with store.connection() as db:
        db.execute("UPDATE discovery_events SET at=at-86400 WHERE id=1")
    assert store.discovery_metrics()["estimated_returning_unclassified_network_ids"] == 1
    assert "NOT confirmed people" in store.discovery_metrics()["interpretation"]


def test_playground_channel_does_not_impersonate_agent_rest(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "read-only-test-admin")
    app = create_app(db_path=str(tmp_path / "channel.sqlite3"), secret="secret")
    with TestClient(app) as client:
        client.post("/v1/lab/schema_diff", json={"before": {}, "after": {}},
                    headers={"X-404-Client-Surface": "web-playground"})
        result = client.get("/v1/lab/metrics", headers={
            "Authorization": "Bearer read-only-test-admin"}).json()
        assert any(row["channel"] == "rest_playground" for row in result["tool_channels"])
        assert not any(row["channel"] == "rest" for row in result["tool_channels"])


def test_head_probes_are_readable_but_unknown_tools_are_not(tmp_path):
    app = create_app(db_path=str(tmp_path / 'head.sqlite3'), secret='secret')
    with TestClient(app) as client:
        for path in ('/', '/tools/', '/tools/json_guard', '/docs',
                     '/llms.txt', '/sitemap.xml', '/v1/lab/catalog'):
            assert client.head(path).status_code == 200
        assert client.head('/tools/not_a_tool').status_code == 404
