from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_poems():
    response = client.get("/poems")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1
    assert "title" in data["items"][0]
    assert "author" in data["items"][0]
    assert "content" in data["items"][0]
