import psycopg
from app.core.config import settings

def get_connection() -> psycopg.Connection:
    return psycopg.connect(settings.database_url)

