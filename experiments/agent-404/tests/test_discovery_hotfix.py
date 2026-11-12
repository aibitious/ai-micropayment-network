from fastapi.testclient import TestClient
from agent404.api import create_app
from agent404.store import Store

def test_public_demo_and_head(tmp_path):
    app = create_app(db_path=str(tmp_path / "demo.sqlite3"), secret="sample")
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
        assert c.get("/tools/json_guard").status_code == 200
        assert "textarea" in c.get("/tools/json_guard").text
        assert c.head("/tools/json_guard").status_code == 200
        assert c.head("/tools/nonexistent").status_code == 404
        r = c.post("/v1/lab/json_guard",
                   json={"document":{"id":1},"schema":{"type":"object","required":["id"]}},
                   headers={"X-404-Client-Surface":"web-playground"})
        assert r.status_code == 200
        with app.state.store.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM discovery_events").fetchone()[0] >= 3

def test_discovery_identity_is_anonymous_and_nonzero(tmp_path):
    store = Store(str(tmp_path / "db.sqlite3"))
    store.discovery_event("landing","GET","hashed-network-id","unclassified",
                          "unattributed",200)
    store.discovery_event("tools_directory","GET","hash-of-bot","declared_automated",
                          "unattributed",200)
    result = store.discovery_metrics()
    assert len(result["by_day_route"]) == 2
    assert result["estimated_returning_unclassified_network_ids"] == 0
    assert "NOT confirmed people" in result["interpretation"]
