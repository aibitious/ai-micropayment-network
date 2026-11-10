import pytest
from fastapi.testclient import TestClient
from agent404.api import create_app

@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path/'404.sqlite3'), secret='test-only-non-production-secret')

@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c
