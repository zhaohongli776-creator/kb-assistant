"""M1 的 D4：8 个接口测试。用内存仓库，不需要数据库也能全绿。

    pytest -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from repo import InMemoryRepo

VALID = {"filename": "policy.pdf", "size_bytes": 1024}


@pytest.fixture()
def client():
    repo = InMemoryRepo()
    main.app.dependency_overrides[main.get_repo] = lambda: repo
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_returns_201_and_id(client):
    r = client.post("/documents", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["status"] == "pending"
    assert body["filename"] == "policy.pdf"


def test_create_duplicate_returns_409(client):
    assert client.post("/documents", json=VALID).status_code == 201
    r = client.post("/documents", json=VALID)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "bad",
    [
        {"filename": "no-extension", "size_bytes": 10},
        {"filename": "ok.pdf", "size_bytes": -1},
        {"filename": "", "size_bytes": 10},
        {"size_bytes": 10},
    ],
)
def test_create_invalid_returns_422(client, bad):
    assert client.post("/documents", json=bad).status_code == 422


def test_list_returns_created_items(client):
    client.post("/documents", json=VALID)
    client.post("/documents", json={"filename": "faq.md", "size_bytes": 20})
    r = client.get("/documents")
    assert r.status_code == 200
    names = {d["filename"] for d in r.json()}
    assert names == {"policy.pdf", "faq.md"}


def test_get_existing(client):
    doc_id = client.post("/documents", json=VALID).json()["id"]
    r = client.get(f"/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["id"] == doc_id


def test_get_missing_returns_404(client):
    assert client.get("/documents/999").status_code == 404


def test_delete_then_get_returns_404(client):
    doc_id = client.post("/documents", json=VALID).json()["id"]
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get(f"/documents/{doc_id}").status_code == 404
