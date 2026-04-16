from app.db.connection import get_connection

def test_database_connection() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            res = cur.fetchall()

    assert res == [(1,)]