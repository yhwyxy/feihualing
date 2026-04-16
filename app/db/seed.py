import argparse

from app.db.connection import get_connection

AUTHOR_DATA = [
    {"name": "李白", "bio": "唐代诗人，字太白，号青莲居士。"},
    {"name": "孟浩然", "bio": "唐代诗人，山水田园诗派代表人物。"},
    {"name": "王之涣", "bio": "唐代诗人，以边塞诗闻名。"},
]

POEM_DATA = [
    {
        "title": "静夜思",
        "author": "李白",
        "content": "床前明月光，\n疑是地上霜。\n举头望明月，\n低头思故乡。",
    },
    {
        "title": "春晓",
        "author": "孟浩然",
        "content": "春眠不觉晓，\n处处闻啼鸟。\n夜来风雨声，\n花落知多少。",
    },
    {
        "title": "登鹳雀楼",
        "author": "王之涣",
        "content": "白日依山尽，\n黄河入海流。\n欲穷千里目，\n更上一层楼。",
    },
    {
        "title": "黄鹤楼送孟浩然之广陵",
        "author": "李白",
        "content": "故人西辞黄鹤楼，\n烟花三月下扬州。\n孤帆远影碧空尽，\n唯见长江天际流。",
    },
]

COLLECTION_DATA = [
    {"name": "唐诗精选", "description": "收录常见唐诗名篇。"},
]

COLLECTION_POEM_DATA = {
    "唐诗精选": ["静夜思", "春晓"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo data for feihualing")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="truncate tables and recreate demo data",
    )
    return parser.parse_args()



def ensure_empty_database(cur) -> None:
    cur.execute(
        """
        SELECT EXISTS (SELECT 1 FROM authors)
            OR EXISTS (SELECT 1 FROM poems)
            OR EXISTS (SELECT 1 FROM collections)
            OR EXISTS (SELECT 1 FROM collection_poems)
        """
    )
    has_data = cur.fetchone()[0]
    if has_data:
        raise RuntimeError("Database is not empty. Re-run with --reset to recreate demo data.")



def reset_database(cur) -> None:
    cur.execute(
        "TRUNCATE TABLE collection_poems, collections, poems, authors RESTART IDENTITY CASCADE"
    )



def seed_authors(cur) -> dict[str, int]:
    author_ids: dict[str, int] = {}
    for author in AUTHOR_DATA:
        cur.execute(
            """
            INSERT INTO authors (name, bio)
            VALUES (%s, %s)
            RETURNING id
            """,
            (author["name"], author["bio"]),
        )
        author_ids[author["name"]] = cur.fetchone()[0]
    return author_ids



def seed_poems(cur, author_ids: dict[str, int]) -> dict[str, int]:
    poem_ids: dict[str, int] = {}
    for poem in POEM_DATA:
        cur.execute(
            """
            INSERT INTO poems (title, author_id, content)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (poem["title"], author_ids[poem["author"]], poem["content"]),
        )
        poem_ids[poem["title"]] = cur.fetchone()[0]
    return poem_ids



def seed_collections(cur) -> dict[str, int]:
    collection_ids: dict[str, int] = {}
    for collection in COLLECTION_DATA:
        cur.execute(
            """
            INSERT INTO collections (name, description)
            VALUES (%s, %s)
            RETURNING id
            """,
            (collection["name"], collection["description"]),
        )
        collection_ids[collection["name"]] = cur.fetchone()[0]
    return collection_ids



def seed_collection_poems(cur, collection_ids: dict[str, int], poem_ids: dict[str, int]) -> None:
    for collection_name, titles in COLLECTION_POEM_DATA.items():
        collection_id = collection_ids[collection_name]
        for title in titles:
            cur.execute(
                """
                INSERT INTO collection_poems (collection_id, poem_id)
                VALUES (%s, %s)
                """,
                (collection_id, poem_ids[title]),
            )



def seed_database(reset: bool) -> tuple[int, int, int]:
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                if reset:
                    reset_database(cur)
                else:
                    ensure_empty_database(cur)

                author_ids = seed_authors(cur)
                poem_ids = seed_poems(cur, author_ids)
                collection_ids = seed_collections(cur)
                seed_collection_poems(cur, collection_ids, poem_ids)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return len(author_ids), len(poem_ids), len(collection_ids)



def main() -> None:
    args = parse_args()

    try:
        author_count, poem_count, collection_count = seed_database(reset=args.reset)
    except RuntimeError as exc:
        raise SystemExit(f"Seed 未执行：{exc}\n如需重建演示数据，请运行：uv run python -m app.db.seed --reset") from exc

    print(
        f"Seed 完成：authors={author_count}, poems={poem_count}, collections={collection_count}"
    )


if __name__ == "__main__":
    main()
