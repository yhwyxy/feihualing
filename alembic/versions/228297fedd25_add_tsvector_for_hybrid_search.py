"""add_tsvector_for_hybrid_search

Revision ID: 228297fedd25
Revises: 1f39babb7324
Create Date: 2026-04-20 15:57:34.625322

"""
from typing import Sequence, Union

from alembic import op


revision: str = "228297fedd25"
down_revision: Union[str, Sequence[str], None] = "1f39babb7324"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'zhcfg') THEN
            CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser);
            ALTER TEXT SEARCH CONFIGURATION zhcfg
              ADD MAPPING FOR n,v,a,i,e,l,d,r,t,j,k,s,f,x WITH simple;
          END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE poems ADD COLUMN IF NOT EXISTS search_tsv tsvector")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION poems_tsv_update() RETURNS trigger AS $$
        BEGIN
          NEW.search_tsv := to_tsvector('zhcfg',
            COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_poems_tsv ON poems")
    op.execute(
        """
        CREATE TRIGGER trg_poems_tsv BEFORE INSERT OR UPDATE OF title, content ON poems
          FOR EACH ROW EXECUTE FUNCTION poems_tsv_update()
        """
    )
    op.execute(
        """
        UPDATE poems SET search_tsv = to_tsvector('zhcfg',
          COALESCE(title, '') || ' ' || COALESCE(content, ''))
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_poems_search_tsv ON poems USING GIN (search_tsv)"
    )

    op.execute("ALTER TABLE authors ADD COLUMN IF NOT EXISTS search_tsv tsvector")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION authors_tsv_update() RETURNS trigger AS $$
        BEGIN
          NEW.search_tsv := to_tsvector('zhcfg',
            COALESCE(NEW.name, '') || ' ' || COALESCE(NEW.bio, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_authors_tsv ON authors")
    op.execute(
        """
        CREATE TRIGGER trg_authors_tsv BEFORE INSERT OR UPDATE OF name, bio ON authors
          FOR EACH ROW EXECUTE FUNCTION authors_tsv_update()
        """
    )
    op.execute(
        """
        UPDATE authors SET search_tsv = to_tsvector('zhcfg',
          COALESCE(name, '') || ' ' || COALESCE(bio, ''))
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_authors_search_tsv ON authors USING GIN (search_tsv)"
    )

    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS search_tsv tsvector")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION collections_tsv_update() RETURNS trigger AS $$
        BEGIN
          NEW.search_tsv := to_tsvector('zhcfg',
            COALESCE(NEW.name, '') || ' ' || COALESCE(NEW.description, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_collections_tsv ON collections")
    op.execute(
        """
        CREATE TRIGGER trg_collections_tsv BEFORE INSERT OR UPDATE OF name, description ON collections
          FOR EACH ROW EXECUTE FUNCTION collections_tsv_update()
        """
    )
    op.execute(
        """
        UPDATE collections SET search_tsv = to_tsvector('zhcfg',
          COALESCE(name, '') || ' ' || COALESCE(description, ''))
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_collections_search_tsv ON collections USING GIN (search_tsv)"
    )

    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_tsv tsvector")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION document_chunks_tsv_update() RETURNS trigger AS $$
        BEGIN
          NEW.search_tsv := to_tsvector('zhcfg', COALESCE(NEW.content, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_tsv ON document_chunks")
    op.execute(
        """
        CREATE TRIGGER trg_document_chunks_tsv BEFORE INSERT OR UPDATE OF content ON document_chunks
          FOR EACH ROW EXECUTE FUNCTION document_chunks_tsv_update()
        """
    )
    op.execute(
        """
        UPDATE document_chunks SET search_tsv = to_tsvector('zhcfg', COALESCE(content, ''))
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_search_tsv "
        "ON document_chunks USING GIN (search_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_search_tsv")
    op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_tsv ON document_chunks")
    op.execute("DROP FUNCTION IF EXISTS document_chunks_tsv_update")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_tsv")

    op.execute("DROP INDEX IF EXISTS idx_collections_search_tsv")
    op.execute("DROP TRIGGER IF EXISTS trg_collections_tsv ON collections")
    op.execute("DROP FUNCTION IF EXISTS collections_tsv_update")
    op.execute("ALTER TABLE collections DROP COLUMN IF EXISTS search_tsv")

    op.execute("DROP INDEX IF EXISTS idx_authors_search_tsv")
    op.execute("DROP TRIGGER IF EXISTS trg_authors_tsv ON authors")
    op.execute("DROP FUNCTION IF EXISTS authors_tsv_update")
    op.execute("ALTER TABLE authors DROP COLUMN IF EXISTS search_tsv")

    op.execute("DROP INDEX IF EXISTS idx_poems_search_tsv")
    op.execute("DROP TRIGGER IF EXISTS trg_poems_tsv ON poems")
    op.execute("DROP FUNCTION IF EXISTS poems_tsv_update")
    op.execute("ALTER TABLE poems DROP COLUMN IF EXISTS search_tsv")
