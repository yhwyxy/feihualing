from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_poem():
    response = client.post(
        "/poems",
        json={
            "title": "登鹳雀楼",
            "author_id": 4,
            "content": "白日依山尽，黄河入海流。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "登鹳雀楼"
    assert data["author_id"] == 4
    assert data["author"] == "王之涣"
    assert data["content"] == "白日依山尽，黄河入海流。"