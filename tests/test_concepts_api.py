from fastapi.testclient import TestClient

from app.db.connection import get_connection
from app.main import app
from app.services.concept_parser import normalize_term, parse_poem_concepts


client = TestClient(app)


def ensure_concept_data() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            for name, concept_type in (("月", "char"), ("明月", "phrase"), ("长安", "place"), ("唐", "dynasty")):
                cur.execute(
                    """
                    INSERT INTO concepts (name, normalized_name, type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (type, normalized_name) DO NOTHING
                    """,
                    (name, normalize_term(name), concept_type),
                )
        conn.commit()

    parse_poem_concepts(1)


def test_list_concepts():
    ensure_concept_data()

    response = client.get("/concepts", params={"keyword": "月"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["name"] == "月" for item in data["items"])


def test_get_poem_concepts():
    ensure_concept_data()

    response = client.get("/poems/1/concepts")

    assert response.status_code == 200
    data = response.json()
    assert data["poem_id"] == 1
    assert any(item["name"] == "月" for item in data["concepts"])


def test_feihualing_query():
    ensure_concept_data()

    response = client.get("/feihualing", params={"keyword": "月", "position": "any"})

    assert response.status_code == 200
    data = response.json()
    assert data["keyword"] == "月"
    assert data["total"] >= 1
    assert any("月" in item["line"] for item in data["items"])


def test_reparse_poem():
    ensure_concept_data()

    response = client.post("/poems/1/reparse")

    assert response.status_code == 200
    data = response.json()
    assert data["poem_id"] == 1
    assert data["status"] in {"pending", "running", "succeeded", "failed", "skipped"}
    assert isinstance(data["job_id"], int)


def test_alias_management():
    ensure_concept_data()

    create_response = client.post("/concepts/1/aliases", json={"alias": "月亮"})
    assert create_response.status_code == 200
    alias_id = create_response.json()["id"]

    list_response = client.get("/concepts/1/aliases")
    assert list_response.status_code == 200
    assert any(item["alias"] == "月亮" for item in list_response.json()["aliases"])

    delete_response = client.delete(f"/concepts/1/aliases/{alias_id}")
    assert delete_response.status_code == 200


def test_manual_line_concept_survives_reparse():
    ensure_concept_data()

    create_response = client.post(
        "/poems/1/concepts/manual",
        json={
            "concept_id": 3,
            "line_index": 0,
            "matched_text": "长安",
            "start_offset": 0,
        },
    )
    assert create_response.status_code == 200

    poem_concepts_response = client.get("/poems/1/concepts")
    assert poem_concepts_response.status_code == 200
    concepts = poem_concepts_response.json()["concepts"]
    assert any(item["id"] == 3 and item["source"] == "manual" for item in concepts)

    reparse_response = client.post("/poems/1/reparse")
    assert reparse_response.status_code == 200

    poem_concepts_after = client.get("/poems/1/concepts")
    concepts_after = poem_concepts_after.json()["concepts"]
    assert any(item["id"] == 3 for item in concepts_after)

    delete_response = client.delete(
        "/poems/1/concepts/manual",
        params={
            "concept_id": 3,
            "line_index": 0,
            "matched_text": "长安",
            "start_offset": 0,
        },
    )
    assert delete_response.status_code == 200


def test_parse_jobs_endpoints():
    ensure_concept_data()

    reparse_response = client.post("/poems/1/reparse")
    assert reparse_response.status_code == 200
    job_id = reparse_response.json()["job_id"]

    list_response = client.get("/concepts/parse-jobs", params={"poem_id": 1})
    assert list_response.status_code == 200
    assert any(item["id"] == job_id for item in list_response.json()["items"])

    detail_response = client.get(f"/concepts/parse-jobs/{job_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["job"]["id"] == job_id


def test_author_dynasty_endpoints():
    ensure_concept_data()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM concepts WHERE name = %s AND type = %s ORDER BY id ASC LIMIT 1", ("唐", "dynasty"))
            dynasty_id = cur.fetchone()[0]

    set_response = client.put("/authors/1/dynasty", json={"concept_id": dynasty_id})
    assert set_response.status_code == 200
    assert set_response.json()["name"] == "唐"

    get_response = client.get("/authors/1/dynasty")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "唐"

    delete_response = client.delete("/authors/1/dynasty")
    assert delete_response.status_code == 200
