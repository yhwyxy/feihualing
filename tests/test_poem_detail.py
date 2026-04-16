from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_poem():
    response = client.get("/poems/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "title" in data
    assert "author" in data
    assert "content" in data