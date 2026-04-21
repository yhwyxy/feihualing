import psycopg
from pgvector.psycopg import register_vector

from app.core.config import settings


def get_connection() -> psycopg.Connection:
    conn = psycopg.connect(settings.database_url)
    register_vector(conn)
    return conn
